from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, home, children, tests, reports, chat, mypage, rag_admin

app = FastAPI(
    title="그담 API",
    description="HTP 기반 AI 심리 분석 및 육아 방향 안내 서비스 API 명세서",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://sai-gdam.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(home.router, prefix="/home", tags=["Home"])
app.include_router(children.router, prefix="/children", tags=["Children"])
app.include_router(tests.router, prefix="/tests", tags=["Tests"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(mypage.router, prefix="/mypage", tags=["Mypage"])

# RAG 관리자 API
app.include_router(rag_admin.router)


@app.get("/")
def root():
    return {"message": "그담 API is running"}