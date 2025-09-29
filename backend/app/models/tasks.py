import uuid

from sqlmodel import Field, SQLModel

from app.models.items import ItemPublic
from maress_types import CeleryState, InitialTaskState


class TaskRef(SQLModel):
    """Model representing a reference to an asynchronous task.

    The task can be discovered and handled by celery workers.
    """

    # Target domain entity the task operates on
    item_id: uuid.UUID = Field(description="Target Item ID")
    # Celery AsyncResult.id
    task_id: str = Field(description="Celery task identifier")
    # Initial server-side assessment at enqueue time
    status: InitialTaskState = Field(
        default="queued",
        description="Initial enqueue assessment for 202 responses",
    )
    # Optional per-task note (e.g., reason when skipped)
    message: str | None = Field(default=None, description="Optional reason")


class TasksAccepted(SQLModel):
    """Model representing a batch of accepted tasks."""

    data: list[TaskRef]
    count: int


class TaskStatus(SQLModel):
    """Model representing the status of an asynchronous task."""

    task_id: str = Field(description="Celery task identifier")
    task_status: CeleryState = Field(description="Celery task state")
    task_result: ItemPublic | None = Field(
        default=None,
        description="Result payload if available; omitted/None in most states",
    )
