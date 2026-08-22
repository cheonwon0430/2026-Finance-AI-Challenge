import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

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


class CompanyStatusResponse(BaseModel):
    b_no: str
    status: str


@router.get(
    "/{company_id}/status",
    response_model=List[CompanyStatusResponse],
)
def get_company_status(
    company_id: str,
    session: AsyncSession = Depends(
        get_db
    ),  # DB 조회 후 없으면 API 조회된 결과로 DB 최신화
):
    """
    기업 휴폐업 조회합니다.
    """

    b_no_list = [company_id]
    if not b_no_list:
        logging.warning("조회할 사업자번호가 없습니다.")
        raise HTTPException(
            status_code=404,
            detail="조회할 사업자번호가 없습니다.",
        )

    if len(b_no_list) > 100:
        logging.error("한 번에 최대 100개의 사업자번호만 조회할 수 없습니다.")
        raise HTTPException(
            status_code=404,
            detail="한 번에 최대 100개의 사업자번호만 조회할 수 없습니다.",
        )

    service = CompanyService(session)
    result = service.get_business_status(b_no_list)
    return result
