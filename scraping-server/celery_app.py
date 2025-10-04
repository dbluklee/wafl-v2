from celery import Celery
import os

# Redis URL 설정
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:56379/0")

# Celery 앱 생성
celery = Celery(
    'scraping_worker',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks.scraping_tasks']
)

# Celery 설정
celery.conf.update(
    # 태스크 직렬화
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,

    # 태스크 라우팅 - 모든 작업을 기본 큐로
    task_routes={
        'tasks.scraping_tasks.scrape_store_data': {'queue': 'celery'},
        'tasks.scraping_tasks.generate_review_summary': {'queue': 'celery'},
    },

    # 워커 설정
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,

    # 태스크 결과 만료 시간 (1시간)
    result_expires=3600,

    # 태스크 타임아웃 (30분)
    task_time_limit=1800,
    task_soft_time_limit=1500,

    # 재시도 설정
    task_default_retry_delay=60,
    task_max_retries=3,
)