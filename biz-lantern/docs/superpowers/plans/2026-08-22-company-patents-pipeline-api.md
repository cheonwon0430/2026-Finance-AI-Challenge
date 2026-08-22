# 기업 특허 + 수집 파이프라인 통합 조회 API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /api/v1/companies/{company_name}` 하나로 KIPRIS 특허(+행정이력)와 DART/국세청 수집 파이프라인 결과를 함께 반환하는 API를 추가한다.

**Architecture:** Router(`router.py`) → Service(`service.py`, `get_company_overview`) → 두 갈래(`get_company_patents` via `api/kipris_api.py`, `run_company_pipeline` via `api/corp_search.py` + `pipeline.py`). `kipris_api.py`/`pipeline.py`는 수정하지 않고 기존 함수를 그대로 재사용한다.

**Tech Stack:** FastAPI, Pydantic, pytest / pytest-asyncio(monkeypatch 기반 단위 테스트), `uv` (패키지 관리).

## Global Constraints

- Router는 `CompanyService`의 메서드만 호출한다. `kipris_api.py`, `pipeline.py`를 Router에서 직접 import/호출하지 않는다.
- `app/domain/company/api/kipris_api.py`, `app/domain/company/pipeline.py`는 수정하지 않는다(그대로 재사용).
- 기존 DI 방식(`Depends(get_db)` → `CompanyService(session)`)을 그대로 유지한다.
- 모든 신규 함수/메서드에 타입 힌트와 Docstring을 작성하고, 비자명한 이유(WHY)가 있는 지점에는 한글 주석을 추가한다(`pipeline.py`의 주석 스타일을 따른다).
- 사용자 결정(2026-08-22): DB의 정수 `company_id`로 조회하는 기존 `GET /companies/{company_id}` 엔드포인트는 더 이상 쓰지 않는다. 이번 작업에서 제거하고 `GET /companies/{company_name}`으로 대체한다. `POST /companies`(생성)와 `GET /companies/{company_id}/status`(휴폐업 조회)는 그대로 유지한다.
- 최종 응답은 `{"company_name": str, "patents": {...}, "pipeline": {...}}` 형태의 단일 객체다.
- 에러 처리: 기업명이 존재하지 않으면 404, 동명 다건(corp_code 여러 건 매칭)이면 400+후보목록, KIPRIS/DART 등 외부 API 호출 실패(Timeout 포함)나 파이프라인 치명적 실패는 502. 특허가 0건인 것은 에러가 아니라 정상적인 빈 결과다.

---

## 파일 구조

| 파일 | 변경 | 책임 |
|---|---|---|
| `app/domain/company/exceptions.py` | 신규 | Service가 올리는 도메인 예외 3종 |
| `app/domain/company/service.py` | 수정 | `get_company_patents`, `run_company_pipeline`, `get_company_overview` 추가, 더 이상 쓰지 않는 `get_company(company_id)` 제거 |
| `app/domain/company/repository.py` | 수정 | `get_company` 제거로 더는 쓰이지 않는 `get_by_id` 제거 |
| `app/domain/company/schema.py` | 수정 | `CompanyOverviewResponse` 추가 (`CompanyResponse`는 `POST /companies`가 계속 쓰므로 유지) |
| `app/domain/company/router.py` | 수정 | `GET /{company_id}` 제거, `GET /{company_name}` 추가 |
| `tests/test_company_exceptions.py` | 신규 | 예외 클래스 동작 테스트 |
| `tests/test_company_service.py` | 신규 | Service 신규 메서드 3종 테스트 |
| `tests/test_company_router.py` | 신규 | 엔드포인트 통합 테스트(에러 매핑 포함) |

**참고 - 라우팅 충돌이 사라짐:** 원래 설계에서는 기존 `GET /{company_id}`(타입 지정 없이 등록돼 있어 임의의 문자열 세그먼트에도 매칭됨)와 신규 `GET /{company_name}`이 같은 경로 모양이라 충돌 위험이 있었고, `/{company_id:int}`로 바꿔 회피할 계획이었다. 사용자가 `GET /{company_id}` 자체를 제거하기로 결정하면서 이 문제는 더 이상 발생하지 않는다 - 단일 세그먼트 GET 라우트가 `/{company_name}` 하나만 남는다.

