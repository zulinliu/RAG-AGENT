from celery import Celery

from rag_qa.core.config import settings

app = Celery(
    "rag_qa",
    broker=settings.redis.url,
    backend=settings.redis.url,
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "rag_qa.workers.sync_worker.sync_datasource_task": {"queue": "sync"},
    },
    task_default_queue="default",
)
