import os
import logging
import ollama
from sqlalchemy import create_engine, text

from embeddings import BGE_M3_Embeddings
from vector_store import MilvusVectorStore
from document_loader import DocumentLoader

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG 파이프라인: 문서 인덱싱 및 검색"""

    def __init__(self):
        # 컴포넌트 초기화
        self.embeddings = BGE_M3_Embeddings()
        self.vector_store = MilvusVectorStore(dimension=self.embeddings.dimension)
        self.document_loader = DocumentLoader(chunk_size=1000, chunk_overlap=200)

        # Ollama 클라이언트 (메인 LLM)
        main_url = os.getenv("OLLAMA_MAIN_URL", "http://112.148.37.41:1884")
        self.llm_client = ollama.Client(host=main_url)
        self.llm_model = "gemma3:27b-it-q4_K_M"

        # 데이터베이스 연결
        db_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(db_url)

    async def index_documents(self, store_id: int, category: str = "customer") -> dict:
        """
        특정 매장의 문서들을 인덱싱

        Args:
            store_id: 매장 ID
            category: 문서 카테고리 (customer/owner)

        Returns:
            인덱싱 결과
        """
        try:
            # 데이터베이스에서 문서 경로 조회
            with self.engine.connect() as conn:
                query = text("""
                    SELECT doc_path FROM rag_documents
                    WHERE store_id = :store_id AND category = :category
                """)
                result = conn.execute(query, {"store_id": store_id, "category": category})
                doc_paths = [row[0] for row in result]

            if not doc_paths:
                return {
                    "status": "error",
                    "message": f"매장 {store_id}의 {category} 문서가 없습니다."
                }

            # 기존 벡터 삭제
            self.vector_store.delete_by_store(store_id, category)

            # 문서 로드 및 청킹
            all_chunks = []
            for doc_path in doc_paths:
                chunks = self.document_loader.load_and_chunk(doc_path)
                all_chunks.extend(chunks)

            if not all_chunks:
                return {
                    "status": "error",
                    "message": "청킹된 문서가 없습니다."
                }

            # 임베딩 생성
            embeddings = self.embeddings.embed_documents(all_chunks)

            # 벡터 스토어에 삽입
            self.vector_store.insert(
                texts=all_chunks,
                embeddings=embeddings,
                store_id=store_id,
                category=category
            )

            return {
                "status": "success",
                "indexed_documents": len(doc_paths),
                "indexed_chunks": len(all_chunks),
                "store_id": store_id,
                "category": category
            }

        except Exception as e:
            logger.error(f"인덱싱 오류: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def query(self, query: str, store_id: int, category: str = "customer") -> tuple[str, dict]:
        """
        RAG 쿼리 실행

        Args:
            query: 사용자 질문
            store_id: 매장 ID
            category: 문서 카테고리

        Returns:
            tuple[str, dict]: (LLM 응답, 디버그 정보)
        """
        try:
            logger.info("="*80)
            logger.info("🔍 [RAG] 문서 검색 시작")
            logger.info("="*80)

            # 쿼리 임베딩
            query_embedding = self.embeddings.embed_query(query)
            logger.info(f"📊 쿼리 임베딩 완료 (차원: {len(query_embedding)})")

            # 유사 문서 검색 (상위 5개)
            documents = self.vector_store.search(
                query_embedding=query_embedding,
                store_id=store_id,
                category=category,
                top_k=5
            )

            if not documents:
                logger.warning("⚠️ 검색된 문서가 없습니다")
                return "제가 잘 모르겠어요. 죄송하지만 직원에게 문의해주세요.", {"error": "No documents found"}

            logger.info(f"📚 검색된 문서: {len(documents)}개")
            for i, doc in enumerate(documents, 1):
                logger.info(f"  [{i}] 유사도: {doc['score']:.4f}")
                logger.info(f"      내용 미리보기: {doc['text'][:100]}...")

            # 유사도가 너무 낮으면 관련 정보 없음으로 처리
            if documents[0]['score'] < 0.3:
                logger.warning(f"⚠️ 최고 유사도가 너무 낮습니다: {documents[0]['score']:.4f}")
                return "제가 잘 모르겠어요. 죄송하지만 직원에게 문의해주세요.", {"error": "Low relevance score", "max_score": documents[0]['score']}

            # 컨텍스트 생성
            context = "\n\n".join([doc["text"] for doc in documents])

            # 프롬프트 템플릿
            prompt = f"""당신은 매장의 친절한 직원입니다.
아래 매장 문서를 바탕으로 손님의 질문에 답변하세요.

답변 규칙:
1. 50자 이내로 간결하게 답변하세요
2. 손님이 원하는 핵심만 전달하세요
3. 친절하지만 요점만 말하세요
4. 불필요한 설명은 생략하세요
5. **중요**: 문서에 정보가 없거나 확실하지 않으면 절대 거짓말하지 마세요
6. 모르는 내용은 "제가 잘 모르겠어요. 죄송하지만 직원에게 문의해주세요"라고 답변하세요

매장 문서:
{context}

손님 질문: {query}

직원 답변:"""

            logger.info("="*80)
            logger.info("🤖 [LLM] 응답 생성")
            logger.info("="*80)
            logger.info(f"📝 최종 프롬프트 (길이: {len(prompt)} 문자):")
            logger.info(f"\n{prompt}\n")

            # LLM 응답 생성
            response = self.llm_client.generate(
                model=self.llm_model,
                prompt=prompt
            )

            answer = response['response'].strip()

            # 50자 제한 체크 및 추가 설명 제안
            if len(answer) > 50:
                answer = answer[:50] + "..."
                answer += "\n\n더 자세히 설명해드릴까요?"

            logger.info(f"💬 LLM 응답:\n{answer}")
            logger.info("="*80)

            debug_info = {
                "retrieved_documents": [
                    {
                        "score": doc["score"],
                        "text_preview": doc["text"][:200]
                    }
                    for doc in documents
                ],
                "context_length": len(context),
                "final_prompt": prompt,
                "llm_model": self.llm_model,
                "llm_response": answer
            }

            return answer, debug_info

        except Exception as e:
            logger.error(f"쿼리 오류: {str(e)}")
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}", {"error": str(e)}
