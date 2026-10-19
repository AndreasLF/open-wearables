import { formatDistance, formatDuration, showDecimal } from '$lib/utils/format';
import { humanise } from '$lib/utils/text';

/** One line of a strength exercise, ready to render. */
export type StrengthSet = {
	label: string;
	detail: string;
};

/** An exercise whose sets were stored on the workout, as Hevy sends them. */
export type StrengthExercise = {
	name: string;
	notes: string | null;
	sets: StrengthSet[];
};

const numberOrNull = (value: unknown): number | null =>
	typeof value === 'number' && Number.isFinite(value) ? value : null;

const textOrNull = (value: unknown): string | null =>
	typeof value === 'string' && value.trim() ? value.trim() : null;

const setDuration = (seconds: number): string =>
	seconds < 60 ? `${Math.round(seconds)}s` : formatDuration(seconds);

/** The parts of a set that were actually logged, in the order a lifter reads them. */
function describeSet(set: Record<string, unknown>): string | null {
	const weight = numberOrNull(set.weight_kg);
	const reps = numberOrNull(set.reps);
	const distance = numberOrNull(set.distance_meters);
	const duration = numberOrNull(set.duration_seconds);
	const custom = numberOrNull(set.custom_metric);
	const rpe = numberOrNull(set.rpe);

	const parts: string[] = [];
	if (weight !== null && reps !== null)
		parts.push(`${showDecimal(weight)} kg × ${showDecimal(reps)}`);
	else if (weight !== null) parts.push(`${showDecimal(weight)} kg`);
	else if (reps !== null) parts.push(`${showDecimal(reps)} reps`);
	if (distance !== null && distance > 0) parts.push(formatDistance(distance));
	if (duration !== null && duration > 0) parts.push(setDuration(duration));
	if (custom !== null) parts.push(showDecimal(custom));
	if (rpe !== null) parts.push(`RPE ${showDecimal(rpe)}`);
	return parts.length ? parts.join(' · ') : null;
}

/**
 * Strength exercises hidden inside workout segments. Lap and split segments
 * (a kind, a start time) are left for the lap count; they are not exercises.
 */
export function strengthExercises(segments: Record<string, unknown>[] | null): StrengthExercise[] {
	if (!segments) return [];

	const exercises: StrengthExercise[] = [];
	for (const segment of segments) {
		const name = textOrNull(segment.exercise);
		const rawSets = segment.sets;
		if (!name || !Array.isArray(rawSets)) continue;

		const sets: StrengthSet[] = [];
		rawSets.forEach((raw, index) => {
			if (!raw || typeof raw !== 'object') return;
			const set = raw as Record<string, unknown>;
			const detail = describeSet(set);
			if (!detail) return;
			const kind = textOrNull(set.type);
			const marker = kind && kind !== 'normal' ? ` · ${humanise(kind)}` : '';
			sets.push({ label: `${index + 1}${marker}`, detail });
		});
		if (sets.length) exercises.push({ name, notes: textOrNull(segment.notes), sets });
	}
	return exercises;
}
