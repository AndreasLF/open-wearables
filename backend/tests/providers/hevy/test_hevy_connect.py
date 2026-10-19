"""Connecting Hevy stores the key only after Hevy accepts it."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserConnection
from app.schemas.enums import ProviderName
from app.services.providers.hevy.client import HevyRejectedKeyError
from app.services.providers.hevy.strategy import HevyStrategy
from tests.factories import UserFactory


def test_rejected_key_does_not_create_a_connection(client: TestClient, db: Session) -> None:
    user = UserFactory()
    with patch("app.services.providers.hevy.connect.fetch_profile", side_effect=HevyRejectedKeyError()):
        response = client.post(
            "/api/v1/oauth/hevy/api-key",
            json={"user_id": str(user.id), "api_key": "not-a-key"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Hevy rejected that API key."
    assert db.query(UserConnection).filter_by(user_id=user.id, provider=ProviderName.HEVY.value).one_or_none() is None


def test_accepted_key_is_stored_and_a_backfill_is_queued(client: TestClient, db: Session) -> None:
    user = UserFactory()
    delay = MagicMock()
    with (
        patch(
            "app.services.providers.hevy.connect.fetch_profile",
            return_value={"id": "hevy-user", "username": "ada"},
        ),
        patch("app.services.providers.hevy.connect.HevyStrategy.start_historical_sync", delay),
    ):
        response = client.post(
            "/api/v1/oauth/hevy/api-key",
            json={"user_id": str(user.id), "api_key": "  secret-key  "},
        )

    assert response.status_code == 200
    assert response.json() == {"provider": "hevy", "connected": True}
    connection = db.query(UserConnection).filter_by(user_id=user.id, provider=ProviderName.HEVY.value).one()
    assert connection.access_token == "secret-key"
    assert connection.provider_user_id == "hevy-user"
    assert connection.provider_username == "ada"
    assert connection.token_expires_at is None
    delay.assert_called_once()
    assert delay.call_args.args[0] == user.id


def test_historical_sync_starts_at_the_beginning_of_the_log() -> None:
    send = MagicMock()
    send.return_value.id = "task-1"
    with patch("app.services.providers.hevy.strategy.celery_app.send_task", send):
        result = HevyStrategy().start_historical_sync(uuid4(), days=30)

    assert send.call_args.kwargs["kwargs"]["start_date"].startswith("1970-01-01")
    assert send.call_args.kwargs["kwargs"]["is_historical"] is True
    assert send.call_args.kwargs["kwargs"]["providers"] == ["hevy"]
    assert result.days is None


def test_oauth_provider_refuses_an_api_key(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/v1/oauth/garmin/api-key",
        json={"user_id": str(uuid4()), "api_key": "secret-key"},
    )
    assert response.status_code == 400
    assert "does not accept an API key" in response.json()["detail"]
