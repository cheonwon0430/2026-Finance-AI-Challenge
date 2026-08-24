from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.model import Company


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.flush()
        await self.session.refresh(company)

        return company