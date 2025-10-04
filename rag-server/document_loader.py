import os
import logging
import tiktoken
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentLoader:
    """마크다운 문서 로더 및 청킹"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # tiktoken 인코더 (토큰 계산용)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def load_markdown(self, file_path: str) -> str:
        """마크다운 파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"문서 로드 완료: {file_path}")
            return content
        except Exception as e:
            logger.error(f"문서 로드 실패: {file_path} - {str(e)}")
            raise

    def chunk_text(self, text: str) -> list[str]:
        """
        텍스트를 토큰 기준으로 청킹

        Args:
            text: 청킹할 텍스트

        Returns:
            청크 리스트
        """
        # 토큰으로 인코딩
        tokens = self.encoder.encode(text)

        chunks = []
        start = 0

        while start < len(tokens):
            # 청크 종료 위치 계산
            end = start + self.chunk_size

            # 청크 추출
            chunk_tokens = tokens[start:end]

            # 토큰을 텍스트로 디코딩
            chunk_text = self.encoder.decode(chunk_tokens)
            chunks.append(chunk_text)

            # 다음 시작 위치 (오버랩 고려)
            start = end - self.chunk_overlap

        logger.info(f"청킹 완료: {len(chunks)}개 청크 생성")
        return chunks

    def load_and_chunk(self, file_path: str) -> list[str]:
        """문서 로드 및 청킹"""
        # 파일이 .md인지 확인
        if not file_path.endswith('.md'):
            raise ValueError("마크다운 파일(.md)만 지원합니다.")

        # 문서 로드
        content = self.load_markdown(file_path)

        # 청킹
        chunks = self.chunk_text(content)

        return chunks
