from celery import Celery

from app.core.config import settings

# Initialize Celery app
celery_app = Celery("modifai")

# Configure Celery
celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task result expiration in seconds (24 hours)
    result_expires=86400,
)

# Autodiscover tasks
celery_app.autodiscover_tasks(["app.worker"])