---

### Task 1: Company 도메인 예외 클래스

**Files:**
- Create: `app/domain/company/exceptions.py`
- Test: `tests/test_company_exceptions.py`

**Interfaces:**
- Produces: `CompanyNotFoundError(message: str)`, `AmbiguousCompanyNameError(company_name: str, candidates: list[dict])` (인스턴스에 `.company_name`, `.candidates` 속성), `ExternalAPIError(message: str)` — 이후 Task 2/3에서 raise, Task 5(Router)에서 catch.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_company_exceptions.py`:

```python
"""app/domain/company/exceptions.py 의 예외 클래스 동작을 검증한다."""
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)


def test_ambiguous_company_name_error_는_기업명과_후보목록을_담는다():
    candidates = [
        {
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "stock_code": "005930",
            "modify_date": "20230101",
        },
        {
            "corp_code": "00164779",
            "corp_name": "삼성전자서비스",
            "stock_code": "",
            "modify_date": "20230101",
        },
    ]

    error = AmbiguousCompanyNameError("삼성", candidates)

    assert error.company_name == "삼성"
    assert error.candidates == candidates
    assert "삼성" in str(error)
    assert "2건" in str(error)


def test_company_not_found_error_는_일반_예외처럼_동작한다():
    error = CompanyNotFoundError("'없는회사' 에 매칭되는 기업이 없습니다.")

    assert isinstance(error, Exception)
    assert "없는회사" in str(error)


def test_external_api_error_는_일반_예외처럼_동작한다():
    error = ExternalAPIError("KIPRIS 특허 조회 실패: company_name=핀샷")

    assert isinstance(error, Exception)
    assert "핀샷" in str(error)
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run (in `apps/backend`): `uv run pytest tests/test_company_exceptions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.company.exceptions'`

- [ ] **Step 3: 최소 구현 작성**

`app/domain/company/exceptions.py`:

```python
"""Company 도메인 전용 예외.

Router 는 이 예외들만 각각 다른 HTTP 상태 코드로 변환한다. 그 외 예외는
그대로 전파해 FastAPI 기본 500 처리에 맡긴다.
"""


class CompanyNotFoundError(Exception):
    """기업명으로 DART corp_code 를 찾지 못했을 때."""


class AmbiguousCompanyNameError(Exception):
    """기업명이 DART corp_code 여러 건에 매칭될 때.

    corp_code 를 자동으로 고르지 않는다(엉뚱한 회사를 분석하게 될 위험이
    있어서다 - pipeline.py CLI 의 _resolve_corp_code 와 동일한 철학).
    candidates 에 후보를 그대로 담아 호출자가 참고하게 한다.
    """

    def __init__(self, company_name: str, candidates: list[dict]):
        self.company_name = company_name
        self.candidates = candidates
        super().__init__(
            f"'{company_name}' 에 매칭되는 기업이 {len(candidates)}건입니다. "
            "corp_code 로 특정해야 합니다."
        )


class ExternalAPIError(Exception):
    """KIPRIS/DART 등 외부 API 호출이 실패했을 때 (Timeout 포함).

    kipris_api.py 의 두 함수는 실패 시 예외 대신 None 을 반환하므로, 그
    None 을 이 예외로 변환해서 Router 까지 실패 신호를 전달한다.
    """
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_company_exceptions.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add app/domain/company/exceptions.py tests/test_company_exceptions.py
git commit -m "feat(company): add domain exceptions for patents/pipeline lookup"
```

---

### Task 2: Service - `get_company_patents` (KIPRIS 특허 + 행정이력)

**Files:**
- Modify: `app/domain/company/service.py`
- Test: `tests/test_company_service.py` (신규 파일, 이 Task에서 생성)

