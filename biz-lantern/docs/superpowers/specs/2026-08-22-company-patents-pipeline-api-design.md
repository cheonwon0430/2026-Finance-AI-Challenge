# 기업 특허 + 수집 파이프라인 통합 조회 API 설계

- 날짜: 2026-08-22
- 대상: `apps/backend/app/domain/company/`
- 엔드포인트: `GET /api/v1/companies/{company_name}`

## 배경 / 목표

기업명을 입력받아 다음 두 가지를 한 번에 조회하는 API를 추가한다.

1. KIPRIS 특허 목록 + 특허별 행정이력 (`api/kipris_api.py` 재사용)
2. DART/국세청 기반 수집 파이프라인 실행 결과 (`pipeline.py` 재사용)

Router는 얇게 유지하고(Service 메서드 한 번 호출), 비즈니스 로직과 두 원천의 조합은 전부 Service 계층에 둔다. `api/kipris_api.py`와 `pipeline.py`는 기존 구현을 그대로 재사용하며 수정하지 않는다.

## 아키텍처

```
Router.get_company_overview(company_name)
  └─ Service.get_company_overview(company_name)
        ├─ Service.get_company_patents(company_name)   → kipris_api.get_company_by_company_name / get_company_by_application_number
        └─ Service.run_company_pipeline(company_name)  → corp_search.search_by_name + pipeline.collect
```

- Router는 `CompanyService.get_company_overview()`만 호출한다. `kipris_api.py`, `pipeline.py`를 직접 import하지 않는다.
- `get_company_patents`, `run_company_pipeline`은 Service의 공개 메서드로 남겨 다른 곳에서도 재사용 가능하게 한다.
- `get_company_overview`는 위 두 메서드를 순차 호출해 결과를 하나의 dict로 조합한다. (두 외부 조회를 동시 실행(`asyncio.gather`)하는 최적화는 지금 범위에서는 불필요한 복잡도로 보고 배제한다. 필요해지면 나중에 추가한다.)

## 컴포넌트별 상세

### 1. `get_company_patents(company_name: str) -> dict`

1. `get_company_by_company_name(company_name)` 호출. 이 함수는 동기(httpx 동기 클라이언트) 함수이므로 `asyncio.to_thread`로 감싸 이벤트 루프를 막지 않는다.
2. 반환값이 `None`이면 KIPRIS 호출 자체가 실패한 것이다(`get_company_by_company_name`은 내부에서 예외를 삼키고 `None`을 암묵적으로 반환하는 기존 동작을 그대로 둔다). 이 경우 `ExternalAPIError`를 올린다.
3. 반환된 JSON 문자열을 파싱해 특허 목록을 뽑는다. 파싱 경로는 `kipris_api.py`에 주석으로 남아 있는 기존 구현(`response.body.items.PatentUtilityInfo`, 단건이면 dict/다건이면 list)을 그대로 따른다.
4. 특허가 0건이면 에러가 아니라 빈 리스트로 정상 반환한다.
5. 각 특허의 출원번호(`ApplicationNumber`)로 `get_company_by_application_number()`를 호출해 행정이력을 조회한다(각 호출도 `asyncio.to_thread`). 개별 특허의 행정이력 조회가 실패(`None` 반환)해도 전체 요청을 실패시키지 않고 해당 특허의 `administrative_history`를 `None`으로, 실패 사유를 남긴 채 계속 진행한다. `pipeline.py`가 국세청 조회 실패를 다루는 것과 동일한 부분 실패 허용 철학이다.

**리스크**: 3번의 파싱 경로는 실제 KIPRIS 응답으로 검증된 적이 없는, 코드에 주석으로만 남아있던 추정 구조다. 실제 응답 스키마가 다르면 파싱이 빈 결과로 떨어질 수 있다. 방어적으로 키가 없으면 예외 대신 빈 리스트로 처리한다.

### 2. `run_company_pipeline(company_name: str) -> dict`

1. `search_by_name(company_name)` 호출(이미 async, 그대로 await).
2. 매칭 0건 → `CompanyNotFoundError`.
3. 매칭 2건 이상 → `AmbiguousCompanyNameError`(후보 `corp_code`/`corp_name` 목록을 담는다). corp_code를 자동으로 고르지 않는다 — CLI(`_resolve_corp_code`)와 동일한 안전 철학.
4. 정확히 1건이면 `collect(corp_code)`를 `asyncio.to_thread`로 실행한다. `collect()`가 올리는 예외(치명적 실패)는 `ExternalAPIError`로 감싸 다시 올린다.

