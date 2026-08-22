"""CompanyService 의 특허/파이프라인 신규 메서드를 테스트한다.

kipris_api / corp_search / pipeline 의 실제 네트워크 호출은 전부 monkeypatch 로
대체한다. CompanyService 는 이 테스트 범위의 메서드들에서 DB 세션을 쓰지 않으므로
session 자리에는 None 을 넘긴다.
"""
import json

import pytest

from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)
from app.domain.company.service import CompanyService


def _patents_json(patent_infos) -> str:
    """kipris_api.get_company_by_company_name() 이 돌려주는 형태의 JSON 문자열을 만든다."""
    return json.dumps(
        {"response": {"body": {"items": {"PatentUtilityInfo": patent_infos}}}},
        ensure_ascii=False,
    )


def _empty_patents_json() -> str:
    return json.dumps({"response": {"body": {"items": {}}}}, ensure_ascii=False)


def _history_json(history_infos) -> str:
    """kipris_api.get_company_by_application_number() 이 돌려주는 형태의 JSON 문자열을 만든다."""
    return json.dumps(
        {"response": {"body": {"items": {"RelatedDocsonfileInfo": history_infos}}}},
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_get_company_patents_는_kipris_호출_실패시_ExternalAPIError를_올린다(monkeypatch):
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_company_name",
        lambda company_name: None,
    )

    service = CompanyService(None)

    with pytest.raises(ExternalAPIError):
        await service.get_company_patents("없는회사")


@pytest.mark.asyncio
async def test_get_company_patents_는_특허가_없으면_빈_목록을_반환한다(monkeypatch):
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_company_name",
        lambda company_name: _empty_patents_json(),
    )

    service = CompanyService(None)

    result = await service.get_company_patents("특허없는회사")

    assert result == {"count": 0, "items": []}


@pytest.mark.asyncio
async def test_get_company_patents_는_특허마다_행정이력을_붙인다(monkeypatch):
    patent = {
        "ApplicationNumber": "1020200012345",
        "InventionName": "테스트 발명",
        "Applicant": "핀샷",
        "ApplicationDate": "20200101",
        "RegistrationStatus": "등록",
    }
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_company_name",
        lambda company_name: _patents_json(patent),
    )
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_application_number",
        lambda app_number: _history_json(
            {"DocumentName": "출원서", "ReceiptDate": "20200101", "DocumentStatus": "접수"}
        ),
    )

    service = CompanyService(None)

    result = await service.get_company_patents("핀샷")

    assert result["count"] == 1
    item = result["items"][0]
    assert item["application_number"] == "1020200012345"
    assert item["invention_name"] == "테스트 발명"
    assert item["administrative_history"] == [
        {"DocumentName": "출원서", "ReceiptDate": "20200101", "DocumentStatus": "접수"}
    ]


@pytest.mark.asyncio
async def test_get_company_patents_는_행정이력_조회가_실패해도_나머지를_계속한다(monkeypatch):
    patent = {
        "ApplicationNumber": "1020200012345",
        "InventionName": "테스트 발명",
        "Applicant": "핀샷",
        "ApplicationDate": "20200101",
        "RegistrationStatus": "등록",
    }
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_company_name",
        lambda company_name: _patents_json(patent),
    )
    monkeypatch.setattr(
        "app.domain.company.service.get_company_by_application_number",
        lambda app_number: None,
    )

    service = CompanyService(None)

    result = await service.get_company_patents("핀샷")

    assert result["count"] == 1
    assert result["items"][0]["administrative_history"] is None


@pytest.mark.asyncio
async def test_run_company_pipeline_은_매칭이_없으면_CompanyNotFoundError를_올린다(monkeypatch):
    async def fake_search_by_name(company_name):
        return []

    monkeypatch.setattr("app.domain.company.service.search_by_name", fake_search_by_name)

    service = CompanyService(None)

    with pytest.raises(CompanyNotFoundError):
        await service.run_company_pipeline("없는회사")


@pytest.mark.asyncio
async def test_run_company_pipeline_은_동명다건이면_AmbiguousCompanyNameError를_올린다(monkeypatch):
    matches = [
        {"corp_code": "001", "corp_name": "삼성전자", "stock_code": "005930", "modify_date": "20230101"},
        {"corp_code": "002", "corp_name": "삼성전자서비스", "stock_code": "", "modify_date": "20230101"},
    ]

    async def fake_search_by_name(company_name):
        return matches

    monkeypatch.setattr("app.domain.company.service.search_by_name", fake_search_by_name)

    service = CompanyService(None)

    with pytest.raises(AmbiguousCompanyNameError) as exc_info:
        await service.run_company_pipeline("삼성")

    assert exc_info.value.candidates == matches


@pytest.mark.asyncio
async def test_run_company_pipeline_은_1건_매칭시_collect_결과를_그대로_반환한다(monkeypatch):
    async def fake_search_by_name(company_name):
        return [
            {"corp_code": "01836952", "corp_name": "핀샷", "stock_code": "", "modify_date": "20230101"}
        ]

    def fake_collect(corp_code, on_progress=None):
        assert corp_code == "01836952"
        return {"corp_code": corp_code, "company": {"corp_name": "핀샷"}}

    monkeypatch.setattr("app.domain.company.service.search_by_name", fake_search_by_name)
    monkeypatch.setattr("app.domain.company.service.collect", fake_collect)

    service = CompanyService(None)

    result = await service.run_company_pipeline("핀샷")

    assert result == {"corp_code": "01836952", "company": {"corp_name": "핀샷"}}


@pytest.mark.asyncio
async def test_run_company_pipeline_은_collect_실패시_ExternalAPIError로_감싼다(monkeypatch):
    async def fake_search_by_name(company_name):
        return [
            {"corp_code": "01836952", "corp_name": "핀샷", "stock_code": "", "modify_date": "20230101"}
        ]

    def fake_collect(corp_code, on_progress=None):
        raise ValueError("DART 기업개황 조회 실패")

    monkeypatch.setattr("app.domain.company.service.search_by_name", fake_search_by_name)
    monkeypatch.setattr("app.domain.company.service.collect", fake_collect)

    service = CompanyService(None)

    with pytest.raises(ExternalAPIError):
        await service.run_company_pipeline("핀샷")