**Interfaces:**
- Consumes: `app.domain.company.api.kipris_api.get_company_by_company_name(company: str) -> str | None`, `get_company_by_application_number(app_number: str) -> str | None`(둘 다 기존 함수, 실패 시 예외 대신 None), `ExternalAPIError`(Task 1).
- Produces: `CompanyService.get_company_patents(company_name: str) -> dict` — 반환 형태 `{"count": int, "items": [{"application_number": str | None, "invention_name": str | None, "applicant": str | None, "application_date": str | None, "status": str | None, "administrative_history": list[dict] | None}, ...]}`. Task 4(`get_company_overview`)가 그대로 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_company_service.py` (신규):

```python
"""CompanyService 의 특허/파이프라인 신규 메서드를 테스트한다.

kipris_api / corp_search / pipeline 의 실제 네트워크 호출은 전부 monkeypatch 로
대체한다. CompanyService 는 이 테스트 범위의 메서드들에서 DB 세션을 쓰지 않으므로
session 자리에는 None 을 넘긴다.
"""
import json

import pytest

from app.domain.company.exceptions import ExternalAPIError
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_company_service.py -v`
Expected: FAIL — `AttributeError: 'CompanyService' object has no attribute 'get_company_patents'`

- [ ] **Step 3: 최소 구현 작성**

`app/domain/company/service.py` 상단 import 블록을 아래처럼 바꾼다(기존 `get_company_by_company_name` 임포트에 `get_company_by_application_number` 를 추가하고, `asyncio`/`json`/`logging`, 신규 예외를 더한다):

```python
import asyncio
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.company.model import Company
from app.domain.company.repository import CompanyRepository
from app.domain.company.schema import CompanyCreate
from app.domain.company.api.nts_api import (
    get_business_status as fetch_business_status,
)
from app.domain.company.api.kipris_api import (
    get_company_by_application_number,
    get_company_by_company_name,
)
from app.domain.company.exceptions import ExternalAPIError

