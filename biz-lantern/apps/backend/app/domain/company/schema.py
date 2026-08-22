from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    industry: str


class CompanyResponse(BaseModel):
    id: int
    name: str
    industry: str

    model_config = {
        "from_attributes": True,
    }


class CompanyOverviewResponse(BaseModel):
    """GET /companies/{company_name} 의 응답 형태.

    patents/pipeline 내부는 KIPRIS/DART 원천 데이터라 동적 구조다. 필드를
    엄격하게 고정하는 대신 dict 로 둔다.
    """

    company_name: str
    patents: dict
    pipeline: dict