import { fail, redirect } from '@sveltejs/kit';
import { ApiError, apiPublicPost } from '$lib/server/api';
import { authorizeProvider } from '$lib/server/oauth';
import { fetchCloudProviders } from '$lib/server/providers';
import { pairingSuccessUrl, safeReturnUrl } from '$lib/pairing/links';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => ({
	providers: await fetchCloudProviders(),
	returnUrl: safeReturnUrl(url.searchParams.get('redirect_url'))
});

export const actions: Actions = {
	connect: async ({ params, request, url }) => {
		// `?/connect` replaces the query string, so the return link travels as a field.
		const form = await request.formData();
		const provider = String(form.get('provider') ?? '');
		const returnUrl = String(form.get('return_url') ?? '') || null;

		let authorizationUrl: string;
		try {
			const target = pairingSuccessUrl(url.origin, params.id, provider, returnUrl);
			({ authorization_url: authorizationUrl } = await authorizeProvider(
				provider,
				params.id,
				target
			));
		} catch (error) {
			const detail = error instanceof ApiError ? error.message : 'Try again in a moment.';
			return fail(400, { provider, message: `Could not reach ${provider}. ${detail}` });
		}

		redirect(303, authorizationUrl);
	},

	connectKey: async ({ params, request, url }) => {
		const form = await request.formData();
		const provider = String(form.get('provider') ?? '');
		const apiKey = String(form.get('api_key') ?? '').trim();
		const returnUrl = String(form.get('return_url') ?? '') || null;

		if (!apiKey) {
			return fail(400, { provider, message: 'Paste the API key from Hevy.' });
		}

		try {
			await apiPublicPost(`/api/v1/oauth/${provider}/api-key`, {
				user_id: params.id,
				api_key: apiKey
			});
		} catch (error) {
			const detail = error instanceof ApiError ? error.message : 'Try again in a moment.';
			return fail(400, { provider, message: detail });
		}

		redirect(303, pairingSuccessUrl(url.origin, params.id, provider, returnUrl));
	}
};
