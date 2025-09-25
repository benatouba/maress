from unittest.mock import MagicMock, patch

from sqlmodel import select

from app.tests_pre_start import init, logger


def test_init_successful_connection() -> None:
    engine_mock = MagicMock()

    session_mock = MagicMock()
    session_mock.exec = MagicMock(return_value=True)
    session_mock.__enter__.return_value = session_mock  # pyright: ignore[reportAny]
    session_mock.__exit__.return_value = None  # pyright: ignore[reportAny]

    with (
        patch("tests_pre_start.Session", return_value=session_mock),
        patch.object(logger, "info"),
        patch.object(logger, "error"),
        patch.object(logger, "warn"),
    ):
        try:
            init(engine_mock)
            connection_successful = True
        except Exception:
            connection_successful = False

        assert (
            connection_successful
        ), "The database connection should be successful and not raise an exception."

        session_mock.exec.assert_called_once()
        called = str(session_mock.exec.call_args[0][0])
        assert called == str(select(1)), f"Expected select(1), received: {called}"
