# Omarchy compatibility and update survival

Flight Deck Calendar v1.1.0 targets an older Omarchy shell. Current Omarchy
(4.x, Qt 6.11) changed host APIs the plugin relied on, and the setup flow needed
two behavior changes: Google must authenticate in the browser, and a provider
must be able to hold more than one account. This document records every change,
the symptom and root cause behind it, and how the fixes survive
`omarchy plugin update`. It doubles as the change log for a pull request.

## What was broken and why

| # | Symptom | Root cause | Files |
| - | ------- | ---------- | ----- |
| 1 | Panel opened with no data and felt frozen; Google looked unconfigured | The host exposes `bar.centerHoverRevealSuppressed` as read-only and provides `bar.setCenterHoverRevealSuppressed(value)`. The plugin assigned the read-only property, which threw a `TypeError`. The throw happened first inside `open()`'s `Qt.callLater`, so `loadView()` and `loadSetupStatus()` never ran. | `Panel.qml` |
| 2 | "Calendar Helper Unavailable" with no events | Third-party plugin manifests are sanitized: `publicPluginManifest()` deletes `__sourceDir`. `Service.qml` built `helperPath` from `manifest.__sourceDir`, so it was empty and every helper call no-op'd. | `Service.qml` |
| 3 | Browser did not come to the front for consent | The shell's environment has no `BROWSER`, so Python `webbrowser` fell back to `xdg-open`, which opens a tab but does not raise or focus the window. | `src/omarchy_calendar/auth_service.py` |
| 4 | Google setup offered the credentials JSON instead of browser auth; native chooser could abort Quickshell | Setup treated a missing/not-yet-loaded bundled registration as "no registration" and opened a native GTK `FileDialog`, the GVFS/D-Bus path that can `SIGABRT` Quickshell. | `SetupView.qml` |
| 5 | Only one Google account could be connected | Account actions only offered "Connect" when a provider had zero accounts, and Google's consent URL reused the single signed-in account. | `SettingsModel.js`, `SettingsView.qml`, `src/omarchy_calendar/oauth.py` |
| 6 | A popup appeared over Today/Week ("Connect Google Calendar", later "NO EVENTS IN THIS PERIOD") whenever the period had no events | The card keyed only off `events.length === 0`, not off whether an account was connected. | `Panel.qml` |

Upstream issue: <https://github.com/joryeugene/omarchy-calendar/issues/4>.

## What changed

- `Panel.qml`
  - `setCenterHoverRevealSuppressed` calls the host method when present and
    falls back to the writable property on older builds.
  - The empty-state card only appears for states the user can act on: a helper
    error, every calendar hidden, or no account connected yet. A connected
    account with no events in the period shows nothing, so Today and Week match.
    Account management, including adding an account, stays in Settings.
- `Service.qml`
  - `helperPath` is resolved from the component's own location with
    `Qt.resolvedUrl("calendarctl")`, independent of the injected manifest.
- `SetupView.qml`
  - Google's primary action always starts browser consent.
  - The JSON import is kept as an explicit "Import Google Desktop credentials
    JSON (advanced)" control.
  - `FileDialog` sets `FileDialog.DontUseNativeDialog` so the GTK/GVFS chooser
    cannot abort the shell.
- `SettingsModel.js` / `SettingsView.qml`
  - Each provider with an account gains an "Add account" row that reopens the
    consent flow, so several Google accounts can be attached.
- `src/omarchy_calendar/oauth.py`
  - Google authorization uses `prompt=select_account consent` so the account
    chooser appears when adding another account.
- `src/omarchy_calendar/auth_service.py`
  - `open_system_browser` prefers `OMARCHY_CALENDAR_BROWSER_COMMAND`, then
    `omarchy-launch-browser` (which focuses the window), then `xdg-open`, then
    `webbrowser.open`. The browser is spawned detached.
- `Panel.qml` header and `SettingsView.qml`
  - The header is now four matching buttons: Today, Week, New, and Settings.
    The sync-status text, Refresh, and Help actions are gone from it.
  - Help moved into the Settings sidebar as a "Help" section showing the same
    keyboard map. Every shortcut is unchanged: `r` still refreshes, `?` still
    toggles help, `s` still opens Settings, `n` still creates.
- Tests cover the host-setter call, the resolved helper path, the browser
  launcher chain, the Google browser/JSON split, the add-account action, the
  connected empty state, and the `select_account` prompt.

## How `omarchy plugin update` treats these commits

`omarchy plugin update` runs, per plugin:

```bash
git -C "$dir" fetch --quiet origin HEAD
git -C "$dir" merge --ff-only FETCH_HEAD
```

The result depends on whether upstream `main` moved:

- **Upstream unchanged since the base commit.** `FETCH_HEAD` is an ancestor of
  the local `HEAD`, so the fast-forward is a no-op and the script prints
  `Updated '<id>'.` The fixes are untouched.
- **Upstream advanced.** `FETCH_HEAD` is not an ancestor of the local `HEAD`,
  so the fast-forward is refused and the script prints:

  ```
  omarchy-plugin-update: cannot fast-forward '<id>'; you have local changes
  ```

Either way the fixes are never overwritten. The second case is the signal that
upstream moved; rebase or merge deliberately (below) to take its changes.

The script always calls `omarchy-shell shell rescanPlugins` after it reports an
update. That reload can exceed the IPC timeout and print
`omarchy-shell is not responding`; the shell is fine and `omarchy-shell shell
ping` returns `ok` immediately after.

## Keeping the fixes across updates

Pick one of these two models.

### A. Track the fork (recommended for a machine that should keep updating)

1. Fork and push the branch once:

   ```bash
   gh repo fork joryeugene/omarchy-calendar --remote=false
   git remote add fork https://github.com/<your-account>/omarchy-calendar.git
   git push -u fork fix/omarchy-shell-api-drift
   ```

2. Point the plugin at the fork so `omarchy plugin update` fast-forwards to it:

   ```bash
   git remote set-url origin https://github.com/<your-account>/omarchy-calendar.git
   ```

3. Periodically merge upstream into the fork (or the local branch) and push:

   ```bash
   git remote add upstream https://github.com/joryeugene/omarchy-calendar.git
   git fetch upstream
   git merge upstream/main      # resolve conflicts, keep the fixes
   git push fork HEAD:main
   ```

Once the pull request is merged upstream, switch back:

```bash
git remote set-url origin https://github.com/joryeugene/omarchy-calendar.git
git checkout main && git pull
```

### B. Stay on upstream and rebase locally

Keep `origin` pointing at upstream and rebase the fix branch when you want new
upstream commits:

```bash
git fetch origin
git rebase origin/main        # resolve conflicts, keep the fixes
```

`omarchy plugin update` continues to refuse the fast-forward, which is the
safety net; the rebase is how you take upstream changes deliberately.

## Reinstalling from scratch

If the plugin is removed and added again from upstream, re-apply the fork:

```bash
omarchy plugin remove io.github.joryeugene.omarchy-calendar
omarchy plugin add https://github.com/<your-account>/omarchy-calendar.git --enable
```

## Verify after any merge or rebase

```bash
plugin="$HOME/.config/omarchy/plugins/io.github.joryeugene.omarchy-calendar"
"$plugin/scripts/check"          # or: just check
omarchy plugin validate "$plugin"
omarchy-shell shell ping
```

Then confirm in the panel: it opens with events, `c` opens Settings at
Accounts and Calendars, Google shows "Connect in browser", and an "Add account"
row appears under a connected provider.
