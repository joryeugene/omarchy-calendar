# Flight Deck Calendar privacy

Flight Deck Calendar is read-only. It has no hosted backend, telemetry, analytics, advertising, or AI integration. Provider tokens and calendar data remain on the local workstation.

## Provider access

Google authorization requests `openid`, `email`, `calendar.events.readonly`, and `calendar.calendarlist.readonly` plus offline access required for local background refresh.

Personal Outlook.com authorization uses Microsoft's `/consumers` authority and requests `openid`, `profile`, `offline_access`, `User.Read`, and `Calendars.Read`.

Flight Deck has no calendar write scopes and no event creation, update, deletion, invitation, or scheduling routes.

Flight Deck uses Google Calendar data only to display calendars and events, select the current or nearest event, and open a meeting or source link when the user requests it. The developer cannot access calendar data or tokens because the app sends neither to a Flight Deck server.

Flight Deck does not sell, share, or transfer Google user data to the developer, advertisers, analytics services, AI systems, or other third parties. The workstation communicates directly with Google and Microsoft only to authorize the account, read the selected calendars, and refresh the local cache.

Flight Deck Calendar's use and transfer of information received from Google APIs adheres to the [Google API Services User Data Policy, including the Limited Use requirements](https://developers.google.com/terms/api-services-user-data-policy).

## Local storage

- OAuth access and refresh tokens are stored in the desktop Secret Service keyring under the `omarchy-calendar` application attribute.
- The local SQLite cache stores account identifiers and labels; calendar identifiers, names, and colors; event titles, times, locations, descriptions, organizers, status, and meeting and source links; and provider refresh health. It is stored at `~/.local/state/omarchy-calendar/calendar.db` with private permissions.
- Local developer builds may store public provider client IDs in `~/.config/omarchy-calendar/providers.json` with private permissions.
- Appearance settings remain in Omarchy's user-owned `~/.config/omarchy/shell.json`.

The project does not collect, transmit, or retain calendar data on a Flight Deck server because no such server exists.

## Links

Meeting and source actions accept only HTTPS URLs already returned with an event. They are passed to the desktop URL opener as one argument without a shell.

## Disconnect and deletion

Disconnecting Google or Outlook deletes that provider's tokens from Secret Service and removes its cached accounts and events immediately. It does not change the provider calendar.

The in-app reset uses two activations: choose `Reset local data`, then choose `Confirm reset`. The terminal command `calendarctl reset-local-data` runs immediately when invoked. Both paths delete all Flight Deck provider tokens, imported Google app credentials, cached events, provider health records, and local provider client-ID overrides. They do not delete appearance settings or change Google or Microsoft data.

Uninstalling the plugin alone does not delete data. Run `calendarctl reset-local-data` first when full local removal is wanted.
