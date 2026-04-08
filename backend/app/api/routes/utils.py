import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.core.config import settings
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])
logger = logging.getLogger(__name__)


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr | None = None) -> Message:
    """Test emails."""
    recipient = email_to or settings.EMAIL_TEST_USER
    email_data = generate_test_email(email_to=str(recipient))
    try:
        send_email(
            email_to=str(recipient),
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as exc:
        logger.exception("Failed to send test email to %s", recipient)
        raise HTTPException(status_code=502, detail=f"Failed to send test email: {exc!s}") from exc
    return Message(message=f"Test email sent to {recipient}")


@router.get("/health-check/")
async def health_check() -> bool:
    return True
