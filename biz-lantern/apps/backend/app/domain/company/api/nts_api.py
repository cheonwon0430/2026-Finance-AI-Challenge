"""
국세청 사업자등록정보 조회 (공공데이터포털 odcloud.kr).

DART 기업개황에서 확보한 bizr_no(사업자등록번호, 10자리 숫자)를 넣어
폐업·휴업 여부를 확인하거나(상태조회), 대표자명·개업일자까지 대조한다(진위확인).
"""

import json
from urllib.parse import unquote

import httpx

from app.common.config import settings

BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1"

# 두 엔드포인트 모두 한 번에 최대 100건까지만 받는다
MAX_BATCH = 100

NTS_VALID_MATCH = "01"  # 진위확인(valid): 사업자번호/대표자/개업일이 국세청 기록과 일치
NTS_STATUS_ACTIVE = "01"  # 상태조회(status.b_stt_cd): 계속사업자


# ---------------------------------------------------------------------------
# 1. 공통
# ---------------------------------------------------------------------------
def _check_batch(items: list, label: str) -> None:
    """API 를 때리기 전에 건수 제약을 끊는다."""
    if not items:
        raise ValueError(f"조회할 {label}가 없습니다.")
    if len(items) > MAX_BATCH:
        raise ValueError(
            f"한 번에 최대 {MAX_BATCH}건까지만 조회할 수 있습니다. (요청 {len(items)}건)"
        )


def _params() -> dict[str, str]:
    """인증키 params. 공공데이터포털 키는 URL 인코딩된 형태(%2B, %3D)로도 발급되는데
    httpx 가 params 를 다시 인코딩하므로 디코딩된 원본을 넘겨야 이중 인코딩을 피한다.
    이미 디코딩된 키에 unquote() 는 무해하다."""
    return {
        "serviceKey": unquote(settings.nts_api_key),
        "returnType": "JSON",
    }


