# Flight Deck Calendar privacy

Flight Deck Calendar is read-only and local-first. It has no hosted backend, telemetry, analytics, advertising, or AI integration.

## Provider access

Google authorization requests `openid`, `email`, `calendar.events.readonly`, and `calendar.calendarlist.readonly` plus offline access required for local background refresh.

Personal Outlook.com authorization uses Microsoft's `/consumers` authority and requests `openid`, `profile`, `offline_access`, `User.Read`, and `Calendars.Read`.

Flight Deck has no calendar write scopes and no event creation, update, deletion, invitation, or scheduling routes.

## Local storage

- OAuth access and refresh tokens are stored in the desktop Secret Service keyring under the `omarchy-calendar` application attribute.
- Normalized calendar events and provider health are stored in `~/.local/state/omarchy-calendar/calendar.db` with private permissions.
- Local developer builds may store public provider client IDs in `~/.config/omarchy-calendar/providers.json` with private permissions.
- Appearance settings remain in Omarchy's user-owned `~/.config/omarchy/shell.json`.

The project does not collect, transmit, or retain calendar data on a Flight Deck server because no such server exists.

## Links

Meeting and source actions accept only HTTPS URLs already returned with an event. They are passed to the desktop URL opener as one argument without a shell.

## Disconnect and deletion

Disconnecting Google or Outlook deletes that provider's tokens from Secret Service and removes its cached accounts and events immediately. It does not change the provider calendar.

`Reset local data` requires two confirmations. It deletes all Flight Deck provider tokens, cached events, provider health, and local provider client-ID overrides. It does not delete appearance settings and does not change Google or Microsoft data.

Uninstalling the plugin alone does not delete data. Run `calendarctl reset-local-data` first when full local removal is wanted.
