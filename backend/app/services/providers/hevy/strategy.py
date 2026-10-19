from datetime import datetime, timezone
from uuid import UUID

from celery import current_app as celery_app

from app.constants.celery_tasks import CeleryTask
from app.schemas.auth import ConnectMethod
from app.services.providers.base_strategy import (
    BaseProviderStrategy,
    HistoricalSyncResult,
    ProviderCapabilities,
    ProviderCoverage,
)
from app.services.providers.hevy.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.hevy.data_247 import Hevy247Data
from app.services.providers.hevy.workouts import HevyWorkouts


class HevyStrategy(BaseProviderStrategy):
    """Hevy workout log. The user pastes an API key; there is no OAuth redirect."""

    def __init__(self) -> None:
        super().__init__()
        self.oauth = None
        self.workouts = HevyWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )
        self.data_247 = Hevy247Data(
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
        )

    @property
    def name(self) -> str:
        return "hevy"

    @property
    def api_base_url(self) -> str:
        return "https://api.hevyapp.com"

    @property
    def connect_method(self) -> ConnectMethod:
        return ConnectMethod.API_KEY

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(rest_pull=True)

    def start_historical_sync(self, user_id: UUID, days: int) -> HistoricalSyncResult:
        """Pull the whole log. Hevy has no date filter and no history cap, so `days` is ignored."""
        end = datetime.now(timezone.utc)
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        task = celery_app.send_task(
            CeleryTask.SYNC_VENDOR_DATA,
            kwargs={
                "user_id": str(user_id),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "providers": [self.name],
                "is_historical": True,
            },
        )
        return HistoricalSyncResult(
            task_id=task.id,
            method="pull_api",
            message=f"Historical sync queued for the full {self.name} log.",
            days=None,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )
