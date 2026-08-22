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