### 3. `get_company_overview(company_name: str) -> dict`

두 메서드를 순차 호출해 아래 형태로 합친다.

```json
{
  "company_name": "...",
  "patents": { "count": 0, "items": [...] },
  "pipeline": { ... pipeline.CollectResult 그대로 ... }
}
```

## 예외 처리

기존 코드베이스에는 공용 예외 클래스가 없다(grep 결과 없음). 최소한의 신규 예외 3개를 `app/domain/company/exceptions.py`에 추가한다.

- `CompanyNotFoundError` — 기업명으로 corp_code를 찾지 못함 → Router가 `HTTPException(404)`로 변환
- `AmbiguousCompanyNameError` — 동명 다건 매칭, `candidates` 속성 보유 → Router가 `HTTPException(400)`으로 변환하며 후보 목록을 detail에 포함
- `ExternalAPIError` — KIPRIS/DART 등 외부 API 호출 실패(Timeout 포함) → Router가 `HTTPException(502)`로 변환

Router는 이 세 예외만 개별 catch하고, 그 외 예외는 그대로 전파해 FastAPI 기본 500 처리에 맡긴다.

## 응답 스키마

`schema.py`에 아래 Pydantic 모델을 추가한다. KIPRIS/DART 원천 데이터는 동적 구조라 내부 필드까지 엄격하게 고정하지 않고 `dict`로 둔다.

```python
class CompanyOverviewResponse(BaseModel):
    company_name: str
    patents: dict
    pipeline: dict
```

## 코드 스타일

- 신규 메서드/함수에는 Docstring을 작성하고, 비자명한 이유(WHY)가 있는 지점에는 한글 주석을 추가한다. 기존 `pipeline.py`의 주석 스타일(무엇을 왜 이렇게 했는지 설명)을 따른다.
- 타입 힌트를 모든 신규 함수/메서드에 작성한다.

## 영향받는 파일

| 파일 | 변경 |
|---|---|
| `app/domain/company/router.py` | `GET /{company_name}` 엔드포인트 추가 |
| `app/domain/company/service.py` | `get_company_patents`, `run_company_pipeline`, `get_company_overview` 메서드 추가 |
| `app/domain/company/schema.py` | `CompanyOverviewResponse` 추가 |
| `app/domain/company/exceptions.py` (신규) | `CompanyNotFoundError`, `AmbiguousCompanyNameError`, `ExternalAPIError` |
| `app/domain/company/api/kipris_api.py` | 수정 없음 (그대로 재사용) |
| `app/domain/company/pipeline.py` | 수정 없음 (그대로 재사용) |

## 서버 실행 및 테스트 방법

프로젝트는 `uv`로 의존성을 관리한다 (`apps/backend/uv.lock` 존재, `fastapi[standard]` 포함).

```bash
cd apps/backend
uv run fastapi dev app/main.py
```

- 기본적으로 `http://127.0.0.1:8000` 에서 뜬다.
- `.env`에 `KIPRIS_API_KEY` 등 필요한 키가 설정돼 있어야 실제 외부 API 호출이 성공한다(`.env.example` 참고).
- Swagger UI: `http://127.0.0.1:8000/docs` 에서 바로 실행/응답 확인 가능.

curl로 직접 호출:

```bash
curl "http://127.0.0.1:8000/api/v1/companies/트래블월렛"
```

확인할 시나리오:

- 정상 케이스: DART corpcode에 1건만 매칭되고 KIPRIS 특허가 있는 회사명 → `200`, `patents`/`pipeline` 모두 채워짐
- 존재하지 않는 회사명 → `404`
- 동명 다건(예: `"삼성"`) → `400` + 후보 목록
- 특허가 없는 회사(정상) → `200`, `patents.items: []`
- KIPRIS 키가 잘못됐거나 외부 API가 응답하지 않을 때 → `502`

## 자기 검토 메모

- 플레이스홀더/미정 항목 없음.
- Router→Service→(kipris_api / pipeline) 계층 제약과 모순되는 부분 없음.
- 범위: 이 스펙은 이 엔드포인트 하나에 한정되며 분해가 필요할 만큼 크지 않다.
