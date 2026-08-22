import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.domain.company.schema import (
    CompanyCreate,
    CompanyOverviewResponse,
    CompanyResponse,
)
from app.domain.company.service import CompanyService
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)
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


@router.get(
    "/{company_name}",
    response_model=CompanyOverviewResponse,
)
async def get_company_overview(
    company_name: str,
    session: AsyncSession = Depends(get_db),
):
    """기업명으로 특허(+행정이력)와 수집 파이프라인 결과를 함께 조회합니다."""
    service = CompanyService(session)

    try:
        return await service.get_company_overview(company_name)
    except CompanyNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AmbiguousCompanyNameError as error:
        # 후보 목록을 detail 에 그대로 실어 호출자가 corp_code 를 특정할 근거를 준다.
        raise HTTPException(
            status_code=400,
            detail={"message": str(error), "candidates": error.candidates},
        ) from error
    except ExternalAPIError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
