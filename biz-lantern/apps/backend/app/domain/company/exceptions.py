"""Company 도메인 전용 예외.

Router 는 이 예외들만 각각 다른 HTTP 상태 코드로 변환한다. 그 외 예외는
그대로 전파해 FastAPI 기본 500 처리에 맡긴다.
"""


class CompanyNotFoundError(Exception):
    """기업명으로 DART corp_code 를 찾지 못했을 때."""


class AmbiguousCompanyNameError(Exception):
    """기업명이 DART corp_code 여러 건에 매칭될 때.

    corp_code 를 자동으로 고르지 않는다(엉뚱한 회사를 분석하게 될 위험이
    있어서다 - pipeline.py CLI 의 _resolve_corp_code 와 동일한 철학).
    candidates 에 후보를 그대로 담아 호출자가 참고하게 한다.
    """

    def __init__(self, company_name: str, candidates: list[dict]):
        self.company_name = company_name
        self.candidates = candidates
        super().__init__(
            f"'{company_name}' 에 매칭되는 기업이 {len(candidates)}건입니다. "
            "corp_code 로 특정해야 합니다."
        )


class ExternalAPIError(Exception):
    """KIPRIS/DART 등 외부 API 호출이 실패했을 때 (Timeout 포함).

    kipris_api.py 의 두 함수는 실패 시 예외 대신 None 을 반환하므로, 그
    None 을 이 예외로 변환해서 Router 까지 실패 신호를 전달한다.
    """
