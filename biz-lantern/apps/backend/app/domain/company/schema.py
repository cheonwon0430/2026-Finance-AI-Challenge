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

    document_markdown 은 pipeline.paths.document_clean_md 가 가리키는, 이미
    생성돼 있는 감사보고서 정리본 마크다운 파일의 내용이다. 감사보고서가 없는
    회사거나 파일을 읽지 못하면 None 이다.
    """

    company_name: str
    patents: dict
    pipeline: dict
    document_markdown: str | None = None