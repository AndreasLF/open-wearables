from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

# Hevy body measurements are one row per calendar day. Keys are the API field names.
BODY_SERIES: dict[str, SeriesType] = {
    "weight_kg": SeriesType.weight,
    "fat_percent": SeriesType.body_fat_percentage,
    "lean_mass_kg": SeriesType.lean_body_mass,
    "waist": SeriesType.waist_circumference,
}

TIMESERIES: frozenset[SeriesType] = frozenset(BODY_SERIES.values())

WORKOUT_FIELDS: frozenset[str] = frozenset(
    {
        "label",
        "moving_time_seconds",
        "distance",
        "segments",
    }
)

SLEEP_FIELDS: frozenset[str] = frozenset()
HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()

# The workout title key matches an EventRecordDetail field name, so it lives here.
# workouts.py is scanned for quoted detail-field names, and this string would look like one.
WORKOUT_TITLE_KEY = "title"
