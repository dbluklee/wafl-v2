import logging
from FlagEmbedding import BGEM3FlagModel

logger = logging.getLogger(__name__)


class BGE_M3_Embeddings:
    """BGE-M3 임베딩 모델"""

    def __init__(self):
        logger.info("BGE-M3 모델 로딩 중...")
        self.model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
        logger.info("BGE-M3 모델 로딩 완료")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """문서 리스트를 임베딩"""
        embeddings = self.model.encode(
            texts,
            batch_size=12,
            max_length=1024
        )['dense_vecs']
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """쿼리 텍스트를 임베딩"""
        embedding = self.model.encode(
            [text],
            batch_size=1,
            max_length=1024
        )['dense_vecs']
        return embedding[0].tolist()

    @property
    def dimension(self) -> int:
        """임베딩 차원 수"""
        return 1024  # BGE-M3의 임베딩 차원
