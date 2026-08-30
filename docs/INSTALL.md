# Flight Deck Calendar installation

Flight Deck Calendar is a self-contained Omarchy shell plugin. It does not install a separate helper, timer, or service and it does not change Hyprland automatically.

## Install

The public install command continues to install RC3 from `main`:

```bash
omarchy plugin add https://github.com/joryeugene/omarchy-calendar.git --enable
```

The installed plugin ID is `io.github.joryeugene.omarchy-calendar`. Its bundled helper is:

```bash
calendarctl="$HOME/.config/omarchy/plugins/io.github.joryeugene.omarchy-calendar/calendarctl"
"$calendarctl" status
```

Invited RC4 testers should clone the exact verification branch into a clean profile instead:

```bash
plugin="$HOME/.config/omarchy/plugins/io.github.joryeugene.omarchy-calendar"
git clone --branch codex/v1.0.0-rc.4-verification --single-branch \
  https://github.com/joryeugene/omarchy-calendar.git "$plugin"
omarchy plugin enable io.github.joryeugene.omarchy-calendar --section right
calendarctl="$plugin/calendarctl"
```

Try the built-in offline dataset without an account:

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

Press `c`, choose Google Calendar or Outlook.com, review the requested read-only access, and choose **Connect in browser**. Complete provider consent in the browser, then return to Flight Deck. The provider is connected only after the first successful sync populates the local cache.

### Google Calendar

Google uses PKCE S256 and receives only identity, `calendar.events.readonly`, and `calendar.calendarlist.readonly` access.

### Personal Outlook.com

Microsoft uses the `/consumers` authority and receives identity, profile, offline access, `User.Read`, and `Calendars.Read`. It uses no application credential. There is no `Calendars.ReadWrite` scope and no mutation command.

For either provider, press `c` and choose Connect when browser consent needs to be repeated.

### Advanced provider override

Contributors can replace either bundled public desktop registration without editing source code. A valid local override always takes precedence, and installing RC4 does not replace existing tokens or provider settings.

For Google, import the Desktop credentials JSON from a separate Google Cloud project. The import stores only the public client ID in `~/.config/omarchy-calendar/providers.json`. The Desktop app credential goes directly to a distinct Secret Service keyring item and is not written to provider settings, source code, command arguments, or output.

```bash
"$calendarctl" import-google-desktop-app /path/to/google-desktop-credentials.json
"$calendarctl" auth google
```

For Microsoft, configure the public Application client ID from a personal-account capable desktop registration:

```bash
"$calendarctl" configure-client microsoft PUBLIC_MICROSOFT_DESKTOP_ID
"$calendarctl" auth microsoft
```

Provider client-ID overrides are written to `~/.config/omarchy-calendar/providers.json` with mode `0600`. OAuth tokens and an imported Google Desktop app credential are stored in the system keyring. Bundled public registrations remain in the installed plugin. Cached events are stored in `~/.local/state/omarchy-calendar/calendar.db` with mode `0600`.

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
