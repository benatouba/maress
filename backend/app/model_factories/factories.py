from datetime import UTC, datetime

from sqlmodel import Column, DateTime, Field, func


def timestamp_field(*, onupdate_now: bool = False) -> datetime:
    """Create a timestamp field with new Column instance."""
    return Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now() if onupdate_now else None,
        ),
    )
