"""수집·판정·서술을 엮어 보고서 하나를 만든다.

라우터는 HTTP 만 알고 엔진(pipeline·infer·compose)은 자기 자료구조만 안다. 그 사이를
잇는 게 여기다.

    corp_code ──▶ pipeline.collect ──▶ infer.run ──▶ compose.run ──▶ store.save

    [1] 시계
    [2] 골격
    [3] 생성
    [4] 조회

**여기가 시계를 읽는 유일한 지점이다.** evidence 는 datetime 을 import 조차 하지 않고,
infer.run 은 as_of 를 키워드 필수로 받으며, compose 는 인자를 아예 두지 않았다. 같은 입력이
날짜마다 다른 근거 ID 를 만들지 않게 하려고 시계를 계층 끝까지 밀어냈고, 그 끝이 여기다.

**FAILED 는 예외가 올라왔을 때뿐이다.** infer 와 compose 는 부분 실패를 스스로 흡수해 언제나
결과를 낸다 - 국세청이 죽어도, 감사보고서가 0건이어도, LLM 이 전부 죽어도 보고서는 완결된다
(그때도 룰베이스 정형문이 남는다). 무엇이 빠졌는지는 status 가 아니라 steps · errors ·
items[].llm_status 에 있다.
"""
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.company import pipeline as pl
from app.domain.company.pipeline import _reason
from app.domain.report import compose, infer, schema, store

logger = logging.getLogger(__name__)

# 백그라운드 태스크의 참조를 붙잡아 둔다. create_task 반환값을 버리면 GC 가 실행 중인
# 태스크를 거둬가 보고서가 PENDING 인 채로 영영 멈춘다(CPython 의 알려진 함정).
_TASKS: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# [1] 시계
# ---------------------------------------------------------------------------
def _now() -> datetime:
    """현재 시각(로컬, tz 포함). 이 함수 하나만 시계를 읽는다 - 테스트는 여기를 갈아끼운다.

    UTC 로 읽어 로컬로 변환한다. as_of 는 회계 기준일이라 한국 날짜여야 하는데, UTC 로
    두면 오전 9시 이전 요청이 전날 보고서가 된다.
    """
    return datetime.now(UTC).astimezone()


# ---------------------------------------------------------------------------
# [2] 골격
# ---------------------------------------------------------------------------
def _pending(report_id: str, corp_code: str, created_at: str) -> dict[str, Any]:
    """POST 직후에 저장할 뼈대.

    이걸 먼저 쓰지 않으면 POST 응답을 받자마자 보낸 GET 이 404 가 된다. 사용자는 방금
    만들라고 한 보고서가 없다는 답을 받는 셈이다.
    """
    return {
        "report_id": report_id,
        "corp_code": corp_code,
        "status": schema.PENDING,
        "created_at": created_at,
        "as_of": None,
        "completed_at": None,
        "company_name": None,
        "failure": None,
        "findings": {},
        "items": {},
        "evidence": [],
        "derived": [],
        "errors": [],
        "orphan_derived": [],
        "steps": [],
    }


def _failed(
    base: dict[str, Any], error: Exception, completed_at: str
) -> dict[str, Any]:
    """실패로 마감한다. 사유는 한 줄로 남긴다.

    _reason() 을 pipeline 에서 그대로 가져다 쓴다. httpx 의 HTTPStatusError 는 요청 URL 을
    메시지에 담는데 DART 도 국세청도 인증키를 쿼리스트링으로 받으므로, 마스킹하지 않으면
    **인증키가 보고서 JSON 에 굳어 그대로 API 응답으로 나간다.** 정규식을 복제하면 새 인증
    파라미터가 생겼을 때 한쪽만 고치게 되므로 복제하지 않는다.
    """
    return {
        **base,
        "status": schema.FAILED,
        "completed_at": completed_at,
        "failure": _reason(error),
    }


# ---------------------------------------------------------------------------
# [3] 생성
# ---------------------------------------------------------------------------
async def create(corp_code: str) -> dict[str, Any]:
    """PENDING 을 저장하고 백그라운드로 넘긴다. 즉시 돌아온다.

    같은 corp_code 로 다시 불러도 기존 보고서를 재사용하지 않는다. id 에 생성 시각이
    들어가 이력이 쌓이고, 그래야 시점이 다른 보고서를 나란히 비교할 수 있다 - 근거 ID 를
    결정적으로 만든 이유가 그 비교였다.
    """
    now = _now()
    report_id = store.new_report_id(corp_code, now)
    report = _pending(report_id, corp_code, now.isoformat(timespec="seconds"))
    store.save(report)

    task = asyncio.create_task(
        build(report_id, corp_code, as_of=now.date().isoformat())
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)

    return report


async def build(report_id: str, corp_code: str, *, as_of: str) -> dict[str, Any]:
    """실제 파이프라인. 예외를 올리지 않고 FAILED 로 기록한다.

    백그라운드 태스크라 예외를 올려 봐야 아무도 받지 못하고 보고서는 PENDING 에 멈춘다.
    그래서 여기서 전부 잡아 파일에 남긴다 - 실패도 조회 가능한 결과여야 한다.
    """
    base = store.load(report_id) or _pending(
        report_id, corp_code, _now().isoformat(timespec="seconds")
    )

    try:
        # collect 는 동기 함수다(DART·국세청을 여러 번 순차 호출). 이벤트 루프를 막지
        # 않도록 스레드로 민다. infer.run 도 동기이고 문서 파싱이라 CPU 를 오래 쓴다.
        collected = await asyncio.to_thread(pl.collect, corp_code)
        inferred = await asyncio.to_thread(infer.run, collected, as_of=as_of)

        company = collected.get("company") or {}
        company_name = company.get("corp_name") or corp_code

        # 클라이언트는 여기서 소유하고 여기서 닫는다. compose 는 전역 클라이언트를 만들지
        # 않는다(app/ai/news/graph.py 와 같은 패턴).
        async with httpx.AsyncClient() as client:
            narrated = await compose.run(client, inferred, company_name=company_name)

    except Exception as error:
        logger.exception("보고서 생성 실패: report_id=%s", report_id)
        report = _failed(base, error, _now().isoformat(timespec="seconds"))
        store.save(report)

        return report

    report = {
        **base,
        "status": schema.COMPLETED,
        "as_of": as_of,
        "completed_at": _now().isoformat(timespec="seconds"),
        "company_name": company_name,
        "failure": None,
        "findings": inferred["findings"],
        "items": narrated["items"],
        "evidence": inferred["evidence"],
        "derived": inferred["derived"],
        "errors": narrated["errors"],
        "orphan_derived": narrated["orphan_derived"],
        "steps": collected.get("steps") or [],
    }
    store.save(report)

    return report


# ---------------------------------------------------------------------------
# [4] 조회
# ---------------------------------------------------------------------------
def read(report_id: str) -> dict[str, Any] | None:
    """파일을 읽기만 한다. 재계산하지 않는다.

    보고서는 만들어진 시점의 사실이다. 조회할 때마다 다시 계산하면 같은 id 가 다른 내용을
    돌려주게 되고, 근거 스냅샷을 굳혀 둔 의미가 사라진다.
    """
    return store.load(report_id)
