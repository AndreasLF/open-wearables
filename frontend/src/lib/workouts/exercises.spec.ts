import { describe, expect, it } from 'vitest';
import { strengthExercises } from './exercises';

describe('strengthExercises', () => {
	it('keeps weight, reps, distance, holds, and the set type', () => {
		const exercises = strengthExercises([
			{
				exercise: 'Back Squat',
				notes: 'Belt on',
				sets: [
					{ type: 'warmup', weight_kg: 60, reps: 5, rpe: null },
					{ type: 'normal', weight_kg: 140, reps: 7, rpe: 8 },
					{
						type: 'normal',
						weight_kg: null,
						reps: null,
						distance_meters: 400,
						duration_seconds: 45
					}
				]
			}
		]);

		expect(exercises).toEqual([
			{
				name: 'Back Squat',
				notes: 'Belt on',
				sets: [
					{ label: '1 · Warmup', detail: '60 kg × 5' },
					{ label: '2', detail: '140 kg × 7 · RPE 8' },
					{ label: '3', detail: '400 m · 45s' }
				]
			}
		]);
	});

	it('ignores lap segments, which are not exercises', () => {
		expect(strengthExercises([{ kind: 'lap', index: 1, elapsed_seconds: 300 }])).toEqual([]);
		expect(strengthExercises(null)).toEqual([]);
	});
});