logger = logging.getLogger(__name__)
```

`CompanyService` 클래스 안, `get_business_status` 메서드 뒤에 아래 메서드들을 추가한다:

```python
    @staticmethod
    def _parse_patent_items(raw_json: str) -> list[dict]:
        """kipris_api.get_company_by_company_name() 의 JSON 문자열에서 특허 목록을 뽑는다.

        kipris_api.py 에 주석으로 남아있던 기존 파싱 로직을 그대로 따른다. 실제
        KIPRIS 응답으로 검증된 적이 없는 추정 구조라, 예상과 다른 구조가 오면
        예외 대신 빈 리스트로 처리한다(특허 0건과 동일하게 취급 - 파싱 불확실성
        때문에 전체 조회를 실패시키지 않는다).
        """
        try:
            body = json.loads(raw_json).get("response", {}).get("body", {})
            patent_info = (body.get("items") or {}).get("PatentUtilityInfo")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("KIPRIS 특허 응답 파싱 실패 (예상 구조와 다름)")
            return []

        if not patent_info:
            return []

        # xmltodict 특성상 결과가 1건이면 dict, 여러 건이면 list 로 오므로 리스트로 통일
        if isinstance(patent_info, dict):
            patent_info = [patent_info]

        return patent_info

    @staticmethod
    def _parse_history_items(raw_json: str) -> list[dict]:
        """kipris_api.get_company_by_application_number() 의 JSON 문자열에서
        행정이력 목록을 뽑는다. 파싱 근거는 _parse_patent_items 와 동일.
        """
        try:
            body = json.loads(raw_json).get("response", {}).get("body", {})
            items = body.get("items") or {}
            history_info = items.get("RelatedDocsonfileInfo") or items.get("item")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("KIPRIS 행정이력 응답 파싱 실패 (예상 구조와 다름)")
            return []

        if not history_info:
            return []

        if isinstance(history_info, dict):
            history_info = [history_info]

        return history_info

    async def _fetch_administrative_history(self, app_number: str) -> list[dict] | None:
        """출원번호 하나의 행정이력을 조회한다.

        get_company_by_application_number 는 동기 함수라 asyncio.to_thread 로
        감싼다. 실패하면(None) 그대로 None 을 돌려주고 예외를 올리지 않는다 -
        특허 하나의 행정이력 조회 실패로 전체 특허 목록 조회를 막지 않기 위해서다.
        """
        raw = await asyncio.to_thread(get_company_by_application_number, app_number)
        if raw is None:
            return None

        return self._parse_history_items(raw)

    async def get_company_patents(self, company_name: str) -> dict:
        """기업명으로 특허 목록과 특허별 행정이력을 조회한다.

        kipris_api.py 의 두 함수를 그대로 재사용한다. 둘 다 동기(httpx 동기
        클라이언트) 함수라서 asyncio.to_thread 로 감싸 이벤트 루프를 막지 않는다.

        Args:
            company_name: 특허 출원인으로 검색할 기업명.

        Returns:
            {"count": int, "items": [{"application_number", "invention_name",
            "applicant", "application_date", "status",
            "administrative_history"}, ...]}

        Raises:
            ExternalAPIError: KIPRIS 특허 검색 자체가 실패했을 때. 특허 0건은
                에러가 아니라 정상적인 빈 결과로 취급한다.
        """
        raw = await asyncio.to_thread(get_company_by_company_name, company_name)
        if raw is None:
            raise ExternalAPIError(f"KIPRIS 특허 조회 실패: company_name={company_name}")

        items = self._parse_patent_items(raw)

        patents = []
        for item in items:
            app_number = item.get("ApplicationNumber")
            history = await self._fetch_administrative_history(app_number) if app_number else None

            patents.append(
                {
                    "application_number": app_number,
                    "invention_name": item.get("InventionName"),
                    "applicant": item.get("Applicant"),
                    "application_date": item.get("ApplicationDate"),
                    "status": item.get("RegistrationStatus"),
                    "administrative_history": history,
                }
            )

        return {"count": len(patents), "items": patents}
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_company_service.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add app/domain/company/service.py tests/test_company_service.py
git commit -m "feat(company): add CompanyService.get_company_patents"
```

---

### Task 3: Service - `run_company_pipeline` (corp_code 해석 + collect 실행)

**Files:**
- Modify: `app/domain/company/service.py`
- Modify: `tests/test_company_service.py`

**Interfaces:**
- Consumes: `app.domain.company.api.corp_search.search_by_name(keyword: str) -> list[dict]`(기존, `corp_code`/`corp_name`/`stock_code`/`modify_date` 키), `app.domain.company.pipeline.collect(corp_code: str, on_progress=None) -> CollectResult`(기존), `CompanyNotFoundError`/`AmbiguousCompanyNameError`/`ExternalAPIError`(Task 1).
- Produces: `CompanyService.run_company_pipeline(company_name: str) -> dict`(= `pipeline.CollectResult`, 즉 `dict`). Task 4가 그대로 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_company_service.py` 상단의 `from app.domain.company.exceptions import ExternalAPIError` 줄을 아래로 교체한다(Task 2 에서 만든 단일 임포트를 세 개짜리로 확장):

```python
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)
```

파일 끝에 추가:

```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_company_service.py -v -k run_company_pipeline`
Expected: FAIL — `AttributeError: 'CompanyService' object has no attribute 'run_company_pipeline'`

- [ ] **Step 3: 최소 구현 작성**

`service.py` import 블록에 두 줄 추가(Task 2에서 만든 블록 바로 아래):

```python
from app.domain.company.api.corp_search import search_by_name
from app.domain.company.pipeline import collect
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)
```

(`ExternalAPIError` 단독 임포트 줄은 이 세 개짜리 줄로 합친다.)

`get_company_patents` 메서드 뒤에 추가:

