import os
import logging
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

logger = logging.getLogger(__name__)


class MilvusVectorStore:
    """Milvus 벡터 스토어"""

    def __init__(self, collection_name: str = "wafl_documents", dimension: int = 1024):
        self.collection_name = collection_name
        self.dimension = dimension
        self.collection = None

        # Milvus 연결
        self._connect()
        # 컬렉션 초기화
        self._init_collection()

    def _connect(self):
        """Milvus 서버 연결"""
        host = os.getenv("MILVUS_HOST", "localhost")
        port = os.getenv("MILVUS_PORT", "19530")

        try:
            connections.connect(
                alias="default",
                host=host,
                port=port
            )
            logger.info(f"Milvus 연결 성공: {host}:{port}")
        except Exception as e:
            logger.error(f"Milvus 연결 실패: {str(e)}")
            raise

    def _init_collection(self):
        """컬렉션 초기화"""
        # 컬렉션이 이미 존재하면 로드
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.info(f"기존 컬렉션 로드: {self.collection_name}")
            return

        # 스키마 정의
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="store_id", dtype=DataType.INT64),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]

        schema = CollectionSchema(fields=fields, description="WAFL 문서 벡터 스토어")

        # 컬렉션 생성
        self.collection = Collection(name=self.collection_name, schema=schema)

        # 인덱스 생성
        index_params = {
            "metric_type": "IP",  # Inner Product (코사인 유사도)
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        self.collection.load()

        logger.info(f"새 컬렉션 생성: {self.collection_name}")

    def insert(self, texts: list[str], embeddings: list[list[float]],
               store_id: int, category: str):
        """문서 삽입"""
        try:
            data = [
                [store_id] * len(texts),  # store_id
                [category] * len(texts),  # category
                texts,                    # text
                embeddings                # embedding
            ]

            self.collection.insert(data)
            self.collection.flush()

            logger.info(f"문서 삽입 완료: {len(texts)}개 (store_id={store_id}, category={category})")

        except Exception as e:
            logger.error(f"문서 삽입 오류: {str(e)}")
            raise

    def search(self, query_embedding: list[float], store_id: int,
               category: str, top_k: int = 5) -> list[dict]:
        """유사 문서 검색"""
        try:
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}

            # 검색 필터: store_id와 category 일치
            expr = f"store_id == {store_id} && category == '{category}'"

            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["text", "store_id", "category"]
            )

            # 결과 포맷팅
            documents = []
            for hits in results:
                for hit in hits:
                    documents.append({
                        "text": hit.entity.get("text"),
                        "score": hit.score,
                        "store_id": hit.entity.get("store_id"),
                        "category": hit.entity.get("category")
                    })

            logger.info(f"검색 완료: {len(documents)}개 문서 (store_id={store_id}, category={category})")
            return documents

        except Exception as e:
            logger.error(f"검색 오류: {str(e)}")
            return []

    def delete_by_store(self, store_id: int, category: str):
        """특정 매장의 문서 삭제"""
        try:
            expr = f"store_id == {store_id} && category == '{category}'"
            self.collection.delete(expr)
            logger.info(f"문서 삭제 완료: store_id={store_id}, category={category}")
        except Exception as e:
            logger.error(f"문서 삭제 오류: {str(e)}")
            raise
