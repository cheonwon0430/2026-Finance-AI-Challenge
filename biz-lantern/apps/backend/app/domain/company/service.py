import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.model import Company
from app.domain.company.repository import CompanyRepository
from app.domain.company.schema import CompanyCreate
from app.domain.company.api.nts_api import (
    get_business_status as fetch_business_status,
)
from app.domain.company.api.kipris_api import (
    get_company_by_application_number,
    get_company_by_company_name,
)
from app.domain.company.api.corp_search import normalize, search_by_name
from app.domain.company.pipeline import collect
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)

logger = logging.getLogger(__name__)

# KIPRIS 는 특허 검색 1회 + 특허마다 행정이력 1회(최대 10건 페이지 크기)로 최대 11회,
# collect() 는 DART/국세청을 5단계에 걸쳐 순차 호출한다. 각 외부 호출 자체에도 타임아웃이
# 있지만, 요청 전체가 지나치게 오래 걸리는 경우(외부 API가 매번 타임아웃 직전까지 느리게
# 응답하는 등)에도 이 요청 하나가 무한정 이벤트 루프를 붙들지 않도록 전체 상한을 둔다.
OVERVIEW_TIMEOUT_SECONDS = 600


class CompanyService:
    def __init__(self, session: AsyncSession):
        self.repository = CompanyRepository(session)

    async def create_company(
        self,
        data: CompanyCreate,
    ) -> Company:
        company = Company(
            name=data.name,
            industry=data.industry,
        )

        return await self.repository.create(company)

    async def get_company_by_kipris_id(
        self,
        company_name: str,
    ) -> str | None:
        return get_company_by_company_name(company_name)

    def get_business_status(self, b_no_list: list[str]) -> str:
        return fetch_business_status(b_no_list)

    @staticmethod
    def _extract_kipris_items(raw_json: str, key: str, fallback_key: str | None = None) -> list[dict]:
        """kipris_api.py 가 돌려주는 JSON 문자열의 response.body.items 밑에서 항목 목록을 뽑는다.

        특허 목록(PatentUtilityInfo)과 행정이력 목록(RelatedDocsonfileInfo/item)
        둘 다 이 구조를 그대로 따라서 하나의 헬퍼로 공유한다. 파싱 경로는
        kipris_api.py 에 주석으로 남아있던 기존 로직을 그대로 따른 것이다 - 실제
        KIPRIS 응답으로 검증된 적이 없는 추정 구조라, 예상과 다른 구조가 오면
        예외 대신 빈 리스트로 처리한다(0건과 동일하게 취급해 전체 조회를
        실패시키지 않는다).

        Args:
            raw_json: kipris_api.py 두 함수 중 하나가 돌려준 JSON 문자열.
            key: items 밑에서 찾을 주 키(예: "PatentUtilityInfo").
            fallback_key: key 가 없을 때 대신 찾을 키(예: 행정이력의 "item").
        """
        try:
            body = json.loads(raw_json).get("response", {}).get("body", {})
            items = body.get("items") or {}
            info = items.get(key)
            if info is None and fallback_key is not None:
                info = items.get(fallback_key)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("KIPRIS 응답 파싱 실패 (예상 구조와 다름): key=%s", key)
            return []

        if not info:
            return []

        # xmltodict 특성상 결과가 1건이면 dict, 여러 건이면 list 로 오므로 리스트로 통일
        if isinstance(info, dict):
            info = [info]

        if not isinstance(info, list):
            logger.warning("KIPRIS 응답의 %s 값이 예상과 다른 타입임: %r", key, type(info))
            return []

        # 리스트 안에 dict 가 아닌 값(예: 빈 XML 태그가 None 으로 온 경우)이 섞여 있어도
        # 그 항목만 걸러내고 나머지는 정상 처리한다.
        return [entry for entry in info if isinstance(entry, dict)]

    async def _fetch_administrative_history(self, app_number: str) -> list[dict] | None:
        """출원번호 하나의 행정이력을 조회한다.

        get_company_by_application_number 는 동기 함수라 asyncio.to_thread 로
        감싼다. 실패하면(None) 그대로 None 을 돌려주고 예외를 올리지 않는다 -
        특허 하나의 행정이력 조회 실패로 전체 특허 목록 조회를 막지 않기 위해서다.
        """
        raw = await asyncio.to_thread(get_company_by_application_number, app_number)
        if raw is None:
            return None

        return self._extract_kipris_items(raw, "RelatedDocsonfileInfo", fallback_key="item")

    async def get_company_patents(self, company_name: str) -> dict:
        """기업명으로 특허 목록과 특허별 행정이력을 조회한다.

        kipris_api.py 의 두 함수를 그대로 재사용한다. 둘 다 동기(httpx 동기
        클라이언트) 함수라서 asyncio.to_thread 로 감싸 이벤트 루프를 막지 않는다.

        Args:
            company_name: 특허 출원인으로 검색할 기업명.

        Returns:
            {"count": int, "items": [{"application_number", "invention_name",
            "applicant", "application_date", "status",
            "administrative_history"}, ...]}

        Raises:
            ExternalAPIError: KIPRIS 특허 검색 자체가 실패했을 때. 특허 0건은
                에러가 아니라 정상적인 빈 결과로 취급한다.
        """
        raw = await asyncio.to_thread(get_company_by_company_name, company_name)
        if raw is None:
            raise ExternalAPIError(f"KIPRIS 특허 조회 실패: company_name={company_name}")

        items = self._extract_kipris_items(raw, "PatentUtilityInfo")

        patents = []
        for item in items:
            app_number = item.get("ApplicationNumber")
            history = await self._fetch_administrative_history(app_number) if app_number else None

            patents.append(
                {
                    "application_number": app_number,
                    "invention_name": item.get("InventionName"),
                    "applicant": item.get("Applicant"),
                    "application_date": item.get("ApplicationDate"),
                    "status": item.get("RegistrationStatus"),
                    "administrative_history": history,
                }
            )

        return {"count": len(patents), "items": patents}

    async def run_company_pipeline(self, company_name: str) -> dict:
        """기업명으로 corp_code 를 찾아 pipeline.collect() 를 실행한다.

        corp_code 를 자동으로 고르지 않는다. 정확히 1건 매칭될 때만 진행하고,
        0건/2건 이상이면 각각 CompanyNotFoundError/AmbiguousCompanyNameError 를
        올린다 - pipeline.py CLI(_resolve_corp_code)와 동일한 안전 철학이다.

        Args:
            company_name: 파이프라인을 실행할 기업명.

        Returns:
            pipeline.collect() 가 돌려주는 CollectResult(dict) 그대로.

        Raises:
            CompanyNotFoundError: 매칭되는 corp_code 가 없을 때.
            AmbiguousCompanyNameError: corp_code 가 여러 건 매칭될 때.
            ExternalAPIError: collect() 가 치명적 실패로 예외를 올렸을 때.
        """
        matches = await search_by_name(company_name)

        if not matches:
            raise CompanyNotFoundError(f"'{company_name}' 에 매칭되는 기업이 없습니다.")

        if len(matches) > 1:
            # corp_search.search() 는 부분 일치라 "삼성전자" 검색이 "삼성전자서비스" 등과
            # 함께 여러 건 걸릴 수 있다. 정확히 일치하는 후보가 하나뿐이면 그것으로
            # 좁힌다 - 이건 자동으로 고르는 게 아니라 모호함을 해소하는 것이다.
            exact = [m for m in matches if normalize(m["corp_name"]) == normalize(company_name)]
            if len(exact) == 1:
                matches = exact

        if len(matches) > 1:
            raise AmbiguousCompanyNameError(company_name, matches)

        corp_code = matches[0]["corp_code"]

        # collect() 는 동기 함수(내부에서 DART/국세청을 여러 번 순차 호출)이므로
        # asyncio.to_thread 로 감싸 이벤트 루프를 막지 않는다.
        try:
            return await asyncio.to_thread(collect, corp_code)
        except Exception as error:
            raise ExternalAPIError(
                f"파이프라인 실행 실패: corp_code={corp_code}"
            ) from error

    async def get_company_overview(self, company_name: str) -> dict:
        """기업명 하나로 특허(+행정이력)와 수집 파이프라인 결과를 함께 조회한다.

        Router 가 호출하는 진입점. 두 조회는 서로 독립적인 외부 API 호출이라
        순차 실행한다(동시 실행은 지금 범위에서 불필요한 최적화로 보고 배제).

        Args:
            company_name: 조회할 기업명.

        Returns:
            {"company_name": str, "patents": dict, "pipeline": dict}.

        Raises:
            CompanyNotFoundError, AmbiguousCompanyNameError, ExternalAPIError:
                get_company_patents / run_company_pipeline 가 올리는 예외를
                그대로 전파한다.
            ExternalAPIError: 위 예외들과 별개로, 전체 처리가
                OVERVIEW_TIMEOUT_SECONDS 를 넘었을 때도 올라온다.
        """
        try:
            async with asyncio.timeout(OVERVIEW_TIMEOUT_SECONDS):
                patents = await self.get_company_patents(company_name)
                pipeline_result = await self.run_company_pipeline(company_name)
        except TimeoutError as error:
            raise ExternalAPIError(
                f"전체 조회 시간 초과({OVERVIEW_TIMEOUT_SECONDS}초): company_name={company_name}"
            ) from error

        return {
            "company_name": company_name,
            "patents": patents,
            "pipeline": pipeline_result,
        }