```python
    async def run_company_pipeline(self, company_name: str) -> dict:
        """기업명으로 corp_code 를 찾아 pipeline.collect() 를 실행한다.

        corp_code 를 자동으로 고르지 않는다. 정확히 1건 매칭될 때만 진행하고,
        0건/2건 이상이면 각각 CompanyNotFoundError/AmbiguousCompanyNameError 를
        올린다 - pipeline.py CLI(_resolve_corp_code)와 동일한 안전 철학이다.

        Args:
            company_name: 파이프라인을 실행할 기업명.

        Returns:
            pipeline.collect() 가 돌려주는 CollectResult(dict) 그대로.

        Raises:
            CompanyNotFoundError: 매칭되는 corp_code 가 없을 때.
            AmbiguousCompanyNameError: corp_code 가 여러 건 매칭될 때.
            ExternalAPIError: collect() 가 치명적 실패로 예외를 올렸을 때.
        """
        matches = await search_by_name(company_name)

        if not matches:
            raise CompanyNotFoundError(f"'{company_name}' 에 매칭되는 기업이 없습니다.")

        if len(matches) > 1:
            raise AmbiguousCompanyNameError(company_name, matches)

        corp_code = matches[0]["corp_code"]

        # collect() 는 동기 함수(내부에서 DART/국세청을 여러 번 순차 호출)이므로
        # asyncio.to_thread 로 감싸 이벤트 루프를 막지 않는다.
        try:
            return await asyncio.to_thread(collect, corp_code)
        except Exception as error:
            raise ExternalAPIError(
                f"파이프라인 실행 실패: corp_code={corp_code}"
            ) from error
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_company_service.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add app/domain/company/service.py tests/test_company_service.py
git commit -m "feat(company): add CompanyService.run_company_pipeline"
```

---

### Task 4: Service - `get_company_overview` (조합) + 응답 스키마

**Files:**
- Modify: `app/domain/company/service.py`
- Modify: `app/domain/company/schema.py`
- Modify: `tests/test_company_service.py`

**Interfaces:**
- Consumes: `get_company_patents`(Task 2), `run_company_pipeline`(Task 3).
- Produces: `CompanyService.get_company_overview(company_name: str) -> dict` = `{"company_name": str, "patents": dict, "pipeline": dict}`. `CompanyOverviewResponse` (Pydantic) — Task 5(Router)가 `response_model` 로 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_company_service.py` 파일 끝에 추가:

```python
@pytest.mark.asyncio
async def test_get_company_overview_는_특허와_파이프라인_결과를_합친다(monkeypatch):
    async def fake_get_company_patents(self, company_name):
        return {"count": 0, "items": []}

    async def fake_run_company_pipeline(self, company_name):
        return {"corp_code": "01836952"}

    monkeypatch.setattr(CompanyService, "get_company_patents", fake_get_company_patents)
    monkeypatch.setattr(CompanyService, "run_company_pipeline", fake_run_company_pipeline)

    service = CompanyService(None)

    result = await service.get_company_overview("핀샷")

    assert result == {
        "company_name": "핀샷",
        "patents": {"count": 0, "items": []},
        "pipeline": {"corp_code": "01836952"},
    }
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_company_service.py -v -k get_company_overview`
Expected: FAIL — `AttributeError: 'CompanyService' object has no attribute 'get_company_overview'`

- [ ] **Step 3: 최소 구현 작성**

`service.py`, `run_company_pipeline` 메서드 뒤에 추가:

```python
    async def get_company_overview(self, company_name: str) -> dict:
        """기업명 하나로 특허(+행정이력)와 수집 파이프라인 결과를 함께 조회한다.

        Router 가 호출하는 진입점. 두 조회는 서로 독립적인 외부 API 호출이라
        순차 실행한다(동시 실행은 지금 범위에서 불필요한 최적화로 보고 배제).

        Args:
            company_name: 조회할 기업명.

        Returns:
            {"company_name": str, "patents": dict, "pipeline": dict}.

        Raises:
            CompanyNotFoundError, AmbiguousCompanyNameError, ExternalAPIError:
                get_company_patents / run_company_pipeline 가 올리는 예외를
                그대로 전파한다.
        """
        patents = await self.get_company_patents(company_name)
        pipeline_result = await self.run_company_pipeline(company_name)

        return {
            "company_name": company_name,
            "patents": patents,
            "pipeline": pipeline_result,
        }
