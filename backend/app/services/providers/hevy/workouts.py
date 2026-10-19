"""Map a Hevy workout (exercises and sets) onto one workout record.

The session title, duration, summed set distance, and the set list are the
fields the unified workout record can hold. Heart rate, calories, and steps
are not in the Hevy workout object.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName, WorkoutType
from app.schemas.model_crud.activities import EventRecordCreate, EventRecordDetailCreate
from app.services.event_record_service import event_record_service
from app.services.providers.hevy.client import iter_collection
from app.services.providers.hevy.coverage import WORKOUT_TITLE_KEY
from app.services.providers.templates.base_workouts import BaseWorkoutsTemplate
from app.utils.structured_logging import log_structured


def parse_time(value: str) -> datetime:
    """Hevy sends ISO-8601 timestamps, sometimes with a trailing Z."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _set_distance_meters(raw: dict[str, Any]) -> Decimal:
    """Sum distance_meters across every set. Sets without a distance contribute nothing."""
    total = Decimal(0)
    for exercise in raw.get("exercises") or []:
        if not isinstance(exercise, dict):
            continue
        for one_set in exercise.get("sets") or []:
            if not isinstance(one_set, dict):
                continue
            meters = one_set.get("distance_meters")
            if isinstance(meters, int | float) and not isinstance(meters, bool):
                total += Decimal(str(meters))
    return total


def _segments(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Exercises and their sets, kept as Hevy sent them so reps and weight survive."""
    segments: list[dict[str, Any]] = []
    for exercise in raw.get("exercises") or []:
        if not isinstance(exercise, dict):
            continue
        sets = [one_set for one_set in (exercise.get("sets") or []) if isinstance(one_set, dict)]
        segments.append(
            {
                "exercise": exercise.get(WORKOUT_TITLE_KEY),
                "notes": exercise.get("notes"),
                "exercise_template_id": exercise.get("exercise_template_id"),
                "sets": sets,
            }
        )
    return segments


def normalize_workout(raw: dict[str, Any], user_id: UUID) -> tuple[EventRecordCreate, EventRecordDetailCreate] | None:
    """Build a workout record, or None when the payload has no usable interval."""
    start_raw = raw.get("start_time")
    end_raw = raw.get("end_time")
    workout_id = raw.get("id")
    if not isinstance(start_raw, str) or not isinstance(end_raw, str) or workout_id is None:
        return None

    start = parse_time(start_raw)
    end = parse_time(end_raw)
    moving = max(int((end - start).total_seconds()), 0)
    record_id = uuid4()
    title = raw.get(WORKOUT_TITLE_KEY)
    label = title.strip() if isinstance(title, str) and title.strip() else None
    distance = _set_distance_meters(raw)

    detail = EventRecordDetailCreate(
        record_id=record_id,
        label=label,
        moving_time_seconds=moving,
        distance=distance or None,
        segments=_segments(raw) or None,
    )
    record = EventRecordCreate(
        id=record_id,
        category="workout",
        type=WorkoutType.STRENGTH_TRAINING.value,
        source_name="Hevy",
        duration_seconds=moving,
        start_datetime=start,
        end_datetime=end,
        external_id=str(workout_id),
        source="hevy",
        provider=ProviderName.HEVY.value,
        user_id=user_id,
    )
    return record, detail


class HevyWorkouts(BaseWorkoutsTemplate):
    """Pull Hevy workouts. The list is newest-first and cannot be filtered by date."""

    def __init__(
        self,
        workout_repo: Any,
        connection_repo: UserConnectionRepository,
        provider_name: str,
        api_base_url: str,
    ) -> None:
        super().__init__(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name=provider_name,
            api_base_url=api_base_url,
            oauth=None,  # ty: ignore[invalid-argument-type]
        )

    def _api_key(self, db: DbSession, user_id: UUID) -> str:
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
        if connection is None or not connection.access_token:
            raise ValueError(f"User {user_id} has no Hevy API key")
        return connection.access_token

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Page until a workout starts before the window. Later pages are older."""
        api_key = self._api_key(db, user_id)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        collected: list[dict[str, Any]] = []
        for raw in iter_collection(api_key, "/v1/workouts", "workouts"):
            start_raw = raw.get("start_time")
            if not isinstance(start_raw, str):
                continue
            start = parse_time(start_raw)
            if start < start_date:
                break
            if start <= end_date:
                collected.append(raw)
        return collected

    def _normalize_workout(
        self,
        raw_workout: Any,
        user_id: UUID,
    ) -> tuple[EventRecordCreate, EventRecordDetailCreate]:
        normalized = normalize_workout(raw_workout, user_id)
        if normalized is None:
            raise ValueError("Hevy workout is missing an id or a start and end time")
        return normalized

    def load_data(self, db: DbSession, user_id: UUID, **kwargs: Any) -> int:
        start = kwargs.get("start") or kwargs.get("start_date")
        end = kwargs.get("end") or kwargs.get("end_date")
        start_dt = parse_time(start) if isinstance(start, str) else start
        end_dt = parse_time(end) if isinstance(end, str) else end
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
            raise ValueError("Hevy workout sync requires a start and end")

        saved = 0
        for raw in self.get_workouts(db, user_id, start_dt, end_dt):
            normalized = normalize_workout(raw, user_id)
            if normalized is None:
                continue
            record, detail = normalized
            if record.external_id and self.workout_repo.get_by_external_id(
                db, user_id, record.external_id, provider=ProviderName.HEVY.value
            ):
                continue
            created = event_record_service.create(db, record)
            event_record_service.create_detail(db, detail.model_copy(update={"record_id": created.id}))
            saved += 1

        log_structured(
            self.logger,
            "info",
            "Saved Hevy workouts",
            provider="hevy",
            action="hevy_workouts_saved",
            user_id=str(user_id),
            saved=saved,
        )
        return saved
