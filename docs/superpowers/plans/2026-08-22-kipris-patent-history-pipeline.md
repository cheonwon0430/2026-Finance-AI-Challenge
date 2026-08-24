# KIPRIS 특허 리스트 + 행정처리 이력 조합 로직 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기업명 하나를 입력받아 KIPRIS 특허 리스트(API 1)를 조회하고, 리스트의 각 특허마다 행정처리 이력(API 6)을 조회해 특허별로 묶은 결과를 반환하는 순수 조합 함수를 만든다.

**Architecture:** 새 파일 `app/domain/company/kipris_pipeline.py`에 파싱 헬퍼(`_extract_items`, `_public_fields`) + 두 단계 fetch 헬퍼(`_fetch_patents`, `_fetch_administrative_history`) + 오케스트레이터(`collect_patents_with_history`)를 순서대로 쌓는다. 기존 `api/kipris_api.py`의 두 함수는 블랙박스로 호출만 하고 수정하지 않는다. DB 저장은 하지 않고, 이미 있는 `PatentSearchResult`/`PatentAdministrativeHistory` 모델의 `from_kipris_json()` 정규화 로직만 재사용해 plain dict로 변환한다.

**Tech Stack:** Python 3.13, pytest (`uv run pytest`), 표준 라이브러리 `json`만 사용. 기존 `app.infrastructure.database.patent` 모델 재사용.

## Global Constraints

- DB에 저장하지 않는다 (세션 add/commit 없음) — 스펙에서 사용자가 명시적으로 선택.
- `api/kipris_api.py`는 수정하지 않는다 — API 6 URL 수정은 사용자가 별도 진행.
- 라우터/서비스 레이어에 노출하지 않는다 — 이번 스코프는 순수 함수까지만.
- 호출은 순차(sync)로 진행한다 — 기존 `dart_api.py`/`nts_api.py`와 일관성 유지.
- 1단계(특허 리스트 조회) 실패는 예외로 전파, 4단계(개별 특허 행정처리 이력 조회) 실패는 해당 특허만 `history_error`로 격리하고 나머지는 계속 진행한다.
- 테스트는 네트워크를 타지 않는다 (`tests/test_document_clean.py`와 동일한 관례) — `monkeypatch`로 `get_company_by_company_name`/`get_company_by_application_number`를 대체한다.

---

### Task 1: `_extract_items` — KIPRIS 응답 JSON에서 아이템 리스트 추출

**Files:**
- Create: `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`
- Test: `biz-lantern/apps/backend/tests/test_kipris_pipeline.py`

**Interfaces:**
- Produces: `_extract_items(json_data: str) -> list[dict]` — `response.body.items.item` 경로에서 아이템을 뽑아 항상 `list[dict]`로 반환한다 (0건이면 빈 리스트, 1건이면 dict 하나짜리 리스트, 여러 건이면 그대로 리스트).

- [ ] **Step 1: 테스트 파일을 만들고 실패하는 테스트 3개를 작성**

`biz-lantern/apps/backend/tests/test_kipris_pipeline.py` 새로 생성:

```python
"""kipris_pipeline 조합 로직 테스트. 네트워크를 타지 않는다."""
import json

import pytest

from app.domain.company import kipris_pipeline


def _response_json(items) -> str:
    return json.dumps({"response": {"body": {"items": {"item": items}}}}, ensure_ascii=False)


def test_아이템이_1건이면_dict_하나짜리_리스트로_통일된다():
    payload = _response_json({"applicationNumber": "10-2024-0012345"})
    assert kipris_pipeline._extract_items(payload) == [{"applicationNumber": "10-2024-0012345"}]


def test_아이템이_여러건이면_리스트_그대로_반환된다():
    items = [
        {"applicationNumber": "10-2024-0012345"},
        {"applicationNumber": "10-2024-0078912"},
    ]
    payload = _response_json(items)
    assert kipris_pipeline._extract_items(payload) == items


def test_items가_없으면_빈_리스트를_반환한다():
    payload = json.dumps({"response": {"body": {"items": None}}}, ensure_ascii=False)
    assert kipris_pipeline._extract_items(payload) == []
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v` (작업 디렉터리: `biz-lantern/apps/backend`)
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.company.kipris_pipeline'`

- [ ] **Step 3: `kipris_pipeline.py`를 만들고 `_extract_items` 구현**

`biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py` 새로 생성:

```python
"""기업명 하나로 KIPRIS 특허 리스트(API 1)와 특허별 행정처리 이력(API 6)을
엮는 조합 로직.

api/kipris_api.py 는 건드리지 않는다. 이미 있는 두 함수가 돌려주는 JSON
문자열을 받아 여기서 파싱하고 조합하기만 한다. DB 저장은 하지 않는다 -
infrastructure/database/patent.py 의 from_kipris_json() 정규화 로직만
재사용해 plain dict 로 변환한다.
"""
import json


def _extract_items(json_data: str) -> list[dict]:
    """response.body.items.item 경로에서 아이템을 뽑아 항상 list[dict]로 통일한다.

    xmltodict 특성상 결과가 1건이면 dict, 여러 건이면 list, 0건이면 None/누락으로
    온다.
    """
    data = json.loads(json_data)
    items = ((data.get("response") or {}).get("body") or {}).get("items") or {}
    item = items.get("item")

    if item is None:
        return []
    if isinstance(item, dict):
        return [item]

    return item
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py biz-lantern/apps/backend/tests/test_kipris_pipeline.py
git commit -m "feat: KIPRIS 응답에서 아이템 리스트를 추출하는 _extract_items 추가"
```

---

### Task 2: `_public_fields` — ORM 인스턴스를 DB 전용 필드 없이 plain dict로 변환

**Files:**
- Modify: `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`
- Test: `biz-lantern/apps/backend/tests/test_kipris_pipeline.py`

**Interfaces:**
- Consumes: `app.infrastructure.database.patent.PatentSearchResult`, `PatentAdministrativeHistory` (기존 모델, 컬럼은 spec 문서에 나열된 그대로 — `id`/`created_at`/`updated_at` 포함해 SQLAlchemy `Base`가 정의한 컬럼 전체를 `__table__.columns`로 순회 가능)
- Produces: `_public_fields(instance) -> dict` — `id`, `created_at`, `updated_at`을 제외한 모든 컬럼을 `{컬럼명: 값}`으로 반환한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_kipris_pipeline.py`에 추가:

```python
from datetime import date

from app.infrastructure.database.patent import (
    PatentAdministrativeHistory,
    PatentSearchResult,
)


def test_public_fields는_id와_타임스탬프를_제외한다():
    patent = PatentSearchResult(
        application_number="10-2024-0012345",
        applicant_name="삼성전자",
        application_date=date(2024, 2, 15),
        invention_title="결제 이상거래 탐지 시스템",
    )
    fields = kipris_pipeline._public_fields(patent)

    assert "id" not in fields
    assert "created_at" not in fields
    assert "updated_at" not in fields
    assert fields["application_number"] == "10-2024-0012345"
    assert fields["applicant_name"] == "삼성전자"
    assert fields["invention_title"] == "결제 이상거래 탐지 시스템"


def test_public_fields는_행정처리_이력_모델에도_동작한다():
    history = PatentAdministrativeHistory(
        application_number="10-2024-0012345",
        document_number="1-1-2024-1234567",
        status="등록결정",
        step="심사",
    )
    fields = kipris_pipeline._public_fields(history)

    assert "id" not in fields
    assert fields["document_number"] == "1-1-2024-1234567"
    assert fields["status"] == "등록결정"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v -k public_fields`
Expected: FAIL — `AttributeError: module 'app.domain.company.kipris_pipeline' has no attribute '_public_fields'`

- [ ] **Step 3: `_public_fields` 구현**

`kipris_pipeline.py`에 `_extract_items` 아래에 추가:

```python
_DB_ONLY_COLUMNS = {"id", "created_at", "updated_at"}


def _public_fields(instance) -> dict:
    """ORM 인스턴스에서 id/created_at/updated_at 을 뺀 컬럼만 plain dict로 뽑는다.

    DB 세션 없이도 쓸 수 있어야 하므로 인스턴스를 만들기만 하고 저장은 하지 않는다.
    """
    return {
        column.name: getattr(instance, column.name)
        for column in instance.__table__.columns
        if column.name not in _DB_ONLY_COLUMNS
    }
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py biz-lantern/apps/backend/tests/test_kipris_pipeline.py
git commit -m "feat: ORM 인스턴스를 DB 전용 필드 없이 dict로 변환하는 _public_fields 추가"
```

---

### Task 3: `_fetch_patents` — 기업명으로 특허 리스트 조회 + 정규화

**Files:**
- Modify: `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`
- Test: `biz-lantern/apps/backend/tests/test_kipris_pipeline.py`

**Interfaces:**
- Consumes: `app.domain.company.api.kipris_api.get_company_by_company_name(company: str) -> str` (기존 함수, JSON 문자열 반환), `_extract_items`, `_public_fields`, `PatentSearchResult.from_kipris_json(data: dict)` (기존 클래스메서드)
- Produces: `_fetch_patents(company: str) -> list[dict]` — 특허 하나당 `_public_fields(PatentSearchResult 인스턴스)` 형태의 dict. 검색 결과 0건이면 빈 리스트.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_kipris_pipeline.py`에 추가:

```python
def _patent_item(application_number="10-2024-0012345", title="결제 이상거래 탐지 시스템") -> dict:
    return {
        "indexNo": "1",
        "inventionTitle": title,
        "applicantName": "삼성전자",
        "applicationNumber": application_number,
        "applicationDate": "2024/02/15",
        "astrtCont": "요약",
        "bigDrawing": None,
        "drawing": None,
        "ipcNumber": "G06Q 20/40",
        "openDate": None,
        "openNumber": None,
        "publicationDate": None,
        "publicationNumber": None,
        "registerDate": "2025/07/10",
        "registerNumber": "10-2678901",
        "registerStatus": "등록",
    }


def test_fetch_patents는_API1_응답을_정규화된_dict_리스트로_반환한다(monkeypatch):
    payload = _response_json(_patent_item())
    monkeypatch.setattr(
        kipris_pipeline, "get_company_by_company_name", lambda company: payload
    )

    result = kipris_pipeline._fetch_patents("삼성전자")

    assert len(result) == 1
    assert result[0]["application_number"] == "10-2024-0012345"
    assert result[0]["invention_title"] == "결제 이상거래 탐지 시스템"
    assert result[0]["register_status"] == "등록"
    assert "id" not in result[0]


def test_fetch_patents는_검색결과_0건이면_빈_리스트를_반환한다(monkeypatch):
    payload = json.dumps({"response": {"body": {"items": None}}}, ensure_ascii=False)
    monkeypatch.setattr(
        kipris_pipeline, "get_company_by_company_name", lambda company: payload
    )

    assert kipris_pipeline._fetch_patents("존재하지않는기업") == []
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v -k fetch_patents`
Expected: FAIL — `AttributeError: module 'app.domain.company.kipris_pipeline' has no attribute '_fetch_patents'`

- [ ] **Step 3: `_fetch_patents` 구현**

`kipris_pipeline.py` 상단 import를 다음으로 교체:

```python
import json

from app.domain.company.api.kipris_api import (
    get_company_by_application_number,
    get_company_by_company_name,
)
from app.infrastructure.database.patent import (
    PatentAdministrativeHistory,
    PatentSearchResult,
)
```

`_public_fields` 아래에 추가:

```python
def _fetch_patents(company: str) -> list[dict]:
    """기업명으로 특허 리스트(API 1)를 조회해 정규화된 dict 리스트로 돌려준다.

    검색 결과가 0건이면 빈 리스트 - 기업에 특허가 없을 수 있으므로 오류가 아니다.
    """
    payload = get_company_by_company_name(company)
    items = _extract_items(payload)

    return [_public_fields(PatentSearchResult.from_kipris_json(item)) for item in items]
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py biz-lantern/apps/backend/tests/test_kipris_pipeline.py
git commit -m "feat: 기업명으로 특허 리스트를 조회/정규화하는 _fetch_patents 추가"
```

---

### Task 4: `_fetch_administrative_history` — 출원번호로 행정처리 이력 조회 + 정규화

**Files:**
- Modify: `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`
- Test: `biz-lantern/apps/backend/tests/test_kipris_pipeline.py`

**Interfaces:**
- Consumes: `app.domain.company.api.kipris_api.get_company_by_application_number(app_number: str) -> str` (기존 함수), `_extract_items`, `_public_fields`, `PatentAdministrativeHistory.from_kipris_json(data: dict)` (기존 클래스메서드)
- Produces: `_fetch_administrative_history(application_number: str) -> list[dict]` — 문서 하나당 `_public_fields(PatentAdministrativeHistory 인스턴스)` 형태의 dict. 실패 시 예외를 그대로 올린다 (여기서 삼키지 않음 — 실패 격리는 Task 5의 오케스트레이터 책임).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_kipris_pipeline.py`에 추가:

```python
def _history_item(document_number="1-1-2024-1234567") -> dict:
    return {
        "applicationNumber": "10-2024-0012345",
        "documentNumber": document_number,
        "documentDate": "20240315",
        "documentTitle": "출원서",
        "documentTitleEng": "Application",
        "status": "출원",
        "statusEng": "Filed",
        "step": "출원",
        "trialNumber": None,
        "registrationNumber": None,
    }


def test_fetch_administrative_history는_API6_응답을_정규화된_dict_리스트로_반환한다(monkeypatch):
    payload = _response_json(_history_item())
    monkeypatch.setattr(
        kipris_pipeline,
        "get_company_by_application_number",
        lambda application_number: payload,
    )

    result = kipris_pipeline._fetch_administrative_history("10-2024-0012345")

    assert len(result) == 1
    assert result[0]["document_number"] == "1-1-2024-1234567"
    assert result[0]["status"] == "출원"
    assert "id" not in result[0]


def test_fetch_administrative_history는_여러건이면_전부_반환한다(monkeypatch):
    items = [_history_item("1-1-2024-1234567"), _history_item("1-1-2024-7654321")]
    payload = _response_json(items)
    monkeypatch.setattr(
        kipris_pipeline,
        "get_company_by_application_number",
        lambda application_number: payload,
    )

    result = kipris_pipeline._fetch_administrative_history("10-2024-0012345")

    assert [item["document_number"] for item in result] == [
        "1-1-2024-1234567",
        "1-1-2024-7654321",
    ]


def test_fetch_administrative_history는_실패시_예외를_그대로_올린다(monkeypatch):
    def _boom(application_number):
        raise ValueError("KIPRIS 서버 오류")

    monkeypatch.setattr(kipris_pipeline, "get_company_by_application_number", _boom)

    with pytest.raises(ValueError, match="KIPRIS 서버 오류"):
        kipris_pipeline._fetch_administrative_history("10-2024-0012345")
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v -k fetch_administrative_history`
Expected: FAIL — `AttributeError: module 'app.domain.company.kipris_pipeline' has no attribute '_fetch_administrative_history'`

- [ ] **Step 3: `_fetch_administrative_history` 구현**

`kipris_pipeline.py`에 `_fetch_patents` 아래에 추가:

```python
def _fetch_administrative_history(application_number: str) -> list[dict]:
    """출원번호로 행정처리 이력(API 6)을 조회해 정규화된 dict 리스트로 돌려준다.

    실패해도 여기서 삼키지 않고 그대로 올린다 - 실패를 특허 단위로 격리해
    나머지 특허는 계속 처리하는 건 호출하는 쪽(collect_patents_with_history)의 책임이다.
    """
    payload = get_company_by_application_number(application_number)
    items = _extract_items(payload)

    return [
        _public_fields(PatentAdministrativeHistory.from_kipris_json(item)) for item in items
    ]
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py biz-lantern/apps/backend/tests/test_kipris_pipeline.py
git commit -m "feat: 출원번호로 행정처리 이력을 조회/정규화하는 _fetch_administrative_history 추가"
```

---

### Task 5: `collect_patents_with_history` — 오케스트레이터 + CLI 진입점

**Files:**
- Modify: `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`
- Test: `biz-lantern/apps/backend/tests/test_kipris_pipeline.py`

**Interfaces:**
- Consumes: `_fetch_patents`, `_fetch_administrative_history`
- Produces: `collect_patents_with_history(company: str) -> list[dict]` — 특허 1건당 `{"patent": {...}, "administrative_history": [...], "history_error": str | None}`. 1단계 실패는 예외 전파, 4단계 실패는 해당 특허만 격리.

- [ ] **Step 1: 실패하는 테스트 3개 작성**

`tests/test_kipris_pipeline.py`에 추가:

```python
def test_collect_patents_with_history는_특허마다_이력을_묶는다(monkeypatch):
    patents_payload = _response_json(
        [_patent_item("10-2024-0012345"), _patent_item("10-2024-0078912")]
    )
    monkeypatch.setattr(
        kipris_pipeline, "get_company_by_company_name", lambda company: patents_payload
    )
    monkeypatch.setattr(
        kipris_pipeline,
        "get_company_by_application_number",
        lambda application_number: _response_json(_history_item()),
    )

    result = kipris_pipeline.collect_patents_with_history("삼성전자")

    assert len(result) == 2
    assert result[0]["patent"]["application_number"] == "10-2024-0012345"
    assert result[0]["administrative_history"][0]["document_number"] == "1-1-2024-1234567"
    assert result[0]["history_error"] is None


def test_collect_patents_with_history는_1단계_실패시_예외를_전파한다(monkeypatch):
    def _boom(company):
        raise ValueError("KIPRIS 서버 오류")

    monkeypatch.setattr(kipris_pipeline, "get_company_by_company_name", _boom)

    with pytest.raises(ValueError, match="KIPRIS 서버 오류"):
        kipris_pipeline.collect_patents_with_history("삼성전자")


def test_collect_patents_with_history는_일부_특허_이력조회_실패해도_나머지는_계속한다(monkeypatch):
    patents_payload = _response_json(
        [_patent_item("10-2024-0012345"), _patent_item("10-2024-0078912")]
    )
    monkeypatch.setattr(
        kipris_pipeline, "get_company_by_company_name", lambda company: patents_payload
    )

    def _history(application_number):
        if application_number == "10-2024-0012345":
            raise ValueError("KIPRIS 서버 오류")
        return _response_json(_history_item())

    monkeypatch.setattr(kipris_pipeline, "get_company_by_application_number", _history)

    result = kipris_pipeline.collect_patents_with_history("삼성전자")

    assert result[0]["administrative_history"] == []
    assert "KIPRIS 서버 오류" in result[0]["history_error"]
    assert result[1]["administrative_history"][0]["document_number"] == "1-1-2024-1234567"
    assert result[1]["history_error"] is None
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v -k collect_patents_with_history`
Expected: FAIL — `AttributeError: module 'app.domain.company.kipris_pipeline' has no attribute 'collect_patents_with_history'`

- [ ] **Step 3: `collect_patents_with_history` + CLI 구현**

`kipris_pipeline.py`에 `_fetch_administrative_history` 아래에 추가:

```python
def collect_patents_with_history(company: str) -> list[dict]:
    """기업명 하나로 특허 리스트와 특허별 행정처리 이력을 묶어 돌려준다.

    특허 리스트 조회(1단계)가 실패하면 그대로 예외를 올린다 - 이게 없으면 이후
    단계가 성립하지 않는다. 반대로 개별 특허의 행정처리 이력 조회(4단계)가
    실패해도 전체를 중단하지 않는다 - 특허 10건 중 1건이 실패했다고 나머지
    9건까지 못 받는 일은 없어야 한다.
    """
    reports = []

    for patent in _fetch_patents(company):
        try:
            history = _fetch_administrative_history(patent["application_number"])
            history_error = None
        except Exception as error:  # noqa: BLE001 - 어떤 실패든 이 특허만 격리하고 계속한다
            history = []
            history_error = f"{type(error).__name__}: {error}"

        reports.append(
            {
                "patent": patent,
                "administrative_history": history,
                "history_error": history_error,
            }
        )

    return reports


if __name__ == "__main__":
    import sys

    target_company = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    reports = collect_patents_with_history(target_company)
    print(json.dumps(reports, ensure_ascii=False, indent=2, default=str))
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `uv run pytest tests/test_kipris_pipeline.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: 전체 테스트 스위트 실행해서 회귀 없는지 확인**

Run: `uv run pytest -q`
Expected: 모든 테스트 PASS (기존 `test_document_clean.py` 70개 + 새 `test_kipris_pipeline.py` 13개 = 83 passed)

- [ ] **Step 6: Commit**

```bash
git add biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py biz-lantern/apps/backend/tests/test_kipris_pipeline.py
git commit -m "feat: 특허 리스트와 행정처리 이력을 묶는 collect_patents_with_history + CLI 추가"
```

---

## Self-Review 결과

- **스펙 커버리지:** 스펙의 6단계 핵심 흐름(1단계 리스트 조회 → 2단계 파싱 → 3단계 정규화 → 4단계 이력 조회 → 5단계 정규화 → 6단계 묶기)을 Task 1~5가 각각 `_extract_items`(2단계) → `_public_fields`+`_fetch_patents`(3단계) → `_fetch_administrative_history`(4~5단계) → `collect_patents_with_history`(6단계 + 조립)로 커버함. 에러 처리(1단계 전파/4단계 격리)는 Task 5에서 테스트로 검증. CLI 진입점은 Task 5 Step 3에 포함. DB 미저장·라우터 미노출·`api/` 미수정은 Global Constraints로 명시하고 어떤 태스크도 그 경계를 넘지 않음.
- **플레이스홀더 스캔:** "TBD"/"나중에"/"적절한 에러 처리" 같은 표현 없음. 모든 스텝에 실행 가능한 실제 코드가 있음.
- **타입 일관성:** `_extract_items(json_data: str) -> list[dict]`, `_public_fields(instance) -> dict`, `_fetch_patents(company: str) -> list[dict]`, `_fetch_administrative_history(application_number: str) -> list[dict]`, `collect_patents_with_history(company: str) -> list[dict]` — 태스크 전체에서 함수명·시그니처가 일관됨. `patent["application_number"]` 키 이름은 `_public_fields`가 SQLAlchemy 컬럼명(snake_case)을 그대로 쓰므로 `PatentSearchResult.application_number`와 일치.
