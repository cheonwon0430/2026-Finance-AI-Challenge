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
    """진위확인 한 번으로 사업자 상태를 확인한다. 판정 근거를 통째로 돌려준다.

    /validate 응답에 status 가 함께 실려 오므로 /status 를 따로 부르지 않는다.

    bool 하나로 줄이지 않는 이유가 있다. 실패에는 서로 다른 세 가지가 섞여 있는데,
    보고서에서는 그 셋을 절대 같이 취급하면 안 된다.

        대표자·개업일 불일치   국세청 기록과 대조에 실패했다. 폐업이라는 뜻이 아니다
        휴업                  영업을 멈췄다
        폐업                  end_dt 에 폐업일이 실려 온다

    "2024-03-15 폐업" 과 "DART 대표자명이 최신이 아니라 대조 실패" 는 위험도가
    정반대인데, bool 로 뭉개면 둘 다 그냥 False 가 된다.

    돌려주는 값:

        verified     진위확인 통과 여부 (valid == "01")
        operating    계속사업자 여부. 진위확인을 통과하지 못했으면 None(알 수 없음)
        status       b_stt 원문 ("계속사업자" / "휴업자" / "폐업자")
        closed_at    end_dt. 폐업일이 있으면 그대로
    """
    # DART는 공동대표를 "홍길동, 김철수"처럼 쉼표로 합쳐 주지만, 국세청 API는
    # 대표자를 p_nm(1인)/p_nm2(공동대표 2인째)로 나눠 받으므로 분리해서 넣는다.
    ceo_names = [name.strip() for name in (ceo_nm or "").split(",") if name.strip()]
    if not ceo_names:
        raise ValueError("대표자명이 없어 진위확인을 요청할 수 없습니다.")

    business = {
        "b_no": bizr_no,
        "start_dt": est_dt,
        "p_nm": ceo_names[0],
    }
    if len(ceo_names) > 1:
        business["p_nm2"] = ceo_names[1]

    data = json.loads(validate_business([business]))["data"]
    if not data:
        return {
            "verified": False,
            "valid_code": None,
            "operating": None,
            "status_code": None,
            "status": None,
            "tax_type": None,
            "closed_at": None,
        }

    result = data[0]
    status = result.get("status") or {}

    # 진위확인을 먼저 본다. 대표자/개업일이 국세청 기록과 다르면 "실존 확인 불가"라
    # 상태값을 해석할 근거가 없다. 그래서 operating 을 False 가 아니라 None 으로 둔다.
    verified = result.get("valid") == NTS_VALID_MATCH
    status_code = status.get("b_stt_cd")

    return {
        "verified": verified,
        "valid_code": result.get("valid"),
        "operating": (status_code == NTS_STATUS_ACTIVE) if verified else None,
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