# ---------------------------------------------------------------------------
# 2. 엔드포인트
# ---------------------------------------------------------------------------
def get_business_status(b_no_list: list[str]) -> str:
    """사업자등록 상태조회(/status). 응답이 이미 JSON 이라 원본 그대로 문자열로 반환.

    b_no_list 는 사업자등록번호(10자리 숫자, '-' 없이) 리스트로 한 번에 최대 100건.
    응답 data 의 b_stt 가 계속사업자 / 휴업자 / 폐업자 중 하나로 온다.
    """
    _check_batch(b_no_list, "사업자번호")

    payload = {"b_no": b_no_list}

    response = httpx.post(
        f"{BASE_URL}/status",
        params=_params(),
        json=payload,
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


def validate_business(businesses: list[dict]) -> str:
    """사업자등록정보 진위확인(/validate). 응답이 이미 JSON 이라 원본 그대로 문자열로 반환.

    businesses 각 항목은 b_no(사업자등록번호) / start_dt(개업일자 YYYYMMDD) /
    p_nm(대표자성명) 이 필수고 b_nm(상호), corp_no(법인등록번호) 등은 선택.
    한 번에 최대 100건. 응답 valid 가 01(일치) / 02(불일치) 로 온다.
    """
    _check_batch(businesses, "사업자 정보")

    payload = {"businesses": businesses}

    response = httpx.post(
        f"{BASE_URL}/validate",
        params=_params(),
        json=payload,
        timeout=30,
        follow_redirects=True,
    )
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 3. 판정
# ---------------------------------------------------------------------------
def check_business(bizr_no: str, ceo_nm: str, est_dt: str) -> dict[str, object]:
    """사업자 상태를 확인한다. 판정 근거를 통째로 돌려준다.

    **상태조회(/status)가 주 출처고 진위확인(/validate)은 신원 대조 보조다.**

    한동안 진위확인 하나만 불렀는데, 그러면 거의 모든 회사가 상태 미확인으로 떨어졌다.
    진위확인은 b_no·start_dt·p_nm 이 **전부** 국세청 기록과 일치해야 01 을 주는데,
    우리가 넣는 start_dt 는 DART 의 est_dt 곧 **설립일**이고 국세청이 대조하는 것은
    **개업일자**다. 둘은 자주 다르다. 게다가 불일치(02)면 응답에 status 가 아예 실려
    오지 않아 상태값을 잃는다. 센트비 실측 - /validate 는 02("확인할 수 없습니다"),
    /status 는 같은 사업자번호로 "계속사업자"를 정상 반환했다.

    그래서 둘을 갈랐다. 상태는 b_no 하나만 있으면 되는 /status 에서 받고, 진위확인은
    "대표자·개업일까지 국세청과 맞는가" 라는 **별개의 사실**로 남긴다. 진위확인 실패가
    상태 확인을 막지 않는다.

    bool 하나로 줄이지 않는 이유는 그대로다. 실패에는 서로 다른 것이 섞여 있고
    보고서에서는 절대 같이 취급하면 안 된다.

        대표자·개업일 불일치   신원 대조에 실패했다. 폐업이라는 뜻이 전혀 아니다
        휴업                  영업을 멈췄다
        폐업                  end_dt 에 폐업일이 실려 온다

    돌려주는 값:

        verified     진위확인 통과 여부 (valid == "01"). 신원 대조 결과일 뿐이다
        valid_code   valid 원문. 호출 자체가 실패했으면 None
        operating    계속사업자 여부. **status 기반이고 verified 와 무관하다**
        status       b_stt 원문 ("계속사업자" / "휴업자" / "폐업자")
        closed_at    end_dt. 폐업일이 있으면 그대로
    """
    # 1. 상태조회 - 주 출처. 사업자번호 하나면 된다.
    status_data = json.loads(get_business_status([bizr_no]))["data"]
    status = status_data[0] if status_data else {}
    status_code = status.get("b_stt_cd") or None

    # 2. 진위확인 - 신원 대조 보조. 실패해도 상태 확인을 막지 않는다.
    #    DART는 공동대표를 "홍길동, 김철수"처럼 쉼표로 합쳐 주지만, 국세청 API는
    #    대표자를 p_nm(1인)/p_nm2(공동대표 2인째)로 나눠 받으므로 분리해서 넣는다.
    ceo_names = [name.strip() for name in (ceo_nm or "").split(",") if name.strip()]

    valid_code: str | None = None
    if ceo_names and est_dt:
        business = {"b_no": bizr_no, "start_dt": est_dt, "p_nm": ceo_names[0]}
        if len(ceo_names) > 1:
            business["p_nm2"] = ceo_names[1]

        try:
            valid_data = json.loads(validate_business([business]))["data"]
        except (httpx.HTTPError, ValueError, KeyError):
            # 신원 대조는 부가 정보다. 여기서 실패해도 상태는 이미 확보했다.
            valid_data = []

        if valid_data:
            valid_code = valid_data[0].get("valid")

    return {
        "verified": valid_code == NTS_VALID_MATCH,
        "valid_code": valid_code,
        "operating": (status_code == NTS_STATUS_ACTIVE) if status_code else None,
        "status_code": status_code,
        "status": status.get("b_stt") or None,
        "tax_type": status.get("tax_type") or None,
        "closed_at": status.get("end_dt") or None,
    }


def is_operating_business(bizr_no: str, ceo_nm: str, est_dt: str) -> bool:
    """check_business 의 bool 요약. 기존 호출부를 위해 남겨 둔다.

    '운영 중이 아니다' 와 '확인하지 못했다' 가 여기서는 똑같이 False 가 되므로,
    보고서처럼 그 둘을 구분해야 하는 쪽은 check_business 를 직접 쓴다.
    """
    return bool(check_business(bizr_no, ceo_nm, est_dt)["operating"])


if __name__ == "__main__":
    import sys

    # 진위확인은 한 건당 필드가 3개라 CLI 로 넘기기 번거로워 상태조회만 노출한다
    # python -m app.domain.company.api.nts_api 1234567890 1234567891
    print(get_business_status(sys.argv[1:]))
