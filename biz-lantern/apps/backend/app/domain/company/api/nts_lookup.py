"""
국세청 사업자등록정보 조회 (공공데이터포털 odcloud.kr).

DART 기업개황에서 확보한 bizr_no(사업자등록번호, 10자리 숫자)를 넣어
폐업·휴업 여부를 확인하거나(상태조회), 대표자명·개업일자까지 대조한다(진위확인).
"""
import json

import httpx

from app.common.config import settings

BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1"


def get_business_status(b_no_list: list[str]) -> str:
    """사업자등록 상태조회(/status). 응답이 이미 JSON 이라 원본 그대로 문자열로 반환.

    b_no_list 는 사업자등록번호(10자리 숫자, '-' 없이) 리스트로 한 번에 최대 100건.
    응답 data 의 b_stt 가 계속사업자 / 휴업자 / 폐업자 중 하나로 온다.
    """
    params = {
        "serviceKey": settings.nts_service_key,
        "returnType": "JSON",
    }
    payload = {"b_no": b_no_list}

    response = httpx.post(
        f"{BASE_URL}/status", params=params, json=payload, timeout=30, follow_redirects=True
    )
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


def validate_business(businesses: list[dict]) -> str:
    """사업자등록정보 진위확인(/validate). 응답이 이미 JSON 이라 원본 그대로 문자열로 반환.

    businesses 각 항목은 b_no(사업자등록번호) / start_dt(개업일자 YYYYMMDD) /
    p_nm(대표자성명) 이 필수고 b_nm(상호), corp_no(법인등록번호) 등은 선택.
    한 번에 최대 100건. 응답 valid 가 01(일치) / 02(불일치) 로 온다.
    """
    params = {
        "serviceKey": settings.nts_service_key,
        "returnType": "JSON",
    }
    payload = {"businesses": businesses}

    response = httpx.post(
        f"{BASE_URL}/validate", params=params, json=payload, timeout=30, follow_redirects=True
    )
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    # 진위확인은 한 건당 필드가 3개라 CLI 로 넘기기 번거로워 상태조회만 노출한다
    # python -m app.domain.company.api.nts_lookup 1234567890 1234567891
    print(get_business_status(sys.argv[1:]))
