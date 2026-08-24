import json

import httpx

from app.common.config import settings

URL = "https://opendart.fss.or.kr/api/company.json"


def get_company(corp_code: str) -> str:
    """기업개황(company.json) 조회. 응답이 이미 JSON 이라 원본 그대로 문자열로 반환."""
    params = {
        "crtfc_key": settings.dart_api_key,
        "corp_code": corp_code,
    }

    response = httpx.get(URL, params=params, timeout=30, follow_redirects=True)
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    # python -m app.domain.company.api.dart_company 01836952
    print(get_company(sys.argv[1]))
