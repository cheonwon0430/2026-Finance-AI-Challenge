from fastapi import FastAPI
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


app.include_router(company_router)


@app.get("/")
async def root():
    return {
        "message": "biz-lantern API",
        "status": "ok",
    }