```

`schema.py` 파일 끝에 추가:

```python
class CompanyOverviewResponse(BaseModel):
    """GET /companies/{company_name} 의 응답 형태.

    patents/pipeline 내부는 KIPRIS/DART 원천 데이터라 동적 구조다. 필드를
    엄격하게 고정하는 대신 dict 로 둔다.
    """

    company_name: str
    patents: dict
    pipeline: dict
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_company_service.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add app/domain/company/service.py app/domain/company/schema.py tests/test_company_service.py
git commit -m "feat(company): add CompanyService.get_company_overview and response schema"
```

---

### Task 5: Router - 기존 `GET /{company_id}` 제거 + `GET /{company_name}` 엔드포인트 추가

**Files:**
- Modify: `app/domain/company/router.py` (`GET /{company_id}` 제거, `GET /{company_name}` 추가)
- Modify: `app/domain/company/service.py` (더 이상 쓰지 않는 `get_company(company_id)` 제거)
- Modify: `app/domain/company/repository.py` (더 이상 쓰지 않는 `get_by_id` 제거)
- Test: `tests/test_company_router.py` (신규)

**Interfaces:**
- Consumes: `CompanyService.get_company_overview`(Task 4), `CompanyOverviewResponse`(Task 4), `CompanyNotFoundError`/`AmbiguousCompanyNameError`/`ExternalAPIError`(Task 1).
- Produces: `GET /api/v1/companies/{company_name}` — 200 시 `CompanyOverviewResponse` JSON, 404/400/502 에러 매핑. `CompanyService.get_company`/`CompanyRepository.get_by_id`는 더 이상 존재하지 않는다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_company_router.py` (신규):

```python
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
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_company_router.py -v`
Expected: FAIL — 새 엔드포인트가 아직 없어 `404 Not Found`. 마지막 테스트는 기존 `GET /{company_id}` 가 아직 남아있어 `company_id: int` 파싱은 성공하지만 `get_company_overview` 가 호출되지 않아 실패한다.

- [ ] **Step 3: 최소 구현 작성**

`service.py` 에서 `get_company` 메서드를 제거한다(더 이상 쓰이지 않음):

```python
    async def get_company(
        self,
        company_id: int,
    ) -> Company | None:
        return await self.repository.get_by_id(company_id)
```

위 메서드 전체를 삭제한다. `Company` import는 여전히 `create_company`에서 타입 힌트로 쓰이므로 그대로 둔다.

`repository.py` 에서 `get_by_id` 메서드를 제거한다(더 이상 쓰이지 않음):

```python
    async def get_by_id(self, company_id: int) -> Company | None:
        result = await self.session.execute(
            select(Company).where(Company.id == company_id)
        )

        return result.scalar_one_or_none()
```

위 메서드 전체를 삭제한다. `select` import가 `create`에서도 쓰이는지 확인한다 - 쓰이지 않으면 import 도 함께 지운다(`create`는 `session.add`/`flush`/`refresh`만 쓰므로 `select` import는 삭제 대상이다).

`router.py` 상단 import 줄을 바꾼다:

```python
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
```

기존 `GET /{company_id}` 엔드포인트 전체를 삭제한다:

```python
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
```

파일 끝(`get_company_status` 뒤)에 새 엔드포인트를 추가한다:

```python
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
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_company_router.py -v`
Expected: PASS (5 passed)

전체 테스트 스위트도 함께 확인한다.

Run: `uv run pytest -v`
Expected: 기존 `tests/test_document_clean.py` 포함 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add app/domain/company/router.py app/domain/company/service.py app/domain/company/repository.py tests/test_company_router.py
git commit -m "feat(company): replace GET /companies/{company_id} with GET /companies/{company_name} overview endpoint"
```

---

### Task 6: 서버 실행 및 수동 확인 (문서화 + 스모크 테스트)

TDD 대상 코드는 Task 1~5에서 끝난다. 이 Task는 실제로 서버를 띄워 Swagger/curl 로 눈으로 확인하는 절차를 남긴다.

**Files:** 없음(코드 변경 없음, 수동 확인 절차)

- [ ] **Step 1: 의존성 동기화 및 `.env` 확인**

```bash
cd apps/backend
uv sync
```

`.env` 에 `KIPRIS_API_KEY`, `DART_API_KEY`(또는 프로젝트에서 쓰는 실제 키 이름 - `app/common/config.py` 의 `settings` 필드명을 따른다), `DATABASE_URL` 등이 채워져 있는지 `.env.example` 과 비교해 확인한다. 실제 외부 API 호출이 성공하려면 유효한 키가 필요하다.

- [ ] **Step 2: 개발 서버 실행**

```bash
uv run fastapi dev app/main.py
```

Expected: `http://127.0.0.1:8000` 에서 서버가 뜬다. 콘솔에 `Application startup complete` 가 보이면 정상이다.

