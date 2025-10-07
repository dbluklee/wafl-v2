"""
암호화 유틸리티
AES-256-GCM을 사용한 대화 내용 암호화/복호화
"""

import os
import base64
import hashlib
import logging
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionManager:
    """대화 내용 암호화 관리자"""

    def __init__(self, key_id: str = "key-001"):
        """
        Args:
            key_id: 암호화 키 ID (키 로테이션용)
        """
        self.key_id = key_id
        self._key = self._load_encryption_key()
        self.aesgcm = AESGCM(self._key)

    def _load_encryption_key(self) -> bytes:
        """
        환경변수에서 암호화 키 로드
        키가 없으면 경고 후 기본값 사용 (개발 환경용)
        """
        key_str = os.getenv("CONVERSATION_ENCRYPTION_KEY")

        if not key_str:
            logger.warning("⚠️  CONVERSATION_ENCRYPTION_KEY 환경변수가 설정되지 않았습니다!")
            logger.warning("⚠️  개발용 기본 키를 사용합니다. 운영 환경에서는 반드시 설정하세요!")
            key_str = "dev-default-key-please-change-in-production!!"

        # 키를 32바이트로 해싱 (AES-256 요구사항)
        key_bytes = hashlib.sha256(key_str.encode()).digest()
        return key_bytes

    def encrypt(self, plaintext: str) -> str:
        """
        텍스트를 AES-256-GCM으로 암호화

        Args:
            plaintext: 암호화할 원본 텍스트

        Returns:
            Base64로 인코딩된 암호화 텍스트 (nonce + ciphertext + tag)
        """
        try:
            # 12바이트 랜덤 nonce 생성
            nonce = os.urandom(12)

            # 암호화 (GCM 모드는 자동으로 인증 태그 생성)
            ciphertext = self.aesgcm.encrypt(
                nonce,
                plaintext.encode('utf-8'),
                None  # 추가 인증 데이터 (필요시 사용)
            )

            # nonce + ciphertext를 함께 저장 (복호화시 필요)
            encrypted_data = nonce + ciphertext

            # Base64 인코딩하여 DB에 저장 가능한 형태로 변환
            return base64.b64encode(encrypted_data).decode('utf-8')

        except Exception as e:
            logger.error(f"암호화 오류: {str(e)}")
            raise

    def decrypt(self, encrypted_text: str) -> str:
        """
        AES-256-GCM으로 암호화된 텍스트를 복호화

        Args:
            encrypted_text: Base64로 인코딩된 암호화 텍스트

        Returns:
            복호화된 원본 텍스트
        """
        try:
            # Base64 디코딩
            encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))

            # nonce와 ciphertext 분리
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]

            # 복호화 및 인증 태그 검증
            plaintext_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext_bytes.decode('utf-8')

        except Exception as e:
            logger.error(f"복호화 오류: {str(e)}")
            raise

    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """
        민감한 데이터를 SHA-256으로 해싱
        (IP 주소, User Agent 등 식별 가능 정보)

        Args:
            data: 해싱할 데이터

        Returns:
            16진수 해시 문자열
        """
        return hashlib.sha256(data.encode()).hexdigest()

    def get_key_hash(self) -> str:
        """
        현재 사용 중인 키의 해시값 반환 (키 검증용)

        Returns:
            키의 SHA-256 해시
        """
        return hashlib.sha256(self._key).hexdigest()


# 전역 암호화 관리자 인스턴스 (싱글톤 패턴)
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """
    전역 암호화 관리자 인스턴스 반환 (싱글톤)
    """
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


# 편의 함수들
def encrypt_message(plaintext: str) -> Tuple[str, str]:
    """
    메시지 암호화 편의 함수

    Args:
        plaintext: 암호화할 텍스트

    Returns:
        (암호화된 텍스트, 키 ID)
    """
    manager = get_encryption_manager()
    encrypted = manager.encrypt(plaintext)
    return encrypted, manager.key_id


def decrypt_message(encrypted_text: str) -> str:
    """
    메시지 복호화 편의 함수

    Args:
        encrypted_text: 암호화된 텍스트

    Returns:
        복호화된 원본 텍스트
    """
    manager = get_encryption_manager()
    return manager.decrypt(encrypted_text)


def hash_ip_address(ip: str) -> str:
    """IP 주소 해싱"""
    return EncryptionManager.hash_sensitive_data(ip)


def hash_user_agent(user_agent: str) -> str:
    """User Agent 해싱"""
    return EncryptionManager.hash_sensitive_data(user_agent)


if __name__ == "__main__":
    # 테스트
    print("=" * 80)
    print("암호화 유틸리티 테스트")
    print("=" * 80)

    # 암호화/복호화 테스트
    test_message = "안녕하세요! 영업시간이 어떻게 되나요?"
    print(f"\n원본 메시지: {test_message}")

    encrypted, key_id = encrypt_message(test_message)
    print(f"암호화된 메시지: {encrypted[:50]}...")
    print(f"사용된 키 ID: {key_id}")

    decrypted = decrypt_message(encrypted)
    print(f"복호화된 메시지: {decrypted}")

    assert test_message == decrypted, "암호화/복호화 실패!"
    print("\n✅ 암호화/복호화 테스트 성공!")

    # 해싱 테스트
    test_ip = "192.168.1.100"
    hashed_ip = hash_ip_address(test_ip)
    print(f"\n원본 IP: {test_ip}")
    print(f"해시된 IP: {hashed_ip}")

    # 키 해시
    manager = get_encryption_manager()
    print(f"\n현재 키 해시: {manager.get_key_hash()}")

    print("\n" + "=" * 80)
    print("모든 테스트 완료!")
    print("=" * 80)
