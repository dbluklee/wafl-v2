import requests
import os
import hashlib
from PIL import Image
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ImageDownloader:
    def __init__(self, base_path="/app/media/images"):
        self.base_path = base_path

    def download_and_save_image(self, image_url, store_id, menu_id=None, image_index=1):
        """
        이미지 다운로드 및 저장

        Args:
            image_url (str): 이미지 URL
            store_id (str): 매장 ID
            menu_id (str, optional): 메뉴 ID
            image_index (int): 이미지 순서

        Returns:
            str: 저장된 파일 경로 또는 None
        """
        try:
            # 이미지 다운로드
            response = requests.get(image_url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()

            # 디렉토리 생성
            if menu_id:
                store_dir = os.path.join(self.base_path, "stores", str(store_id), "menus")
            else:
                store_dir = os.path.join(self.base_path, "stores", str(store_id), "profile")

            os.makedirs(store_dir, exist_ok=True)

            # 파일명 생성 (중복 방지를 위한 해시값 포함)
            file_hash = hashlib.md5(response.content).hexdigest()[:8]

            # URL에서 확장자 추출
            parsed_url = urlparse(image_url)
            file_ext = os.path.splitext(parsed_url.path)[-1].lower()
            if not file_ext or file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                file_ext = '.jpg'

            if menu_id:
                filename = f"{menu_id}_{image_index}_{file_hash}{file_ext}"
            else:
                filename = f"profile_{image_index}_{file_hash}{file_ext}"

            file_path = os.path.join(store_dir, filename)

            # 이미지 저장
            with open(file_path, 'wb') as f:
                f.write(response.content)

            # 이미지 최적화
            optimized_path = self.optimize_image(file_path)

            logger.info(f"이미지 저장 완료: {optimized_path}")
            return optimized_path

        except Exception as e:
            logger.error(f"이미지 다운로드 실패 ({image_url}): {e}")
            return None

    def optimize_image(self, file_path, max_width=800, quality=85):
        """
        이미지 최적화 (리사이징 및 압축)

        Args:
            file_path (str): 이미지 파일 경로
            max_width (int): 최대 너비
            quality (int): JPEG 품질

        Returns:
            str: 최적화된 파일 경로
        """
        try:
            with Image.open(file_path) as img:
                # 이미지 리사이징
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                # RGBA나 P 모드를 RGB로 변환
                if img.mode in ('RGBA', 'P'):
                    # 투명한 배경을 흰색으로 변환
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background

                # JPEG로 저장 (품질 최적화)
                optimized_path = file_path
                if not file_path.lower().endswith('.jpg'):
                    optimized_path = os.path.splitext(file_path)[0] + '.jpg'
                    # 원본 파일 삭제
                    if optimized_path != file_path:
                        os.remove(file_path)

                img.save(optimized_path, 'JPEG', quality=quality, optimize=True)

                logger.info(f"이미지 최적화 완료: {optimized_path}")
                return optimized_path

        except Exception as e:
            logger.error(f"이미지 최적화 실패 ({file_path}): {e}")
            # 최적화 실패 시 원본 파일 경로 반환
            return file_path

    def get_image_url_from_media_path(self, file_path):
        """
        로컬 파일 경로를 웹 URL로 변환

        Args:
            file_path (str): 로컬 파일 경로

        Returns:
            str: 웹 접근 가능한 URL
        """
        if not file_path:
            return None

        # /app/media를 /media로 변환
        if file_path.startswith('/app/media'):
            return file_path.replace('/app/media', '/media')
        elif file_path.startswith(self.base_path):
            return file_path.replace(self.base_path, '/media/images')

        return file_path