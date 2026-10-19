"""Hevy payloads map onto the few unified fields the workout log actually has."""

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.enums import SeriesType, WorkoutType
from app.services.providers.hevy.data_247 import samples_from_measurement
from app.services.providers.hevy.workouts import normalize_workout


def test_workout_keeps_title_duration_distance_and_sets() -> None:
    user_id = uuid4()
    record, detail = normalize_workout(
        {
            "id": "w-1",
            "title": "  Leg day  ",
            "start_time": "2026-10-19T12:00:00Z",
            "end_time": "2026-10-19T13:00:00Z",
            "exercises": [
                {
                    "title": "Back Squat",
                    "notes": None,
                    "exercise_template_id": "79D0BB3A",
                    "sets": [
                        {"type": "normal", "weight_kg": 100, "reps": 5, "distance_meters": None, "rpe": 8},
                        {"type": "normal", "weight_kg": None, "reps": None, "distance_meters": 400},
                    ],
                }
            ],
        },
        user_id,
    ) or (None, None)

    assert record is not None
    assert detail is not None
    assert record.type == WorkoutType.STRENGTH_TRAINING.value
    assert record.external_id == "w-1"
    assert record.user_id == user_id
    assert record.duration_seconds == 3600
    assert detail.label == "Leg day"
    assert detail.moving_time_seconds == 3600
    assert detail.distance == 400
    assert detail.segments is not None
    assert detail.segments[0]["exercise"] == "Back Squat"
    assert detail.segments[0]["sets"][0]["weight_kg"] == 100
    assert detail.heart_rate_avg is None
    assert detail.energy_burned is None


def test_workout_without_an_interval_is_skipped() -> None:
    assert normalize_workout({"id": "w-2", "title": "Nope"}, uuid4()) is None


def test_body_measurement_emits_only_populated_series() -> None:
    user_id = uuid4()
    samples = samples_from_measurement(
        {"date": "2026-10-19", "weight_kg": 82.5, "fat_percent": None, "lean_mass_kg": 64, "waist": 84},
        user_id,
    )

    by_type = {sample.series_type: sample for sample in samples}
    assert set(by_type) == {SeriesType.weight, SeriesType.lean_body_mass, SeriesType.waist_circumference}
    assert by_type[SeriesType.weight].value == 82.5
    assert by_type[SeriesType.weight].recorded_at == datetime(2026, 10, 19, tzinfo=timezone.utc)
    assert by_type[SeriesType.weight].external_id == "hevy:2026-10-19:weight"
