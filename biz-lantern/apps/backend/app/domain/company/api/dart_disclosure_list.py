import json

import httpx

from app.common.config import settings

URL = "https://opendart.fss.or.kr/api/list.json"


def get_disclosure_list(
    corp_code: str,
    bgn_de: str | None = None,
    end_de: str | None = None,
    pblntf_ty: str | None = None,
    pblntf_detail_ty: str | None = None,
    corp_cls: str | None = None,
    page_no: int | None = None,
    page_count: int | None = None,
    last_reprt_at: str | None = None,
) -> str:
    """공시검색(list.json) 조회. 응답이 이미 JSON 이라 원본 그대로 문자열로 반환.

    pblntf_detail_ty 는 F001(감사보고서) / F002 / F005(미제출신고) 등.
    """
    params = {
        "crtfc_key": settings.dart_api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "pblntf_ty": pblntf_ty,
        "pblntf_detail_ty": pblntf_detail_ty,
        "corp_cls": corp_cls,
        "page_no": page_no,
        "page_count": page_count,
        "last_reprt_at": last_reprt_at,
    }
    # 값을 주지 않은 선택 파라미터는 아예 보내지 않는다
    params = {key: value for key, value in params.items() if value is not None}

    response = httpx.get(URL, params=params, timeout=30, follow_redirects=True)
    response.raise_for_status()

    return json.dumps(response.json(), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    # python -m app.domain.company.api.dart_disclosure_list 01836952 F001 20200101
    print(get_disclosure_list(
        sys.argv[1],
        pblntf_detail_ty=sys.argv[2] if len(sys.argv) > 2 else None,
        bgn_de=sys.argv[3] if len(sys.argv) > 3 else None,
    ))
