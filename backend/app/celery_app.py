from celery import Celery

import app.nlp  # noqa: F401
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
    imports=(
        "app.tasks.extract",
        "app.tasks.download",
    ),
)

# Import tasks to ensure they are registered with Celery
# This must happen after celery configuration
from app.tasks.download import download_attachments_task  # noqa: E402, F401
from app.tasks.extract import extract_study_site_task  # noqa: E402, F401
