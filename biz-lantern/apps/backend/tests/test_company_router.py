"""GET /api/v1/companies/{company_name} 엔드포인트 테스트.

CompanyService.get_company_overview 를 monkeypatch 로 대체해 실제 외부 API를
타지 않는다. DB 세션도 get_db 오버라이드로 대체한다(이 엔드포인트는 DB 를
쓰지 않는다).
"""
import pytest
from fastapi.testclient import TestClient

from app.domain.company import service as company_service_module
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)
from app.infrastructure.database.session import get_db
from app.main import app


async def _fake_get_db():
    yield None


app.dependency_overrides[get_db] = _fake_get_db

client = TestClient(app)


def test_get_company_overview_성공(monkeypatch):
    async def fake_get_company_overview(self, company_name):
        return {
            "company_name": company_name,
            "patents": {"count": 0, "items": []},
            "pipeline": {"corp_code": "01836952"},
        }

    monkeypatch.setattr(
        company_service_module.CompanyService,
        "get_company_overview",
        fake_get_company_overview,
    )

    response = client.get("/api/v1/companies/핀샷")

    assert response.status_code == 200
    assert response.json() == {
        "company_name": "핀샷",
        "patents": {"count": 0, "items": []},
        "pipeline": {"corp_code": "01836952"},
    }


def test_get_company_overview_는_기업이_없으면_404(monkeypatch):
    async def fake_get_company_overview(self, company_name):
        raise CompanyNotFoundError(f"'{company_name}' 에 매칭되는 기업이 없습니다.")

    monkeypatch.setattr(
        company_service_module.CompanyService,
        "get_company_overview",
        fake_get_company_overview,
    )

    response = client.get("/api/v1/companies/없는회사")

    assert response.status_code == 404


def test_get_company_overview_는_동명다건이면_400과_후보목록을_반환한다(monkeypatch):
    candidates = [
        {"corp_code": "001", "corp_name": "삼성전자", "stock_code": "005930", "modify_date": "20230101"},
    ]

    async def fake_get_company_overview(self, company_name):
        raise AmbiguousCompanyNameError(company_name, candidates)

    monkeypatch.setattr(
        company_service_module.CompanyService,
        "get_company_overview",
        fake_get_company_overview,
    )

    response = client.get("/api/v1/companies/삼성")

    assert response.status_code == 400
    assert response.json()["detail"]["candidates"] == candidates


def test_get_company_overview_는_외부_api_실패시_502(monkeypatch):
    async def fake_get_company_overview(self, company_name):
        raise ExternalAPIError("KIPRIS 특허 조회 실패")

    monkeypatch.setattr(
        company_service_module.CompanyService,
        "get_company_overview",
        fake_get_company_overview,
    )

    response = client.get("/api/v1/companies/에러회사")

    assert response.status_code == 502


def test_company_id_라우트는_더_이상_없고_숫자도_company_name으로_처리된다(monkeypatch):
    """GET /{company_id} 를 제거했으므로, 숫자로만 된 경로도 이제

    get_company_overview(company_name="999999") 로 들어간다(기존처럼 DB
    company_id 조회로 취급되지 않는다). 라우트가 실제로 지워졌는지 확인한다.
    """

    async def fake_get_company_overview(self, company_name):
        assert company_name == "999999"
        return {"company_name": company_name, "patents": {"count": 0, "items": []}, "pipeline": {}}

    monkeypatch.setattr(
        company_service_module.CompanyService,
        "get_company_overview",
        fake_get_company_overview,
    )

    response = client.get("/api/v1/companies/999999")

    assert response.status_code == 200
    assert response.json()["company_name"] == "999999"
