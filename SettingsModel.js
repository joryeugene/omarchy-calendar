// SPDX-License-Identifier: GPL-3.0-or-later
var DEFAULTS = {
  theme: "kinetic-tokyo-night",
  density: "compact",
  textScale: 1,
  animations: true,
  defaultView: "today",
  weekStartHour: 7,
  weekEndHour: 20,
  timeFormat: "system",
  syncIntervalMinutes: 5,
  format: "yyyy/MM/dd HH:mm",
  formatAlt: "dddd yyyy/MM/dd HH:mm",
  verticalFormat: "yyyy\nMM\ndd\nHH\nmm",
  verticalFormatAlt: "ddd\nyyyy\nMM\ndd\nHH\nmm",
  hiddenCalendars: []
}

function choice(value, allowed, fallback) {
  return allowed.indexOf(value) >= 0 ? value : fallback
}

function numberInRange(value, minimum, maximum, fallback) {
  var parsed = Number(value)
  if (!isFinite(parsed)) return fallback
  return Math.max(minimum, Math.min(maximum, parsed))
}

function opaqueCalendarKeys(values) {
  var result = []
  var source = Array.isArray(values) ? values : []
  for (var i = 0; i < source.length && result.length < 512; i++) {
    if (typeof source[i] !== "string" || !/^[0-9a-f]{64}$/.test(source[i])) continue
    if (result.indexOf(source[i]) === -1) result.push(source[i])
  }
  return result
}

function normalize(values) {
  var source = values || {}
  var start = Math.round(numberInRange(source.weekStartHour, 0, 22, DEFAULTS.weekStartHour))
  var end = Math.round(numberInRange(source.weekEndHour, start + 2, 24, DEFAULTS.weekEndHour))
  var density = source.density === "comfortable" ? "roomy" : source.density
  var animations = typeof source.animations === "boolean" ? source.animations
    : source.motion === "reduced" ? false : DEFAULTS.animations
  if (end < start + 2) end = start + 2
  return {
    theme: choice(source.theme, ["kinetic-tokyo-night", "omarchy", "high-contrast"], DEFAULTS.theme),
    density: choice(density, ["compact", "roomy"], DEFAULTS.density),
    textScale: numberInRange(source.textScale, 0.9, 1.25, DEFAULTS.textScale),
    animations: animations,
    defaultView: choice(source.defaultView, ["today", "week"], DEFAULTS.defaultView),
    weekStartHour: start,
    weekEndHour: end,
    timeFormat: choice(source.timeFormat, ["system", "12h", "24h"], DEFAULTS.timeFormat),
    syncIntervalMinutes: choice(Number(source.syncIntervalMinutes), [5, 15, 30], DEFAULTS.syncIntervalMinutes),
    format: String(source.format || DEFAULTS.format),
    formatAlt: String(source.formatAlt || DEFAULTS.formatAlt),
    verticalFormat: String(source.verticalFormat || DEFAULTS.verticalFormat),
    verticalFormatAlt: String(source.verticalFormatAlt || DEFAULTS.verticalFormatAlt),
    hiddenCalendars: opaqueCalendarKeys(source.hiddenCalendars)
  }
}

function withValue(values, key, value) {
  var next = {}
  var current = values || {}
  for (var name in current) next[name] = current[name]
  next[key] = value
  return normalize(next)
}

function accountRows(providers, calendars, health) {
  var rows = []
  var setup = providers || []
  for (var p = 0; p < setup.length; p++) {
    var provider = setup[p]
    var accounts = []
    for (var h = 0; h < (health || []).length; h++)
      if (health[h].provider === provider.provider && health[h].demo !== true)
        accounts.push(String(health[h].account_id || ""))
    for (var c = 0; c < (calendars || []).length; c++)
      if (calendars[c].provider === provider.provider && accounts.indexOf(String(calendars[c].account_id || "")) < 0)
        accounts.push(String(calendars[c].account_id || ""))
    if (!accounts.length) accounts.push("")
    for (var a = 0; a < accounts.length; a++) {
      var accountId = accounts[a]
      var calendar = (calendars || []).find(function(item) {
        return item.provider === provider.provider && String(item.account_id || "") === accountId
      })
      var state = (health || []).find(function(item) {
        return item.provider === provider.provider && String(item.account_id || "") === accountId
      })
      rows.push({
        provider: provider.provider,
        provider_label: provider.label || provider.provider,
        account_id: accountId,
        account_label: calendar ? String(calendar.account_label || provider.label) : String(provider.label || provider.provider),
        connected: state ? state.connected === true : provider.connected === true,
        stale: state ? state.stale === true : provider.stale === true,
        last_sync: state ? String(state.last_sync || "") : String(provider.last_sync || ""),
        last_error: state ? String(state.last_error || "") : String(provider.last_error || ""),
        editing: (provider.editing_account_ids || []).indexOf(accountId) >= 0,
      })
    }
    // Providers can hold several accounts at once. Once one is connected the
    // placeholder row disappears, so add an explicit row that opens the same
    // browser consent flow again to attach another account.
    if (accounts.length > 0 && accounts[0] !== "") {
      rows.push({
        provider: provider.provider,
        provider_label: provider.label || provider.provider,
        account_id: "",
        account_label: "Add another " + String(provider.label || provider.provider) + " account",
        connected: false,
        stale: false,
        last_sync: "",
        last_error: "",
        editing: false,
        add: true,
      })
    }
  }
  return rows
}

function accountActions(rows) {
  var actions = []
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i]
    if (row.add) actions.push({ provider: row.provider, account_id: "", kind: "add", row: i })
    else if (!row.connected) actions.push({ provider: row.provider, account_id: row.account_id, kind: "connect", row: i })
    else {
      if (!row.editing) actions.push({ provider: row.provider, account_id: row.account_id, kind: "enable", row: i })
      actions.push({ provider: row.provider, account_id: row.account_id, kind: "disconnect", row: i })
    }
  }
  return actions
}

function palette(name, omarchy) {
  var source = omarchy || {}
  if (name === "omarchy") {
    return {
      background: source.background || "#1a1b26",
      surface: source.surface || source.background || "#24283b",
      foreground: source.foreground || "#c0caf5",
      muted: source.muted || "#7f849c",
      accent: source.accent || "#7aa2f7",
      border: source.muted || "#565f89",
      positive: source.positive || "#9ece6a",
      urgent: source.urgent || "#f7768e"
    }
  }
  if (name === "high-contrast") {
    return {
      background: "#050608",
      surface: "#11141a",
      foreground: "#ffffff",
      muted: "#c4cad8",
      accent: "#66d9ff",
      border: "#ffffff",
      positive: "#8fff8f",
      urgent: "#ff7a9b"
    }
  }
  return {
    background: "#16161e",
    surface: "#1f2335",
    foreground: "#c0caf5",
    muted: "#9aa5ce",
    accent: "#7aa2f7",
    border: "#3b4261",
    positive: "#9ece6a",
    urgent: "#f7768e"
  }
}

if (typeof module !== "undefined") module.exports = {
  DEFAULTS: DEFAULTS,
  normalize: normalize,
  withValue: withValue,
  accountRows: accountRows,
  accountActions: accountActions,
  palette: palette
}
