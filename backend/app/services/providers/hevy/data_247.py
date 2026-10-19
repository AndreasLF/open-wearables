"""Hevy body measurements as daily time-series samples.

Neck, chest, arms, hips, thighs, and calves are on the Hevy row and have no
series type here, so they are left on the provider.
"""

from datetime import datetime, timezone
from typing import Any, NoReturn
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.providers.hevy.client import iter_collection
from app.services.providers.hevy.coverage import BODY_SERIES
from app.services.providers.sync_247_result import Sync247Result
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.timeseries_service import timeseries_service


def _day(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def samples_from_measurement(raw: dict[str, Any], user_id: UUID) -> list[TimeSeriesSampleCreate]:
    """One sample per populated Hevy field that has a series type."""
    date_raw = raw.get("date")
    if not isinstance(date_raw, str):
        return []
    recorded_at = _day(date_raw)
    if recorded_at is None:
        return []

    samples: list[TimeSeriesSampleCreate] = []
    for field, series_type in BODY_SERIES.items():
        value = raw.get(field)
        if not isinstance(value, int | float) or isinstance(value, bool):
            continue
        samples.append(
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                recorded_at=recorded_at,
                value=value,
                series_type=series_type,
                external_id=f"hevy:{date_raw}:{series_type.value}",
                source="hevy",
                provider=ProviderName.HEVY.value,
            )
        )
    return samples


class Hevy247Data(Base247DataTemplate):
    """Body measurements only. Hevy has no sleep, recovery, or all-day activity."""

    def __init__(
        self,
        connection_repo: UserConnectionRepository,
        provider_name: str,
        api_base_url: str,
    ) -> None:
        super().__init__(provider_name=provider_name, api_base_url=api_base_url, oauth=None)  # ty: ignore[invalid-argument-type]
        self.connection_repo = connection_repo

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        is_first_sync: bool = False,
    ) -> Sync247Result:
        start_dt, end_dt = self.resolve_window(start_time, end_time)
        run = self.sync_run(db, user_id)
        with run.step("body_measurements", commit=True) as step:
            step.record(self._save_body(db, user_id, start_dt, end_dt))
        run.log_summary()
        return run.result

    def _save_body(self, db: DbSession, user_id: UUID, start: datetime, end: datetime) -> WriteCounts | int:
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
        if connection is None or not connection.access_token:
            raise ValueError(f"User {user_id} has no Hevy API key")

        samples: list[TimeSeriesSampleCreate] = []
        for raw in iter_collection(connection.access_token, "/v1/body_measurements", "body_measurements"):
            for sample in samples_from_measurement(raw, user_id):
                if start.date() <= sample.recorded_at.date() <= end.date():
                    samples.append(sample)
        if not samples:
            return 0
        return timeseries_service.bulk_create_samples(db, samples)

    def _unsupported(self, feature: str) -> NoReturn:
        raise NotImplementedError(f"Hevy 24/7 data uses load_and_save_all(); {feature} is not used")

    def get_sleep_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_sleep_data")

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_sleep")

    def get_recovery_data(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_recovery_data")

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_recovery")

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_activity_samples")

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        self._unsupported("normalize_activity_samples")

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        self._unsupported("get_daily_activity_statistics")

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_daily_activity")
