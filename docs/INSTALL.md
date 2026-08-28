# Flight Deck Calendar installation

Flight Deck Calendar is a self-contained Omarchy shell plugin. It does not install a separate helper, timer, or service and it does not change Hyprland automatically.

## Bring your own OAuth registration

Flight Deck Calendar is a public preview. It does not include Google or Microsoft OAuth registrations. Before installing or connecting a provider, create your own Google Desktop OAuth app and Microsoft public desktop app that supports personal accounts. Each registration must use only the required read-only scopes.

Provider setup needs one browser consent session per provider. This preview is not one-click or seamless account setup.

## Install

Install the public preview from GitHub:

```bash
omarchy plugin add https://github.com/joryeugene/omarchy-calendar.git --enable
```

The installed plugin ID is `io.github.joryeugene.omarchy-calendar`. Its bundled helper is:

```bash
calendarctl="$HOME/.config/omarchy/plugins/io.github.joryeugene.omarchy-calendar/calendarctl"
"$calendarctl" status
```

Try fictional local data without an account:

```bash
"$calendarctl" demo seed
"$calendarctl" status
```

## Optional launch binding

`Super+Shift+C` is optional and the plugin does not claim it during installation. If the chord is free on the machine, add this user-owned binding to the normal Omarchy Hyprland bindings file:

```ini
bindd = SUPER SHIFT, C, Flight Deck calendar, exec, omarchy-shell shell toggle io.github.joryeugene.omarchy-calendar
```

Reload Hyprland and confirm `hyprctl configerrors` is empty. Remove the single line to roll back the binding.

## Provider setup

After completing the bring-your-own registration prerequisite, Flight Deck can open the browser consent flow from Settings.

### Google Calendar

Create or use a Google OAuth Desktop app with only the required read-only Calendar scopes. Download its Desktop credentials JSON and keep the file outside the repository. In Flight Deck, press `c`, choose Google Calendar, then choose **Google Desktop JSON**. Flight Deck imports the registration metadata and immediately opens browser authorization.

The bundled helper provides the same flow as a command-line fallback:

```bash
"$calendarctl" import-google-desktop-app /path/to/google-desktop-credentials.json
"$calendarctl" auth google
```

The import stores only the public client ID in `~/.config/omarchy-calendar/providers.json`. The Desktop app credential goes directly to a distinct Secret Service keyring item. It is not written to the provider settings, source tree, command arguments, or output. Delete the downloaded JSON after independently confirming it is no longer needed for recovery.

Google uses PKCE S256 and receives only identity, `calendar.events.readonly`, and `calendar.calendarlist.readonly` access.

### Personal Outlook.com

Use a Microsoft public desktop application registration that supports personal accounts. In Flight Deck, press `c`, choose Outlook.com, paste its public Application client ID, then choose **Save ID and connect**.

The bundled helper provides the same flow as a command-line fallback:

```bash
"$calendarctl" configure-client microsoft PUBLIC_MICROSOFT_DESKTOP_ID
"$calendarctl" auth microsoft
```

Microsoft uses the `/consumers` authority and receives identity, profile, offline access, `User.Read`, and `Calendars.Read`. It uses no application credential. There is no `Calendars.ReadWrite` scope and no mutation command.

For either provider, press `c` in Flight Deck after metadata is configured and choose Connect if browser consent needs to be repeated. The provider is connected only after a successful sync, not merely after the browser redirects.

Provider client-ID overrides are written to `~/.config/omarchy-calendar/providers.json` with mode `0600`. OAuth tokens and the Google Desktop app credential are stored in the system keyring. Cached events are stored in `~/.local/state/omarchy-calendar/calendar.db` with mode `0600`.

## Operations

```bash
"$calendarctl" sync
"$calendarctl" sync --provider google
"$calendarctl" sync --provider microsoft
"$calendarctl" status
"$calendarctl" setup-status
"$calendarctl" disconnect google
"$calendarctl" disconnect microsoft
"$calendarctl" reset-local-data
```

One singleton Omarchy service refreshes every 5, 15, or 30 minutes according to inline settings. No user systemd unit is involved. On network failure, the last successful local cache remains visible and is marked stale.

## Health checks

```bash
omarchy plugin validate "$HOME/.config/omarchy/plugins/io.github.joryeugene.omarchy-calendar"
hyprctl configerrors
omarchy-shell shell ping
"$calendarctl" status
"$calendarctl" setup-status
```

## Uninstall

To remove local calendar data and tokens first:

```bash
"$calendarctl" reset-local-data
```

Then remove the plugin:

```bash
omarchy plugin remove io.github.joryeugene.omarchy-calendar
```

Remove the optional `Super+Shift+C` binding separately if it was added. Provider calendars are never modified.
