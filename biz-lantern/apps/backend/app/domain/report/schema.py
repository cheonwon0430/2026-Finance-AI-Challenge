"""
/reports 엔드포인트의 요청·응답 DTO.

보고서 본문은 infer.InferResult 와 compose.ComposeResult 를 그대로 실어 보낸다. 그 안의
Finding·Evidence·ItemNarrative 를 pydantic 으로 다시 모델링하지 않는다 - Evidence 는
total=False 필드가 많아 옮겨 적으면 두 곳이 갈라지고, 갈라지는 순간 응답이 조용히 필드를
잃는다. 타입 정의의 원본은 백엔드 TypedDict 이고 프론트는 자기 DTO 를 따로 만든다.
(company/schema.py 가 pipeline 을 dict 로 둔 것과 같은 선택이다.)

    [1] 상태값
    [2] 요청
    [3] 응답
"""
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# [1] 상태값
# ---------------------------------------------------------------------------
# FAILED 는 수집이 예외를 올렸을 때뿐이다. infer 와 compose 는 부분 실패를 스스로 흡수해
# 언제나 결과를 내므로, LLM 이 전부 죽어도 COMPLETED 다 - 그때도 룰베이스 정형문이 남아
# 보고서로 성립한다. "무엇이 빠졌는가" 는 status 가 아니라 errors 와 items[].llm_status 에 있다.
PENDING = "PENDING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

Status = Literal["PENDING", "COMPLETED", "FAILED"]

CORP_CODE_LENGTH = 8  # DART 고유번호는 8자리 고정이다


# ---------------------------------------------------------------------------
# [2] 요청
# ---------------------------------------------------------------------------
class ReportCreate(BaseModel):
    """corp_code 하나로 보고서 생성을 요청한다.

    회사명을 받지 않는다. 이름은 부분 일치라 여러 건이 걸리고, 그걸 자동으로 고르면 엉뚱한
    회사를 분석하게 된다. 이름 -> corp_code 해소는 이미 GET /companies 가 한다.
    """

    corp_code: str = Field(
        min_length=CORP_CODE_LENGTH,
        max_length=CORP_CODE_LENGTH,
        pattern=r"^\d{8}$",
        description="DART 고유번호 8자리 (예: 01685996)",
    )


# ---------------------------------------------------------------------------
# [3] 응답
# ---------------------------------------------------------------------------
class ReportAccepted(BaseModel):
    """POST 직후의 응답. 아직 만들어지지 않았다."""

    report_id: str
    corp_code: str
    status: Status
    created_at: str


class ReportResponse(BaseModel):
    """GET 응답. 파일에 얼려 둔 것을 그대로 돌려준다.

    PENDING 이면 본문 필드가 전부 비어 있고 status 만 의미가 있다. 화면은 status 를 보고
    폴링을 계속할지 정한다.
    """

    report_id: str
    corp_code: str
    status: Status
    created_at: str
    as_of: str | None = None          # 판정 기준일. PENDING 이면 null
    completed_at: str | None = None
    company_name: str | None = None
    failure: str | None = None        # FAILED 일 때의 사유 한 줄. 그 외에는 null

    findings: dict = Field(default_factory=dict)          # 항목 25개의 판정
    items: dict = Field(default_factory=dict)             # 항목 25개의 서술
    sections: list[dict] = Field(default_factory=list)    # 보고서 본문 절
    evidence: list[dict] = Field(default_factory=list)    # 근거 조각 전량
    derived: list[str] = Field(default_factory=list)      # F 블록 파생 조각 ID
    errors: list[dict] = Field(default_factory=list)      # 서술 단계에서 터진 것
    orphan_derived: list[str] = Field(default_factory=list)

    # 이상징후와 그에 딸린 조사. findings 와 같은 이유로 dict 인 채로 둔다 - Signal 도
    # InvestigationTask 도 소유자가 signals.py 이고, 여기 옮겨 적으면 두 곳이 갈라진다.
    signals: list[dict] = Field(default_factory=list)         # 발견한 이상징후
    investigations: list[dict] = Field(default_factory=list)  # 중복을 없앤 조사 큐
    coverage: dict = Field(default_factory=dict)              # 무엇을 평가할 수 있었는가
    steps: list[dict] = Field(default_factory=list)       # 수집 진행 기록
