from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import logging
import time
from typing import Optional

from agent import Agent  # 기존 Agent (백업용, 추후 제거 예정)
from router import get_router
from tool_executor import get_tool_executor
from rag_pipeline import RAGPipeline
from document_generator import DocumentGenerator
from conversation_service import get_conversation_service
from conversation_logger import get_conversation_logger
import ollama
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WAFL RAG LLM Server")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 에이전트 및 RAG 파이프라인 초기화
agent = Agent()  # 기존 Agent (백업용)
router = get_router()  # 지능형 라우터
tool_executor = get_tool_executor()  # 툴 실행기
rag_pipeline = RAGPipeline()
doc_generator = DocumentGenerator()

# 메인 LLM 클라이언트 (SIMPLE_QA 및 LLM-Interpreted 툴용)
main_llm_url = os.getenv("OLLAMA_MAIN_URL", "http://112.148.37.41:1884")
main_llm_client = ollama.Client(host=main_llm_url)
main_llm_model = "gemma3:27b-it-q4_K_M"

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
    language: Optional[str] = "ko"  # 사용자 언어 설정 (ko, en, ja, zh)


class DocumentIndexRequest(BaseModel):
    store_id: int
    category: str = "customer"


async def interpret_tool_result_with_llm(
    user_message: str,
    tool_name: str,
    tool_result: dict,
    language: str = "ko"
) -> str:
    """
    LLM-Interpreted 툴 결과를 Gemma3로 자연어 해석

    Args:
        user_message: 사용자 메시지
        tool_name: 실행된 툴 이름
        tool_result: 툴 실행 결과
        language: 응답 언어 (ko, en, ja, zh)

    Returns:
        자연어 응답
    """
    try:
        # 툴 결과를 문자열로 변환
        import json
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)

        # 언어별 지시
        language_instructions = {
            "ko": "한국어로 답변하세요.",
            "en": "Answer in English.",
            "ja": "日本語で答えてください。",
            "zh": "用中文回答。"
        }

        prompt = f"""You are a friendly store assistant.
The system has retrieved the following data. Please respond naturally to the customer based on this data.

Customer question: {user_message}
Function executed: {tool_name}
Query results:
{result_str}

Response rules:
1. Keep your answer concise, within 50 characters
2. Deliver only the key points of the data
3. Explain naturally and kindly
4. Format numbers for readability (e.g., 1500000 → 1.5M or 150만원)
5. Mention trends or insights briefly if any

**IMPORTANT: {language_instructions.get(language, language_instructions["ko"])}**

Answer:"""

        response = main_llm_client.generate(
            model=main_llm_model,
            prompt=prompt
        )

        answer = response['response'].strip()

        # 50자 제한 체크
        more_messages = {
            "ko": "\n\n더 자세히 설명해드릴까요?",
            "en": "\n\nWould you like more details?",
            "ja": "\n\nもっと詳しく説明しましょうか？",
            "zh": "\n\n需要更详细的说明吗？"
        }

        if len(answer) > 50:
            answer = answer[:50] + "..."
            answer += more_messages.get(language, more_messages["ko"])

        return answer

    except Exception as e:
        logger.error(f"LLM 해석 오류: {str(e)}")
        error_messages = {
            "ko": "데이터 조회는 완료했지만, 설명 중 오류가 발생했습니다.",
            "en": "Data retrieval completed, but an error occurred during explanation.",
            "ja": "データ検索は完了しましたが、説明中にエラーが発生しました。",
            "zh": "数据检索已完成，但在解释过程中发生了错误。"
        }
        return error_messages.get(language, error_messages["ko"])


