import os
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """매장 정보 및 리뷰 요약을 MD 문서로 생성"""

    def __init__(self):
        db_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(db_url)
        self.docs_dir = Path("/app/media/documents")
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def generate_store_info_md(self, store_id: int) -> str:
        """
        매장 정보를 MD 파일로 생성

        Returns:
            생성된 파일 경로
        """
        try:
            with self.engine.connect() as conn:
                # 매장 정보 조회
                query = text("""
                    SELECT
                        store_name,
                        scraped_store_name,
                        scraped_category,
                        scraped_description,
                        store_address,
                        scraped_store_address,
                        scraped_directions,
                        owner_phone,
                        scraped_phone,
                        scraped_sns,
                        scraped_etc_info,
                        scraped_intro,
                        scraped_services,
                        naver_store_url
                    FROM stores
                    WHERE id = :store_id
                """)
                result = conn.execute(query, {"store_id": store_id}).fetchone()

                if not result:
                    raise ValueError(f"매장 ID {store_id}를 찾을 수 없습니다.")

                # MD 파일 생성
                store_name = result[0] or result[1]
                file_path = self.docs_dir / f"store_{store_id}_info.md"

                content = f"""# {store_name} - 매장 정보

## 기본 정보

**매장명**: {result[1] or result[0]}
**카테고리**: {result[2] or '정보 없음'}
**설명**: {result[3] or '정보 없음'}

## 위치 및 연락처

**주소**: {result[5] or result[4]}

### 찾아오시는 길
{result[6] or '정보 없음'}

**전화번호**: {result[8] or result[7]}

**SNS**: {result[9] or '정보 없음'}

## 매장 소개

{result[11] or '정보 없음'}

## 서비스 및 편의시설

{result[12] or '정보 없음'}

## 추가 정보

{result[10] or '정보 없음'}

## 네이버 스토어

{result[13] or '정보 없음'}

---
*최종 업데이트: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                logger.info(f"매장 정보 MD 생성 완료: {file_path}")
                return str(file_path)

        except Exception as e:
            logger.error(f"매장 정보 MD 생성 오류: {str(e)}")
            raise

    def generate_review_summary_md(self, store_id: int) -> str:
        """
        리뷰 요약을 MD 파일로 생성

        Returns:
            생성된 파일 경로
        """
        try:
            with self.engine.connect() as conn:
                # 리뷰 요약 조회
                query = text("""
                    SELECT summary_md
                    FROM review_summaries
                    WHERE store_id = :store_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                result = conn.execute(query, {"store_id": store_id}).fetchone()

                if not result or not result[0]:
                    raise ValueError(f"매장 ID {store_id}의 리뷰 요약이 없습니다.")

                # MD 파일 생성
                file_path = self.docs_dir / f"store_{store_id}_reviews.md"

                content = f"""# 고객 리뷰 요약

{result[0]}

---
*최종 업데이트: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                logger.info(f"리뷰 요약 MD 생성 완료: {file_path}")
                return str(file_path)

        except Exception as e:
            logger.error(f"리뷰 요약 MD 생성 오류: {str(e)}")
            raise

    def generate_menu_info_md(self, store_id: int) -> str:
        """
        메뉴 정보를 MD 파일로 생성

        Returns:
            생성된 파일 경로
        """
        try:
            with self.engine.connect() as conn:
                # 메뉴 정보 조회
                query = text("""
                    SELECT
                        menu_name,
                        price,
                        description,
                        recommendation
                    FROM menus
                    WHERE store_id = :store_id
                    ORDER BY id
                """)
                result = conn.execute(query, {"store_id": store_id}).fetchall()

                if not result:
                    logger.warning(f"매장 ID {store_id}의 메뉴 정보가 없습니다.")
                    return None

                # MD 파일 생성
                file_path = self.docs_dir / f"store_{store_id}_menus.md"

                content = "# 메뉴 정보\n\n"

                for menu in result:
                    menu_name = menu[0]
                    price = menu[1]
                    description = menu[2]
                    recommendation = menu[3]

                    content += f"## {menu_name}\n\n"

                    if price:
                        content += f"**가격**: {price}\n\n"

                    if description:
                        content += f"**설명**: {description}\n\n"

                    if recommendation:
                        content += f"**추천**: {recommendation}\n\n"

                    content += "---\n\n"

                content += f"\n*최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                logger.info(f"메뉴 정보 MD 생성 완료: {file_path}")
                return str(file_path)

        except Exception as e:
            logger.error(f"메뉴 정보 MD 생성 오류: {str(e)}")
            raise

    def register_document(self, store_id: int, category: str, doc_path: str):
        """
        생성된 문서를 rag_documents 테이블에 등록

        Args:
            store_id: 매장 ID
            category: customer 또는 owner
            doc_path: 문서 파일 경로
        """
        try:
            with self.engine.connect() as conn:
                # 기존 문서 확인
                check_query = text("""
                    SELECT id FROM rag_documents
                    WHERE store_id = :store_id
                    AND category = :category
                    AND doc_path = :doc_path
                """)
                existing = conn.execute(check_query, {
                    "store_id": store_id,
                    "category": category,
                    "doc_path": doc_path
                }).fetchone()

                if existing:
                    logger.info(f"문서가 이미 등록되어 있습니다: {doc_path}")
                    return

                # 새 문서 등록
                insert_query = text("""
                    INSERT INTO rag_documents (store_id, category, doc_path)
                    VALUES (:store_id, :category, :doc_path)
                """)
                conn.execute(insert_query, {
                    "store_id": store_id,
                    "category": category,
                    "doc_path": doc_path
                })
                conn.commit()

                logger.info(f"문서 등록 완료: {doc_path}")

        except Exception as e:
            logger.error(f"문서 등록 오류: {str(e)}")
            raise

    def generate_all_documents(self, store_id: int) -> dict:
        """
        매장의 모든 문서를 생성하고 등록

        Returns:
            생성된 문서 정보
        """
        generated = {
            "store_id": store_id,
            "documents": []
        }

        try:
            # 1. 매장 정보 (customer용)
            try:
                store_info_path = self.generate_store_info_md(store_id)
                self.register_document(store_id, "customer", store_info_path)
                generated["documents"].append({
                    "type": "store_info",
                    "path": store_info_path,
                    "category": "customer"
                })
            except Exception as e:
                logger.error(f"매장 정보 생성 실패: {str(e)}")

            # 2. 메뉴 정보 (customer용)
            try:
                menu_info_path = self.generate_menu_info_md(store_id)
                if menu_info_path:
                    self.register_document(store_id, "customer", menu_info_path)
                    generated["documents"].append({
                        "type": "menu_info",
                        "path": menu_info_path,
                        "category": "customer"
                    })
            except Exception as e:
                logger.error(f"메뉴 정보 생성 실패: {str(e)}")

            # 3. 리뷰 요약 (customer, owner 둘 다)
            try:
                review_path = self.generate_review_summary_md(store_id)
                self.register_document(store_id, "customer", review_path)
                self.register_document(store_id, "owner", review_path)
                generated["documents"].append({
                    "type": "review_summary",
                    "path": review_path,
                    "category": "customer, owner"
                })
            except Exception as e:
                logger.error(f"리뷰 요약 생성 실패: {str(e)}")

            return generated

        except Exception as e:
            logger.error(f"문서 생성 오류: {str(e)}")
            raise
