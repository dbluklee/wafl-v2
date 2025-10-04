from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import logging

from agent import Agent
from rag_pipeline import RAGPipeline
from document_generator import DocumentGenerator

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WAFL RAG LLM Server")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 에이전트 및 RAG 파이프라인 초기화
agent = Agent()
rag_pipeline = RAGPipeline()
doc_generator = DocumentGenerator()


class ChatRequest(BaseModel):
    message: str
    store_id: int
    category: str = "customer"


class DocumentIndexRequest(BaseModel):
    store_id: int
    category: str = "customer"


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """테스트용 웹 페이지"""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """채팅 엔드포인트"""
    try:
        logger.info("🚀 " + "="*76)
        logger.info(f"🚀 새로운 채팅 요청: store_id={request.store_id}, message={request.message}")
        logger.info("🚀 " + "="*76)

        # 에이전트가 RAG 필요 여부 판단
        needs_rag, agent_debug = await agent.needs_rag(request.message)

        debug_info = {
            "agent": agent_debug,
            "used_rag": needs_rag
        }

        if needs_rag:
            # RAG 파이프라인 실행
            response, rag_debug = await rag_pipeline.query(
                query=request.message,
                store_id=request.store_id,
                category=request.category
            )
            debug_info["rag"] = rag_debug
        else:
            # 일반 대화
            response, chat_debug = await agent.chat(request.message)
            debug_info["chat"] = chat_debug

        logger.info("✅ " + "="*76)
        logger.info(f"✅ 채팅 완료: 응답 길이 = {len(response)} 문자")
        logger.info("✅ " + "="*76 + "\n")

        return JSONResponse({
            "response": response,
            "used_rag": needs_rag,
            "debug": debug_info
        })

    except Exception as e:
        logger.error(f"채팅 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.post("/api/generate-documents")
async def generate_documents(request: DocumentIndexRequest):
    """매장 문서 자동 생성 및 등록 엔드포인트"""
    try:
        logger.info(f"문서 생성 요청: store_id={request.store_id}")

        # 문서 자동 생성
        result = doc_generator.generate_all_documents(request.store_id)

        return JSONResponse({
            "status": "success",
            "message": "문서 생성 완료",
            "data": result
        })

    except Exception as e:
        logger.error(f"문서 생성 오류: {str(e)}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.post("/api/index-documents")
async def index_documents(request: DocumentIndexRequest):
    """문서 인덱싱 엔드포인트"""
    try:
        logger.info(f"문서 인덱싱 요청: store_id={request.store_id}, category={request.category}")

        # 문서 인덱싱
        result = await rag_pipeline.index_documents(
            store_id=request.store_id,
            category=request.category
        )

        return JSONResponse(result)

    except Exception as e:
        logger.error(f"인덱싱 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.get("/api/stores")
async def get_stores():
    """매장 목록 조회"""
    try:
        from sqlalchemy import create_engine, text
        import os

        db_url = os.getenv("DATABASE_URL")
        engine = create_engine(db_url)

        with engine.connect() as conn:
            query = text("SELECT id, store_name FROM stores ORDER BY id")
            result = conn.execute(query)
            stores = [{"id": row[0], "name": row[1]} for row in result]

        return {"stores": stores}

    except Exception as e:
        logger.error(f"매장 목록 조회 오류: {str(e)}")
        return {"stores": []}


@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy", "service": "rag-server"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
