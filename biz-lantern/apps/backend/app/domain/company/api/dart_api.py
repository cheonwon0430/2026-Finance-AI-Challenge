import https

from app.common.config import settings
from app.domain.company.api.nts_api import is_operating_business

DART_COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"


def get_company_overview(corp_code: str) -> dict:
    """DART 기업개황 조회. 국세청 진위확인에 필요한 bizr_no/ceo_nm/est_dt가 여기서 나온다."""
    params = {
        # "crtfc_key": "f2c6d4368f027c88545f53a4b820545b1f26538ca6c5c8ceccaf98c1be827ea6",
        "crtfc_key": settings.dart_api_key,
        "corp_code": corp_code,
    }
    response = https.get(DART_COMPANY_URL, params=params)
    response.raise_for_status()

    data = response.json()
    if data.get("status") != "000":
        raise ValueError(f"DART 기업개황 조회 실패: {data.get('message')}")

    return data


def is_verified_operating_business(corp_code: str) -> bool:
    """DART 기업개황에서 bizr_no/ceo_nm/est_dt를 가져와 국세청 진위확인·상태조회로 검증한다."""
    overview = get_company_overview(corp_code)

    return is_operating_business(
        bizr_no=overview["bizr_no"],
        ceo_nm=overview["ceo_nm"],
        est_dt=overview["est_dt"],
    )


if __name__ == "__main__":
    result = is_verified_operating_business(corp_code="01836952")
    print(result)


