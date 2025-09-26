from celery import Celery

from app.core.config import settings

celery = Celery(
    "maress_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
celery.conf.update(
    imports=("app.tasks.extract",),  # explicit imports
)

