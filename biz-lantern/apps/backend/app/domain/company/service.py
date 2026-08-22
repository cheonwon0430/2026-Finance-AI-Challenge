from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.model import Company
from app.domain.company.repository import CompanyRepository
from app.domain.company.schema import CompanyCreate
from app.domain.company.api.nts_api import (
    get_business_status as fetch_business_status,
)
from app.domain.company.api.kipris_api import get_company_by_company_name
from app.domain.company.pipeline import find_corp_candidates


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

    async def get_company(
        self,
        company_id: int,
    ) -> Company | None:
        return await self.repository.get_by_id(company_id)

    async def get_company_by_kipris_id(
        self,
        company_name: str,
    ) -> str | None:
        return get_company_by_company_name(company_name)

    def get_business_status(self, b_no_list: list[str]) -> str:
        return fetch_business_status(b_no_list)

    async def search_companies_by_name(
        self,
        company_name: str,
    ) -> list[dict]:
        """DART corp_code 후보 검색. corp_search 는 pipeline 을 거쳐서만 쓴다."""
        return await find_corp_candidates(company_name)