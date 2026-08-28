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
  palette: palette
}