- [ ] **Step 3: Swagger UI로 확인**

브라우저에서 `http://127.0.0.1:8000/docs` 접속 → `GET /api/v1/companies/{company_name}` 을 펼쳐 `Try it out` 으로 실제 기업명을 넣어 실행한다.

- [ ] **Step 4: curl로 시나리오별 확인**

정상 케이스(DART 에 정확히 1건 매칭되고 KIPRIS 특허가 있을 만한 기업명으로 교체해서 실행):

```bash
curl -i "http://127.0.0.1:8000/api/v1/companies/트래블월렛"
```
Expected: `200`, JSON body 에 `company_name`/`patents`/`pipeline` 키가 모두 존재.

존재하지 않는 기업명:

```bash
curl -i "http://127.0.0.1:8000/api/v1/companies/이런회사는없음"
```
Expected: `404`.

동명 다건(예: DART 에 "삼성"으로 여러 건 매칭됨):

```bash
curl -i "http://127.0.0.1:8000/api/v1/companies/삼성"
```
Expected: `400`, body 의 `detail.candidates` 에 후보 목록.

`GET /companies/{company_id}` 가 실제로 제거됐는지 확인(숫자를 넣어도 이제는 기업명으로 취급됨):

```bash
curl -i "http://127.0.0.1:8000/api/v1/companies/1"
```
Expected: DB id 조회가 아니라 `company_name="1"` 로 특허/파이프라인 조회가 시도된다. DART 에 매칭되는 기업이 없을 테니 보통 `404`.

- [ ] **Step 5: 자동화 테스트 스위트 전체 재확인**

```bash
uv run pytest -v
```
Expected: 전부 PASS. (Task 1~5 에서 만든 테스트 + 기존 `test_document_clean.py`)

---

## Self-Review 결과

- **스펙 커버리지**: 특허 조회(Task 2), 특허별 행정이력(Task 2), Pipeline 실행(Task 3), Router 엔드포인트(Task 5), 응답 구조 `{company_name, patents, pipeline}`(Task 4/5), 계층 제약(Router는 Service만 호출 - Task 5), 에러 처리 5종(기업명 없음/특허없음/KIPRIS 실패/Pipeline 실패/Timeout - Task 1,2,3,5), DI 유지(Task 5), 타입힌트+Docstring+주석(전 Task) 모두 특정 Task에 매핑됨. 사용자 추가 요청인 "주석 추가"와 "FastAPI 실행/테스트 방법"은 각각 전 Task의 코드 주석과 Task 6에서 다룸. 사용자가 2026-08-22 대화에서 `GET /companies/{company_id}` 를 더 이상 쓰지 않기로 결정해 Task 5 에서 해당 엔드포인트와 이제 쓰이지 않는 `CompanyService.get_company`/`CompanyRepository.get_by_id`를 함께 제거하도록 반영함(원래 계획의 `/{company_id:int}` 라우팅 충돌 회피안은 대체됨).
- **플레이스홀더 스캔**: 없음. 모든 Step 에 실제 코드/명령어 포함.
- **타입/이름 일관성**: `get_company_patents`, `run_company_pipeline`, `get_company_overview`, `_parse_patent_items`, `_parse_history_items`, `_fetch_administrative_history`, `CompanyNotFoundError`, `AmbiguousCompanyNameError(company_name, candidates)`, `ExternalAPIError`, `CompanyOverviewResponse` — Task 전체에서 동일한 이름/시그니처로 사용됨을 확인.
