from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import logging
import time
from typing import Optional

from agent import Agent
from rag_pipeline import RAGPipeline
from document_generator import DocumentGenerator
from conversation_service import get_conversation_service
from conversation_logger import get_conversation_logger

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

# 대화 저장 서비스 초기화
try:
    conversation_service = get_conversation_service()
    logger.info("✅ 대화 저장 서비스 초기화 완료")
except Exception as e:
    logger.error(f"⚠️ 대화 저장 서비스 초기화 실패: {str(e)}")
    conversation_service = None

# 비동기 대화 로거 초기화
try:
    conversation_logger = get_conversation_logger()
    if conversation_logger.is_available():
        queue_info = conversation_logger.get_queue_info()
        logger.info(f"✅ 비동기 대화 로거 초기화 완료 (큐: {queue_info.get('queued_jobs', 0)}개 대기)")
    else:
        logger.warning("⚠️ 비동기 대화 로거 사용 불가 - 동기 저장으로 대체")
except Exception as e:
    logger.error(f"⚠️ 비동기 대화 로거 초기화 실패: {str(e)}")
    conversation_logger = None


class ChatRequest(BaseModel):
    message: str
    store_id: int
    category: str = "customer"
    conversation_uuid: Optional[str] = None  # 기존 대화 세션 UUID (선택)


class DocumentIndexRequest(BaseModel):
    store_id: int
    category: str = "customer"


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """테스트용 웹 페이지"""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/api/chat")
async def chat(request: ChatRequest, http_request: Request):
    """채팅 엔드포인트 (대화 저장 포함)"""
    start_time = time.time()
    conversation_uuid = request.conversation_uuid

    try:
        logger.info("🚀 " + "="*76)
        logger.info(f"🚀 새로운 채팅 요청: store_id={request.store_id}, message={request.message}")
        logger.info("🚀 " + "="*76)

        # 대화 세션 생성 또는 기존 세션 사용
        if conversation_service and not conversation_uuid:
            try:
                # 클라이언트 정보 추출
                client_ip = http_request.client.host if http_request.client else None
                user_agent = http_request.headers.get("user-agent")

                # 새 대화 세션 생성
                conversation_uuid = conversation_service.create_conversation(
                    store_id=request.store_id,
                    category=request.category,
                    client_ip=client_ip,
                    user_agent=user_agent
                )
                logger.info(f"🔐 대화 세션 생성: {conversation_uuid}")
            except Exception as e:
                logger.error(f"⚠️ 대화 세션 생성 실패: {str(e)}")

        # 에이전트가 RAG 필요 여부 판단
        needs_rag, agent_debug = await agent.needs_rag(request.message)

        debug_info = {
            "agent": agent_debug,
            "used_rag": needs_rag
        }

        rag_doc_count = None
        rag_max_score = None

        if needs_rag:
            # RAG 파이프라인 실행
            response, rag_debug = await rag_pipeline.query(
                query=request.message,
                store_id=request.store_id,
                category=request.category
            )
            debug_info["rag"] = rag_debug

            # RAG 메타데이터 추출
            if "retrieved_documents" in rag_debug:
                rag_doc_count = len(rag_debug["retrieved_documents"])
                if rag_doc_count > 0:
                    rag_max_score = rag_debug["retrieved_documents"][0].get("score")
        else:
            # 일반 대화
            response, chat_debug = await agent.chat(request.message)
            debug_info["chat"] = chat_debug

        # 응답 시간 계산
        response_time_ms = int((time.time() - start_time) * 1000)

        # 대화 저장 (비동기 전용 - 실패 시 저장 안함)
        if conversation_logger and conversation_logger.is_available() and conversation_uuid:
            try:
                # 메시지를 큐에 추가만 하고 즉시 반환 (~1ms)
                job_id = conversation_logger.enqueue_message_save(
                    conversation_uuid=conversation_uuid,
                    user_message=request.message,
                    bot_response=response,
                    used_rag=needs_rag,
                    response_time_ms=response_time_ms,
                    rag_doc_count=rag_doc_count,
                    rag_max_score=rag_max_score
                )
                if job_id:
                    logger.info(f"📤 대화 저장 작업 큐 추가: job_id={job_id}")
                else:
                    logger.warning("⚠️ 대화 저장 큐 추가 실패 - 저장 스킵")
            except Exception as e:
                logger.error(f"⚠️ 대화 저장 실패 - 저장 스킵: {str(e)}")
        else:
            if conversation_uuid:
                logger.warning("⚠️ 비동기 로거 사용 불가 - 대화 저장 스킵")

        logger.info("✅ " + "="*76)
        logger.info(f"✅ 채팅 완료: 응답 길이 = {len(response)} 문자, 응답 시간 = {response_time_ms}ms")
        logger.info("✅ " + "="*76 + "\n")

        return JSONResponse({
            "response": response,
            "used_rag": needs_rag,
            "conversation_uuid": conversation_uuid,
            "response_time_ms": response_time_ms,
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


@app.get("/api/logging-queue/status")
async def get_logging_queue_status():
    """
    비동기 로깅 큐 상태 조회

    Returns:
        큐 상태 정보 (대기중, 처리중, 완료, 실패 작업 수)
    """
    try:
        if not conversation_logger or not conversation_logger.is_available():
            return JSONResponse({
                "available": False,
                "message": "비동기 로깅 사용 불가"
            })

        queue_info = conversation_logger.get_queue_info()

        return JSONResponse({
            "available": True,
            "queue_info": queue_info,
            "message": "비동기 로깅 정상 작동 중"
        })

    except Exception as e:
        logger.error(f"큐 상태 조회 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# =====================================================================
# 대화 관리 API
# =====================================================================

@app.get("/api/conversations/{conversation_uuid}")
async def get_conversation(conversation_uuid: str, decrypt: bool = False):
    """
    특정 대화 세션의 메시지 조회

    Args:
        conversation_uuid: 대화 세션 UUID
        decrypt: 메시지 복호화 여부 (기본: False)
    """
    try:
        if not conversation_service:
            return JSONResponse(
                {"error": "대화 저장 서비스를 사용할 수 없습니다"},
                status_code=503
            )

        messages = conversation_service.get_conversation_messages(
            conversation_uuid=conversation_uuid,
            decrypt=decrypt
        )

        return JSONResponse({
            "conversation_uuid": conversation_uuid,
            "message_count": len(messages),
            "messages": messages
        })

    except Exception as e:
        logger.error(f"대화 조회 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.post("/api/conversations/{conversation_uuid}/end")
async def end_conversation_session(conversation_uuid: str):
    """대화 세션 종료"""
    try:
        if not conversation_service:
            return JSONResponse(
                {"error": "대화 저장 서비스를 사용할 수 없습니다"},
                status_code=503
            )

        conversation_service.end_conversation(conversation_uuid)

        return JSONResponse({
            "status": "success",
            "message": "대화 세션이 종료되었습니다",
            "conversation_uuid": conversation_uuid
        })

    except Exception as e:
        logger.error(f"대화 종료 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


@app.get("/api/stores/{store_id}/conversation-statistics")
async def get_conversation_statistics(store_id: int, days: int = 30):
    """
    매장의 대화 통계 조회

    Args:
        store_id: 매장 ID
        days: 조회 기간 (일, 기본: 30일)
    """
    try:
        if not conversation_service:
            return JSONResponse(
                {"error": "대화 저장 서비스를 사용할 수 없습니다"},
                status_code=503
            )

        stats = conversation_service.get_store_statistics(
            store_id=store_id,
            days=days
        )

        return JSONResponse(stats)

    except Exception as e:
        logger.error(f"통계 조회 오류: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
