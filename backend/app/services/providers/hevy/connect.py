"""Store a Hevy API key as the connection credential and queue a backfill.

The pairing page posts the key here. Hevy has no consent screen for third
parties, so the key the person created in Hevy settings is the consent.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.database import DbSession
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName
from app.schemas.model_crud.user_management.user_connection import UserConnectionCreate
from app.services.outgoing_webhooks.events import on_connection_created
from app.services.providers.hevy.client import HevyRejectedKeyError, fetch_profile
from app.services.providers.hevy.strategy import HevyStrategy
from app.services.user_connection_service import user_connection_service


def _profile_identity(profile: dict) -> tuple[str | None, str | None]:
    raw_id = profile.get("id") or profile.get("user_id")
    raw_name = profile.get("username") or profile.get("name")
    user_id = str(raw_id) if raw_id else None
    username = str(raw_name) if raw_name else None
    return user_id, username


def connect_api_key(db: DbSession, user_id: UUID, api_key: str) -> None:
    """Validate the key with Hevy, save it on the user's connection, and backfill."""
    strategy = HevyStrategy()
    if strategy.user_repo.get(db, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    key = api_key.strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paste the API key from Hevy.")

    try:
        profile = fetch_profile(key)
    except HevyRejectedKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hevy rejected that API key.",
        ) from exc

    provider_user_id, username = _profile_identity(profile)
    existing = strategy.connection_repo.get_by_user_and_provider(db, user_id, ProviderName.HEVY.value)
    now = datetime.now(timezone.utc)

    if existing is None:
        created = strategy.connection_repo.create(
            db,
            UserConnectionCreate(
                user_id=user_id,
                provider=ProviderName.HEVY.value,
                provider_user_id=provider_user_id,
                provider_username=username,
                access_token=key,
                token_expires_at=None,
                status=ConnectionStatus.ACTIVE,
            ),
        )
        if created is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store the Hevy connection.",
            )
        on_connection_created(
            user_id=user_id,
            provider=ProviderName.HEVY.value,
            connection_id=created.id,
            connected_at=created.created_at.isoformat(),
        )
    else:
        was_inactive = existing.status != ConnectionStatus.ACTIVE
        existing.access_token = key
        existing.refresh_token = None
        existing.token_expires_at = None
        existing.status = ConnectionStatus.ACTIVE
        existing.updated_at = now
        if provider_user_id:
            existing.provider_user_id = provider_user_id
        if username:
            existing.provider_username = username
        db.add(existing)
        db.commit()
        db.refresh(existing)
        if was_inactive:
            on_connection_created(
                user_id=user_id,
                provider=ProviderName.HEVY.value,
                connection_id=existing.id,
                connected_at=now.isoformat(),
            )

    user_connection_service.stamp_last_synced_at(db, user_id, ProviderName.HEVY.value)

    if settings.historical_sync_on_connect:
        strategy.start_historical_sync(user_id, days=1)
