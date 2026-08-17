from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.schema import CompanyCreate, CompanyResponse
from app.domain.company.service import CompanyService
from app.infrastructure.database.session import get_db


router = APIRouter(
    prefix="/companies",
    tags=["Company"],
)


@router.post(
    "",
    response_model=CompanyResponse,
)
async def create_company(
    data: CompanyCreate,
    session: AsyncSession = Depends(get_db),
):
    service = CompanyService(session)

    company = await service.create_company(data)

    await session.commit()

    return company


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
)
async def get_company(
    company_id: int,
    session: AsyncSession = Depends(get_db),
):
    service = CompanyService(session)

    company = await service.get_company(company_id)

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    return company