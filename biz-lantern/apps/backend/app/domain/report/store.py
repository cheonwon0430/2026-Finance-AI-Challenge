"""보고서를 파일로 얼리고 다시 읽는다. data/reports/{report_id}.json 한 곳이다.

DB 를 쓰지 않는 이유: 실측으로 보고서 하나가 문서 1건 기준 57KB(근거 조각 41건, 가장 큰
조각 706자)다. 3개년이라도 100KB 미만이라 파일 하나로 충분하고, report 용 ORM 모델도
마이그레이션 도구도 없는 상태에서 테이블을 새로 만들 값이 없다. data/raw · data/clean 과
같은 자리에 둔다.

    [1] 설정
    [2] 식별자
    [3] 저장과 조회

**GET 은 재계산하지 않는다.** 여기서 읽은 것이 그대로 응답이 된다. 그래서 저장할 때
raw_content 를 자르지 않는다 - 자르면 근거 토글이 원문에 닿지 못한다.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
REPORTS_DIR = Path("data/reports")  # data/ 는 gitignore 대상이다

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# [2] 식별자
# ---------------------------------------------------------------------------
# 랜덤 UUID 를 쓰지 않는다. 디렉터리를 열었을 때 어느 회사의 언제 보고서인지 바로 읽혀야
# 하고, 같은 기업의 보고서가 시간순으로 정렬돼야 이력 비교가 된다.
ID_FORMAT = "%Y%m%d%H%M%S"
_REPORT_ID = re.compile(r"^\d{8}_\d{14}$")


def new_report_id(corp_code: str, now: datetime) -> str:
    """{corp_code}_{YYYYMMDDHHMMSS}. 시각은 인자로 받는다 - 이 모듈은 시계를 읽지 않는다."""
    return f"{corp_code}_{now.strftime(ID_FORMAT)}"


def is_valid_id(report_id: str) -> bool:
    """형식 검사. 통과하지 못한 id 로는 파일을 열지 않는다.

    report_id 가 URL 경로에 그대로 들어오므로 이 검사가 보안 요구다. '..' 이나 '/' 가
    섞인 값을 그대로 REPORTS_DIR 에 붙이면 저장소 밖 파일을 읽을 수 있다. 화이트리스트
    정규식으로 막는다 - 위험한 문자를 골라 지우는 방식은 언제나 빠뜨리는 것이 생긴다.
    """
    return bool(_REPORT_ID.fullmatch(report_id or ""))


def path_of(report_id: str) -> Path:
    """id -> 파일 경로. 형식을 통과한 id 에만 쓴다."""
    return REPORTS_DIR / f"{report_id}.json"


# ---------------------------------------------------------------------------
# [3] 저장과 조회
# ---------------------------------------------------------------------------
def save(report: dict[str, Any]) -> Path:
    """보고서 하나를 통째로 쓴다. 같은 id 면 덮어쓴다(PENDING -> COMPLETED)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    path = path_of(report["report_id"])
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return path


def load(report_id: str) -> dict[str, Any] | None:
    """없으면 None. 형식이 틀린 id 도 None 이다 - 파일을 열기 전에 막는다.

    JSON 이 깨져 있으면 None 이 아니라 예외를 올린다. 파일이 없는 것(404 로 답할 일)과
    저장이 깨진 것(우리 쪽 오류)은 다른 사건이고, 뭉개면 깨진 저장을 영영 모른다.
    """
    if not is_valid_id(report_id):
        logger.warning("보고서 id 형식이 아니다: %r", report_id)

        return None

    path = path_of(report_id)
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))
