// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

const require = createRequire(import.meta.url)
const settings = require("../SettingsModel.js")

test("settings normalize to the locked release defaults", () => {
  assert.deepEqual(settings.normalize({}), {
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
    hiddenCalendars: [],
  })
})

test("calendar visibility settings keep only unique opaque selector keys", () => {
  const first = "a".repeat(64)
  const second = "b".repeat(64)
  const normalized = settings.normalize({
    hiddenCalendars: [first, "not-an-opaque-key", first, second, 42],
  })

  assert.deepEqual(normalized.hiddenCalendars, [first, second])
})

test("settings reject unknown choices and clamp numeric ranges", () => {
  const normalized = settings.normalize({
    theme: "neon-rainbow",
    density: "huge",
    textScale: 9,
    animations: "sometimes",
    defaultView: "month",
    weekStartHour: 23,
    weekEndHour: 2,
    timeFormat: "martian",
    syncIntervalMinutes: 7,
  })

  assert.equal(normalized.theme, "kinetic-tokyo-night")
  assert.equal(normalized.density, "compact")
  assert.equal(normalized.textScale, 1.25)
  assert.equal(normalized.animations, true)
  assert.equal(normalized.defaultView, "today")
  assert.equal(normalized.weekStartHour, 22)
  assert.equal(normalized.weekEndHour, 24)
  assert.equal(normalized.timeFormat, "system")
  assert.equal(normalized.syncIntervalMinutes, 5)
})

test("appearance settings migrate legacy values to clear current choices", () => {
  assert.equal(settings.normalize({ density: "comfortable" }).density, "roomy")
  assert.equal(settings.normalize({ motion: "reduced" }).animations, false)
  assert.equal(settings.normalize({ motion: "restrained" }).animations, true)
  assert.equal(settings.normalize({ animations: false }).animations, false)
})

test("updating a draft never mutates the applied settings", () => {
  const applied = settings.normalize({ theme: "omarchy" })
  const draft = settings.withValue(applied, "theme", "high-contrast")

  assert.equal(applied.theme, "omarchy")
  assert.equal(draft.theme, "high-contrast")
})

test("three theme presets expose complete semantic palettes", () => {
  for (const name of ["kinetic-tokyo-night", "omarchy", "high-contrast"]) {
    const palette = settings.palette(name, {
      background: "#111111",
      foreground: "#eeeeee",
      accent: "#44aaff",
      muted: "#999999",
      urgent: "#ff4444",
    })
    assert.deepEqual(Object.keys(palette).sort(), [
      "accent", "background", "border", "foreground", "muted", "positive", "surface", "urgent",
    ])
  }
})

test("account actions are account-specific and preserve separate enable and disconnect controls", () => {
  const providers = [
    { provider: "google", label: "Google", connected: true, editing_account_ids: [] },
    { provider: "microsoft", label: "Outlook", connected: false, editing_account_ids: [] },
  ]
  const calendars = [
    { provider: "google", account_id: "one", account_label: "one@example.com" },
    { provider: "google", account_id: "two", account_label: "two@example.com" },
  ]
  const health = [
    { provider: "google", account_id: "one", connected: true, stale: false },
    { provider: "google", account_id: "two", connected: true, stale: true },
  ]

  const rows = settings.accountRows(providers, calendars, health)
  const actions = settings.accountActions(rows)

  assert.deepEqual(rows.map(row => [row.provider, row.account_id, row.account_label, row.editing]), [
    ["google", "one", "one@example.com", false],
    ["google", "two", "two@example.com", false],
    ["google", "", "Add another Google account", false],
    ["microsoft", "", "Outlook", false],
  ])
  assert.deepEqual(actions.map(action => [action.provider, action.account_id, action.kind]), [
    ["google", "one", "enable"],
    ["google", "one", "disconnect"],
    ["google", "two", "enable"],
    ["google", "two", "disconnect"],
    ["google", "", "add"],
    ["microsoft", "", "connect"],
  ])
})

test("connected providers keep an add-account action for more calendars", () => {
  const rows = settings.accountRows(
    [{ provider: "google", label: "Google", connected: true, editing_account_ids: [] }],
    [{ provider: "google", account_id: "one", account_label: "one@example.com" }],
    [{ provider: "google", account_id: "one", connected: true, stale: false }],
  )

  assert.deepEqual(settings.accountActions(rows).map(action => action.kind), ["enable", "disconnect", "add"])
})

test("editing accounts expose status and disconnect without another enable action", () => {
  const rows = settings.accountRows(
    [{ provider: "google", label: "Google", connected: true, editing_account_ids: ["one"] }],
    [{ provider: "google", account_id: "one", account_label: "one@example.com" }],
    [{ provider: "google", account_id: "one", connected: true, stale: false }],
  )

  assert.equal(rows[0].editing, true)
  assert.deepEqual(settings.accountActions(rows).map(action => action.kind), ["disconnect", "add"])
})
