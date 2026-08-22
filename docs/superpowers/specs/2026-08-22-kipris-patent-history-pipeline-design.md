# KIPRIS 특허 리스트 + 행정처리 이력 조합 로직 설계

## 배경

`biz-lantern/apps/backend/app/domain/company/api/kipris_api.py`에 KIPRIS Open API 두 개가 이미 구현돼 있다.

- **API 1** `get_company_by_company_name(company)`: 출원인(기업명)으로 특허/실용신안을 검색해 서지정보·등록 상태를 조회하는 API. XML 응답을 `xmltodict`로 dict 변환 후 `json.dumps`한 문자열을 그대로 반환한다 (파싱 미완성).
- **API 6** `get_company_by_application_number(app_number)`: 출원번호 하나로 심사·행정처리 이력을 조회하는 API. 현재는 API 1과 동일한 URL(`freeSearchInfo`)을 쓰고 있어 실제로는 잘못된 엔드포인트다. **이 URL/파라미터 수정은 사용자가 직접 진행한다 — 이 스펙 범위에 포함하지 않는다.**

`biz-lantern/apps/backend/app/infrastructure/database/patent.py`에는 이 두 API의 응답을 저장하기 위한 SQLAlchemy 모델이 이미 정의돼 있다.

- `PatentSearchResult`: API 1 결과 캐시. `from_kipris_json(data: dict)` 클래스메서드가 `applicationNumber`, `inventionTitle`, `applicantName`, `applicationDate` 등 camelCase 필드를 읽어 날짜 파싱(`/` 구분자)과 `N/A` 정규화까지 처리한다.
- `PatentAdministrativeHistory`: API 6 결과 캐시. `from_kipris_json(data: dict)`가 `documentNumber`, `documentDate`(compact 날짜), `status`, `step`, `trialNumber`, `registrationNumber` 등을 정규화한다.

두 모델의 필드명이 이미 실제 KIPRIS 응답 필드명에 맞춰져 있으므로, 이 정규화 로직을 그대로 재사용한다.

이번 작업의 목표: **기업명 하나를 입력받아, (1) 그 기업의 특허 리스트를 조회하고, (2) 리스트의 특허마다 행정처리 이력을 조회해, 특허별로 묶은 결과를 반환하는 조합 로직**을 만든다.

## 범위

- **포함**: 기업명 → 특허 리스트 → 특허별 행정처리 이력을 엮는 순수 조합 함수. 테스트 실행을 위한 CLI(`__main__`) 진입점.
- **제외**:
  - DB 저장(사용자가 명시적으로 "핵심 로직 함수만, DB 저장 없이"를 선택함). `PatentSearchResult`/`PatentAdministrativeHistory`는 정규화 로직만 재사용하고 세션에 add/commit하지 않는다.
  - FastAPI 라우터/엔드포인트 노출. `router.py`/`service.py` 변경 없음.
  - `api/kipris_api.py`의 API 6 URL/파라미터 수정 (사용자가 별도 진행).
  - `api/` 계층의 기존 함수 시그니처나 동작 변경.

## 파일 구조

새 파일 `biz-lantern/apps/backend/app/domain/company/kipris_pipeline.py`를 만든다.

기존 `pipeline.py`가 명시한 계층 원칙을 그대로 따른다: `api/`는 원본 응답만 반환하고, 여러 API 호출을 조합·가공하는 로직은 별도 파일에 둔다. 이렇게 분리해두면 나중에 DART/NTS 파이프라인과 합치거나, 이 파일만 독립적으로 라우터에 연결하기 쉽다.

## 핵심 흐름

```
collect_patents_with_history(company: str) -> list[PatentReport]
```

1. `get_company_by_company_name(company)` 호출 → JSON 문자열을 받는다.
2. `_extract_items(json_data)` 헬퍼로 `response.body.items.item` 경로에서 아이템 리스트를 뽑는다.
   - xmltodict 특성상 결과가 1건이면 dict, 여러 건이면 list로 오므로 리스트로 통일한다.
   - 검색 결과가 0건이면 빈 리스트를 반환한다 (에러 아님 — 기업이 특허가 없을 수 있다).