async def simple_chat_with_llm(user_message: str, language: str = "ko") -> str:
    """
    일반 대화 처리 (SIMPLE_QA)

    Args:
        user_message: 사용자 메시지
        language: 응답 언어 (ko, en, ja, zh)

    Returns:
        LLM 응답
    """
    try:
        # 언어별 지시
        language_instructions = {
            "ko": "한국어로 답변하세요.",
            "en": "Answer in English.",
            "ja": "日本語で答えてください。",
            "zh": "用中文回答。"
        }

        prompt = f"""You are a friendly store assistant.

Response rules:
1. Keep your answer concise, within 50 characters
2. Deliver only the key points the customer wants
3. Be kind but get to the point
4. Skip unnecessary explanations
5. **Important**: Never make up information you don't know
6. If uncertain, say "I'm not sure. Please ask a staff member for assistance"

**IMPORTANT: {language_instructions.get(language, language_instructions["ko"])}**

User: {user_message}
Assistant:"""

        response = main_llm_client.generate(
            model=main_llm_model,
            prompt=prompt
        )

        answer = response['response'].strip()

        # 50자 제한 체크
        more_messages = {
            "ko": "\n\n더 자세히 설명해드릴까요?",
            "en": "\n\nWould you like more details?",
            "ja": "\n\nもっと詳しく説明しましょうか？",
            "zh": "\n\n需要更详细的说明吗？"
        }

        if len(answer) > 50:
            answer = answer[:50] + "..."
            answer += more_messages.get(language, more_messages["ko"])

        return answer

    except Exception as e:
        logger.error(f"일반 대화 오류: {str(e)}")
        error_messages = {
            "ko": "죄송합니다. 일시적인 오류가 발생했습니다.",
            "en": "Sorry, a temporary error has occurred.",
            "ja": "申し訳ありません。一時的なエラーが発生しました。",
            "zh": "抱歉，发生了临时错误。"
        }
        return error_messages.get(language, error_messages["ko"])


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

        # 라우터로 경로 결정
        route_decision = await router.route(request.message)

        debug_info = {
            "router": route_decision,
            "route": route_decision["route"]
        }

        rag_doc_count = None
        rag_max_score = None
        used_rag = False
        used_tool = None
        changed_language = None  # 툴로 변경된 언어

        # 경로별 처리
        if route_decision["route"] == "TOOL_CALL":
            # 툴 호출
            tool_name = route_decision["tool_name"]
            tool_params = route_decision.get("tool_params", {})
            tool_type = route_decision["tool_type"]

            logger.info(f"🔧 툴 호출: {tool_name} ({tool_type})")

            # 툴 실행
            tool_result = await tool_executor.execute_tool(tool_name, tool_params)
            debug_info["tool_result"] = tool_result
            used_tool = tool_name

            # set_language 툴인 경우 변경된 언어 추출
            if tool_name == "set_language" and tool_result.get("success"):
                changed_language = tool_result.get("result", {}).get("language")
                logger.info(f"🌐 언어 변경 감지: {changed_language}")

            if not tool_result["success"]:
                # 툴 실행 실패
                response = f"죄송합니다. {tool_result.get('error', '알 수 없는 오류')}"
                logger.error(f"❌ 툴 실행 실패: {tool_result.get('error')}")
            elif tool_type == "Self-Contained":
                # 자체 처리 툴 - 즉시 응답
                response = tool_result["result"].get("message", tool_result["notification"])
                logger.info(f"✅ Self-Contained 툴 완료: {response}")
            else:
                # LLM-Interpreted 툴 - Gemma3로 해석
                logger.info(f"🤖 LLM 해석 시작 (툴 결과 해석)")
                response = await interpret_tool_result_with_llm(
                    user_message=request.message,
                    tool_name=tool_name,
                    tool_result=tool_result["result"],
                    language=changed_language if changed_language else request.language
                )
                debug_info["llm_interpretation"] = response

        elif route_decision["route"] == "RAG_QUERY":
            # RAG 파이프라인 실행
            logger.info(f"📚 RAG 쿼리 실행")
            used_rag = True

            response, rag_debug = await rag_pipeline.query(
                query=route_decision["query"],
                store_id=request.store_id,
                category=request.category,
                language=request.language
            )
            debug_info["rag"] = rag_debug

            # RAG 메타데이터 추출
            if "retrieved_documents" in rag_debug:
                rag_doc_count = len(rag_debug["retrieved_documents"])
                if rag_doc_count > 0:
                    rag_max_score = rag_debug["retrieved_documents"][0].get("score")

        else:  # SIMPLE_QA
            # 일반 대화 - Gemma3 직접 응답
            logger.info(f"💬 일반 대화 처리")
            response = await simple_chat_with_llm(route_decision["query"], language=request.language)
            debug_info["simple_chat"] = response

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

        # 응답 구성
        response_data = {
            "response": response,
            "route": route_decision["route"],
            "used_rag": used_rag,
            "used_tool": used_tool,
            "conversation_uuid": conversation_uuid,
            "response_time_ms": response_time_ms,
            "debug": debug_info
        }

        # 언어가 변경된 경우 변경된 언어를 반환, 아니면 요청 언어 반환
        if changed_language:
            response_data["language"] = changed_language
            response_data["language_changed"] = True
            logger.info(f"📤 응답에 변경된 언어 포함: {changed_language}")
        else:
            response_data["language"] = request.language

        return JSONResponse(response_data)

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


@app.get("/api/language")
async def get_language():
    """
    현재 언어 설정 조회 (프론트엔드용)
    로컬 스토리지에서 관리하므로 기본값만 반환
    """
    return {"language": "ko"}


@app.post("/api/language")
async def set_language(language: str = "ko"):
    """
    언어 설정 변경 (프론트엔드용)
    실제로는 프론트엔드에서 로컬 스토리지로 관리
    """
    supported_languages = ["ko", "en", "ja", "zh"]
    if language not in supported_languages:
        return JSONResponse(
            {"error": f"지원하지 않는 언어입니다. 지원 언어: {', '.join(supported_languages)}"},
            status_code=400
        )

    return {
        "success": True,
        "language": language,
        "message": f"언어가 {language}(으)로 변경되었습니다"
    }


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
