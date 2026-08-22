from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.domain.company.router import router as company_router


app = FastAPI(
    title="biz-lantern API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
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

# Register API v1
app.include_router(base_router)



##########################################################
# Health Check
@base_router.get("")
async def root():
    return {
        "message": "biz-lantern API is Connected",
        "status": "ok",
    }