import { humanise } from '$lib/utils/text';
import type { Provider } from '$lib/server/providers';

/**
 * By the name people read, not the slug: the API orders providers by when they
 * joined its enum, which says nothing to anyone scanning a list.
 */
export const byName = <T extends { name: string }>(providers: T[]) =>
	[...providers].sort((a, b) => a.name.localeCompare(b.name));

/**
 * Fed by the mobile SDK rather than a cloud API. Unknown counts as cloud.
 * An API-key provider also has no OAuth client, so `has_cloud_api` is false,
 * and that alone would mark it as an SDK feed.
 */
export const viaSdk = (
	providers: Pick<Provider, 'provider' | 'has_cloud_api' | 'connect_method'>[],
	slug: string
) => {
	const entry = providers.find((provider) => provider.provider === slug);
	if (!entry || entry.connect_method === 'api_key') return false;
	if (entry.connect_method === 'sdk') return true;
	return entry.has_cloud_api === false;
};

/** What a provider needs to be shown: its slug, its name and where its logo is. */
export type ProviderBrand = Pick<Provider, 'provider' | 'name' | 'icon_url'>;

/**
 * Backend `ProviderName` values that are not OAuth connections, so `/oauth/providers`
 * never names them. `internal` is Open Wearables' own work - its sleep and
 * resilience scores - and left to `humanise()` it read as "Internal".
 */
const UNLISTED: Record<string, string> = { internal: 'OW' };

/** The backend owns provider names; an unknown slug still has to render. */
export function providerLabel(providers: Provider[], slug: string): string {
	return (
		providers.find((provider) => provider.provider === slug)?.name ??
		UNLISTED[slug] ??
		humanise(slug)
	);
}

/** A provider's logo and name, or a bare one for a slug the catalogue no longer lists. */
export const brandOf = (providers: Provider[], slug: string): ProviderBrand =>
	providers.find((provider) => provider.provider === slug) ?? {
		provider: slug,
		name: providerLabel(providers, slug),
		icon_url: ''
	};
