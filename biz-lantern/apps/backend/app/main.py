import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.config import settings
from app.domain.ai.router import router as chat_router
from app.domain.company.router import router as company_router
from app.domain.report.router import router as report_router
from app.infrastructure.database.init import init_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동 시 테이블을 만든다.

    Alembic 을 쓰지 않으므로 이 호출이 스키마를 만드는 유일한 경로다. 이게 없으면 새로 올린
    서버는 뜨기는 하는데 첫 /companies 요청에서 UndefinedTable 로 죽는다 - 로컬은 예전에
    수동으로 만들어둔 테이블이 남아 있어서 드러나지 않던 문제다.

    create_all 은 이미 있는 테이블을 건드리지 않으므로 매 기동마다 불러도 안전하다.
    DB 에 닿지 못하면 여기서 예외가 올라가 기동이 실패한다 - 그게 맞다. 스키마 없는 채로 떠서
    요청마다 500 을 내는 것보다 컨테이너가 재시작을 반복하는 쪽이 원인이 보인다.
    """
    await init_database()
    logger.info("DB 스키마 확인 완료")

    yield


app = FastAPI(
    title="biz-lantern API",
    version="0.1.0",
    lifespan=lifespan,
)

# 배포에서는 CORS_ORIGINS 로 서버 주소를 넣는다. nginx 가 /api 를 프록시하는 구성에서는
# 동일 출처라 CORS 자체가 발동하지 않지만, 프론트를 따로 띄우는 경우를 위해 남긴다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 Root Router
base_router = APIRouter(
    prefix="/api/v1",
)

# Domain Routers
base_router.include_router(company_router)
base_router.include_router(chat_router)
base_router.include_router(report_router)

##########################################################
# Health Check
# **include_router 보다 먼저 정의해야 한다.** include_router 는 호출 시점의 routes 를 복사하므로
# 그 뒤에 base_router 에 붙인 경로는 앱에 등록되지 않는다(원래 이 핸들러가 그 자리에 있어서
# GET /api/v1 이 404 였다).
@base_router.get("")
async def root():
    return {
        "message": "biz-lantern API is Connected",
        "status": "ok",
    }


# Register API v1
app.include_router(base_router)
