<script lang="ts">
	import KeyRound from '@lucide/svelte/icons/key-round';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { enhance } from '$app/forms';
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import { buttonClass } from '$lib/components/ui/button';
	import { FIELD } from '$lib/components/ui/field';
	import { FOOTNOTE } from '$lib/components/ui/typography';
	import type { Provider } from '$lib/server/providers';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let { provider, returnUrl }: { provider: Provider; returnUrl: string | null } = $props();

	const submit = createSubmitFlag();
</script>

<form
	method="POST"
	action="?/connectKey"
	use:enhance={submit.enhance}
	class="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4"
>
	<div class="flex items-center gap-4">
		<ProviderLogo {provider} />
		<span class="min-w-0 flex-1">
			<span class="block truncate font-medium text-foreground">{provider.name}</span>
			<span class="block text-xs text-muted-foreground">Paste an API key</span>
		</span>
	</div>

	<input type="hidden" name="provider" value={provider.provider} />
	{#if returnUrl}
		<input type="hidden" name="return_url" value={returnUrl} />
	{/if}

	<label class="flex flex-col gap-1.5">
		<span class="sr-only">{provider.name} API key</span>
		<input
			name="api_key"
			type="password"
			autocomplete="off"
			spellcheck="false"
			required
			placeholder="API key"
			class="{FIELD} w-full px-3"
		/>
		<span class={FOOTNOTE}>
			From {provider.name} settings, under Developer. The key is stored for this connection.
		</span>
	</label>

	<button type="submit" disabled={submit.submitting} class="{buttonClass('primary')} w-full">
		{#if submit.submitting}
			<LoaderCircle size={16} aria-hidden="true" class="animate-spin" />
			Connecting…
		{:else}
			<KeyRound size={16} aria-hidden="true" />
			Connect
		{/if}
	</button>
</form>