3. 각 아이템을 `PatentSearchResult.from_kipris_json(item)`으로 정규화한다 (인스턴스만 생성, DB 세션에 추가하지 않음).
4. 정규화된 특허마다 `application_number`로 `get_company_by_application_number(application_number)`를 호출한다.
   - 같은 `_extract_items` 헬퍼로 아이템 리스트를 뽑는다 (KIPRIS Plus 응답은 보통 동일한 `response > body > items > item` 구조를 따른다).
   - 각 아이템을 `PatentAdministrativeHistory.from_kipris_json(item)`으로 정규화한다.
   - 한 특허가 여러 행정처리 문서를 가질 수 있으므로 리스트로 모은다.
5. 특허 1건 = `PatentReport` 형태로 묶는다:
   ```python
   class PatentReport(TypedDict):
       patent: dict            # PatentSearchResult 공개 필드 (id/created_at/updated_at 제외)
       administrative_history: list[dict]  # PatentAdministrativeHistory 공개 필드 리스트
       history_error: str | None           # 4단계 실패 시 사유, 성공하면 None
   ```
6. 전체 결과는 `list[PatentReport]`.

ORM 인스턴스를 그대로 반환하지 않고 공개 필드만 뽑아 plain dict로 변환한다 (`id`/`created_at`/`updated_at` 등 DB 전용 필드 제외). DB 세션이 없어도 호출 가능해야 하기 때문이다.

## 에러 처리

- **1단계 (특허 리스트 조회) 실패**: 예외를 그대로 올린다. 이 목록이 없으면 이후 단계가 성립하지 않는다.
- **4단계 (개별 특허의 행정처리 이력 조회) 실패**: 해당 특허만 `history_error`에 사유를 담고 `administrative_history=[]`로 두고 계속 진행한다. 특허 10건 중 1건의 이력 조회가 실패했다고 나머지 9건까지 못 받는 일은 없어야 한다.

호출은 순차(sync)로 진행한다. 기존 `dart_api.py`/`nts_api.py`가 전부 sync `httpx.get`을 쓰는 것과 일관성을 맞춘다.

## 파싱 헬퍼

```python
def _extract_items(json_data: str) -> list[dict]:
    """KIPRIS 응답 JSON 문자열에서 response.body.items.item 을 리스트로 뽑는다."""
```

1단계·4단계 모두 이 헬퍼를 재사용한다. 실제 응답 구조가 예상과 다르면 이 함수 하나만 고치면 되도록 파싱 로직을 한 곳에 모은다.

## 테스트용 CLI

파일 하단에 추가:

```python
if __name__ == "__main__":
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else "삼성전자"
    result = collect_patents_with_history(company)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
```

`default=str`은 날짜(`date`) 필드가 JSON 직렬화 안 되는 문제를 처리하기 위함이다.

## 미해결 리스크

- API 6 URL이 아직 실제 KIPRIS 행정처리이력 엔드포인트가 아니므로(사용자가 별도 수정 예정), 사용자가 URL을 고치기 전까지는 4단계가 API 1과 같은 데이터를 다시 받아오거나 예상과 다른 구조로 응답할 수 있다. `_extract_items`와 `PatentAdministrativeHistory.from_kipris_json`이 기대하는 필드가 없으면 해당 특허의 `history_error`에 파싱 실패 사유가 담기고 나머지는 계속 진행된다 — 전체 파이프라인이 죽지는 않는다.
- 실제 KIPRIS 응답의 정확한 XML 구조(`response.body.items.item`)는 코드베이스 내 실제 응답 샘플이 없어 `PatentSearchResult`/`PatentAdministrativeHistory`의 필드명 설계와 일반적인 KIPRIS Plus 응답 패턴에 근거한 추정이다. 실제 실행 시 구조가 다르면 `_extract_items` 수정이 필요할 수 있다.
