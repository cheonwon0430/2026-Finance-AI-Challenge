"""
비상장기업 분석 보고서 HTTP API.

    POST /api/v1/reports              {"corp_code": "01685996"}  -> 202 + report_id
    GET  /api/v1/reports/{report_id}                             -> 200 보고서 전체

프리픽스는 /reports 하나만 갖는다. /api/v1 은 main.py 의 base_router 가 붙인다.

생성이 수십 초에서 몇 분 걸린다(DART 문서 3건 다운로드 + LLM 항목별 호출). 그래서 요청 안에서
끝내지 않고 접수만 하고 돌아온다. 화면은 GET 을 폴링하며 status 를 본다.

**GET 은 파일을 읽기만 한다.** 재계산하지 않는다 - 보고서는 만들어진 시점의 사실이고, 조회할
때마다 다시 계산하면 같은 id 가 다른 내용을 돌려준다.

상태코드를 이렇게 나눈다. **"보고서를 못 만들었다" 와 "그런 보고서가 없다" 는 다른 사건이다.**

    202  생성 요청을 접수했다. 아직 만들어지지 않았다
    200  보고서를 돌려준다. PENDING·COMPLETED·FAILED 를 status 로 구분한다
    400  report_id 가 형식에 맞지 않는다
    404  그 id 의 보고서가 없다
    422  요청 본문이 스키마에 안 맞는다 (FastAPI 가 처리)

FAILED 를 200 으로 돌려주는 이유: 생성이 실패했다는 것도 조회 결과다. 사유는 failure 에 한 줄로
있고, 어디까지 갔는지는 steps 에 있다. 이걸 4xx/5xx 로 만들면 화면이 그 정보를 받지 못한다.
LLM 설정이 없어도 500 이 아니다 - compose 가 룰베이스 정형문으로 저하 동작하고 그 사실을
errors 에 남긴다.

    [1] 설정
    [2] 핸들러
    [3] 시험용 실행

사용법:
    python -m app.domain.report.router
    curl -X POST http://127.0.0.1:8101/reports -H "Content-Type: application/json" \
         -d '{"corp_code":"01685996"}'
    curl http://127.0.0.1:8101/reports/01685996_20260906120000
"""
import logging

from fastapi import APIRouter, HTTPException

from app.domain.report import service, store
from app.domain.report.schema import ReportAccepted, ReportCreate, ReportResponse

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8101  # ai/router.py 가 8100 을 쓴다

logger = logging.getLogger(__name__)

# DB 세션을 받지 않는다. 보고서는 파일로 저장하므로 Depends(get_db) 가 필요 없고, 넣으면
# 요청마다 커넥션이 열리는 데다 테스트가 dependency_overrides 로 우회해야 한다.
router = APIRouter(prefix="/reports", tags=["Report"])


# ---------------------------------------------------------------------------
# [2] 핸들러
# ---------------------------------------------------------------------------
@router.post("", response_model=ReportAccepted, status_code=202)
async def create_report(body: ReportCreate):
    """보고서 생성을 접수한다. 실제 생성은 백그라운드에서 돈다."""
    report = await service.create(body.corp_code)
    logger.info("보고서 접수: report_id=%s", report["report_id"])

    return report


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str):
    """보고서 하나. 아직 만들어지는 중이면 status 가 PENDING 이다."""
    if not store.is_valid_id(report_id):
        # 형식이 아닌 id 는 "없다" 가 아니라 "잘못 물었다" 다. 여기서 끊지 않으면
        # 경로 조작 문자열이 파일 조회까지 내려간다.
        raise HTTPException(
            status_code=400, detail=f"보고서 id 형식이 아닙니다: {report_id}"
        )

    report = service.read(report_id)
    if report is None:
        raise HTTPException(
            status_code=404, detail=f"보고서를 찾을 수 없습니다: {report_id}"
        )

    return report


# ---------------------------------------------------------------------------
# [3] 시험용 실행 - main.py 를 건드리지 않고 HTTP 로 확인한다
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = FastAPI(title="report 시험용 API")
    app.include_router(router)

    print(f"POST http://{HOST}:{PORT}/reports")
    print(f"문서 http://{HOST}:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT)
