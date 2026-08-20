from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.model import Company
from app.domain.company.repository import CompanyRepository
from app.domain.company.schema import CompanyCreate
from app.domain.company.api.nts_api import read_business_status

from typing import List


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

    def get_business_status(self, b_no_list: List) -> object | None:
        return read_business_status(b_no_list)
