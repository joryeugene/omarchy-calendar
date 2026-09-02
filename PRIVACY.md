# Flight Deck Calendar privacy

Flight Deck Calendar is read-only. It has no hosted backend, telemetry, analytics, advertising, or AI integration. Provider tokens and calendar data remain on the local workstation.

## Google user data we access

Google authorization requests `openid`, `email`, `calendar.events.readonly`, and `calendar.calendarlist.readonly` plus offline access required for local background refresh.

The identity scopes provide the Google account identifier and email address used to label the connected account. The calendar-list scope provides calendar identifiers, names, colors, selection state, and deletion state. The events scope provides event identifiers, titles, times, all-day status, location, description, organizer, event status, meeting links, source links, and update times.

Personal Outlook.com authorization uses Microsoft's `/consumers` authority and requests `openid`, `profile`, `offline_access`, `User.Read`, and `Calendars.Read`.

Flight Deck has no calendar write scopes and no event creation, update, deletion, invitation, or scheduling routes.

## How we use Google user data

Flight Deck uses Google Calendar data only to display calendars and events, let the user choose which calendars appear, select the current or nearest event, refresh the local read-only view, and open a meeting or source link when the user requests it.

The calendar-list scope is required to identify the user's calendars and support calendar visibility controls. The events scope is required to read events from those calendars. A narrower identity-only grant cannot provide either feature, and either calendar scope alone cannot provide both the calendar selector and the event views.

The developer cannot access calendar data or tokens because the app sends neither to a Flight Deck server.

## Sharing and disclosure

Flight Deck does not sell, share, or transfer Google user data to the developer, advertisers, analytics services, AI systems, or other third parties. Flight Deck does not integrate with AI services. The workstation communicates directly with Google and Microsoft only to authorize the account, read the selected calendars, and refresh the local cache.

Flight Deck Calendar's use and transfer of information received from Google APIs adheres to the [Google API Services User Data Policy, including the Limited Use requirements](https://developers.google.com/terms/api-services-user-data-policy).

## Data protection

- OAuth access and refresh tokens are stored in the desktop Secret Service keyring under the `omarchy-calendar` application attribute.
- The local SQLite cache stores account identifiers and labels; calendar identifiers, names, and colors; event titles, times, locations, descriptions, organizers, status, and meeting and source links; and provider refresh health. It is stored at `~/.local/state/omarchy-calendar/calendar.db` with private file permissions. Its parent directory is accessible only to the local user.
- Flight Deck communicates with Google and Microsoft over HTTPS. Meeting and source actions accept only HTTPS URLs returned with an event and pass each URL to the desktop opener without a shell.
- Bundled Google and Microsoft desktop registrations are public application metadata shipped with the plugin. They are not account credentials and cannot grant access without the user's browser consent and tokens.
- Advanced provider overrides may store public provider client IDs in `~/.config/omarchy-calendar/providers.json` with private file permissions. An imported Google Desktop app credential is stored in a separate Secret Service item.
- Appearance settings remain in Omarchy's user-owned `~/.config/omarchy/shell.json`.

The project does not collect, transmit, or retain calendar data on a Flight Deck server because no such server exists.

## Retention and deletion

Flight Deck retains Google OAuth tokens until the user disconnects Google or resets local data. It retains cached Google Calendar data until a successful refresh replaces the applicable time window, the user disconnects Google, or the user resets local data. Flight Deck retains no Google user data on a developer-controlled server.

Disconnecting Google or Outlook deletes that provider's tokens from Secret Service and removes its cached accounts and events immediately. It does not change the provider calendar.

The in-app reset uses two activations: choose `Reset local data`, then choose `Confirm reset`. The terminal command `calendarctl reset-local-data` runs immediately when invoked. Both paths delete all Flight Deck provider tokens, imported Google app credentials, cached events, provider health records, and local provider client-ID overrides. They do not delete bundled public registration metadata, appearance settings, or Google or Microsoft data.

Uninstalling the plugin alone does not delete data. Run `calendarctl reset-local-data` first when full local removal is wanted.
