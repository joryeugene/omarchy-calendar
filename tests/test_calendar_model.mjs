// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"

process.env.TZ = "America/Chicago"
const require = createRequire(import.meta.url)
const model = require("../CalendarModel.js")

test("day and Monday week identities are stable", () => {
  assert.equal(model.dayKey(new Date("2026-08-25T12:00:00-05:00")), "2026-08-25")
  assert.equal(model.dayKey(model.startOfWeek(new Date("2026-08-27T12:00:00-05:00"))), "2026-08-24")
  assert.equal(model.weekDays(new Date("2026-08-27T12:00:00-05:00")).length, 7)
})

test("period navigation moves the cursor and selection exactly one visible period", () => {
  const cursor = new Date("2026-08-27T12:00:00-05:00")
  const selected = new Date("2026-08-26T09:00:00-05:00")

  const nextDay = model.periodState(cursor, selected, "today", 1)
  assert.equal(model.dayKey(nextDay.cursorDate), "2026-08-28")
  assert.equal(model.dayKey(nextDay.selectedDay), "2026-08-27")

  const previousWeek = model.periodState(cursor, selected, "week", -1)
  assert.equal(model.dayKey(previousWeek.cursorDate), "2026-08-20")
  assert.equal(model.dayKey(previousWeek.selectedDay), "2026-08-19")
})

test("calendar visibility removes only explicitly hidden opaque calendar keys", () => {
  const events = [
    { uid: "work", calendar_key: "work-key" },
    { uid: "todoist", calendar_key: "todoist-key" },
    { uid: "legacy-without-key" },
  ]

  assert.deepEqual(
    model.visibleCalendarEvents(events, ["todoist-key"]).map(event => event.uid),
    ["work", "legacy-without-key"],
  )
  assert.deepEqual(model.visibleCalendarEvents(events, []).map(event => event.uid), [
    "work", "todoist", "legacy-without-key",
  ])
})

test("events are filtered by local day and initial selection prefers upcoming", () => {
  const events = [
    { start: "2026-08-25T08:00:00-05:00", end: "2026-08-25T09:00:00-05:00" },
    { start: "2026-08-25T11:00:00-05:00", end: "2026-08-25T12:00:00-05:00" },
    { start: "2026-08-26T11:00:00-05:00", end: "2026-08-26T12:00:00-05:00" },
  ]
  const today = model.eventsForDay(events, new Date("2026-08-25T12:00:00-05:00"))
  assert.equal(today.length, 2)
  assert.equal(model.initialSelection(today, new Date("2026-08-25T10:00:00-05:00")), 1)
})

test("Now prefers an ongoing timed event, then the nearest timed event", () => {
  const events = [
    { uid: "all-day", all_day: true, start: "2026-08-27T00:00:00-05:00", end: "2026-08-28T00:00:00-05:00" },
    { uid: "past", all_day: false, start: "2026-08-27T08:00:00-05:00", end: "2026-08-27T09:00:00-05:00" },
    { uid: "ongoing", all_day: false, start: "2026-08-27T09:45:00-05:00", end: "2026-08-27T10:15:00-05:00" },
    { uid: "future", all_day: false, start: "2026-08-27T10:20:00-05:00", end: "2026-08-27T10:50:00-05:00" },
  ]
  const day = new Date("2026-08-27T10:00:00-05:00")

  assert.equal(model.nowSelectionUid(events, day, day), "ongoing")
  assert.equal(
    model.nowSelectionUid(events.filter(event => event.uid !== "ongoing"), day, day),
    "future",
  )
  assert.equal(model.nowSelectionUid([events[0]], day, day), "all-day")
  assert.equal(model.nowSelectionUid([], day, day), "")
})

test("selection reveal scrolls fully hidden rows into view and clamps to content", () => {
  assert.equal(model.revealOffset(260, 240, 120, 60, 900, 16), 104)
  assert.equal(model.revealOffset(100, 240, 390, 70, 900, 16), 236)
  assert.equal(model.revealOffset(10, 240, 0, 60, 900, 16), 0)
  assert.equal(model.revealOffset(600, 240, 870, 60, 900, 16), 660)
  assert.equal(model.revealOffset(80, 240, 120, 60, 200, 16), 0)
})

test("vertical movement reaches all-day events and clamps inside one day", () => {
  const events = [
    { uid: "timed-late", all_day: false, start: "2026-08-25T13:00:00-05:00", end: "2026-08-25T14:00:00-05:00" },
    { uid: "all-day", all_day: true, start: "2026-08-25T00:00:00-05:00", end: "2026-08-26T00:00:00-05:00" },
    { uid: "timed-early", all_day: false, start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "tomorrow", all_day: false, start: "2026-08-26T09:00:00-05:00", end: "2026-08-26T10:00:00-05:00" },
  ]
  const day = new Date("2026-08-25T12:00:00-05:00")

  assert.equal(model.moveWithinDay(events, day, "", 1), "all-day")
  assert.equal(model.moveWithinDay(events, day, "all-day", -1), "all-day")
  assert.equal(model.moveWithinDay(events, day, "all-day", 1), "timed-early")
  assert.equal(model.moveWithinDay(events, day, "timed-early", -1), "all-day")
  assert.equal(model.moveWithinDay(events, day, "timed-late", 1), "timed-late")
  assert.equal(model.moveWithinDay(events, new Date("2026-08-27T12:00:00-05:00"), "", 1), "")
})

test("horizontal movement preserves the closest vertical anchor", () => {
  const events = [
    { uid: "source", all_day: false, start: "2026-08-25T10:30:00-05:00", end: "2026-08-25T11:00:00-05:00" },
    { uid: "target-morning", all_day: false, start: "2026-08-26T10:00:00-05:00", end: "2026-08-26T10:30:00-05:00" },
    { uid: "target-afternoon", all_day: false, start: "2026-08-26T14:00:00-05:00", end: "2026-08-26T15:00:00-05:00" },
    { uid: "target-all-day", all_day: true, start: "2026-08-26T00:00:00-05:00", end: "2026-08-27T00:00:00-05:00" },
  ]
  const target = new Date("2026-08-26T12:00:00-05:00")

  assert.equal(model.closestUidForDay(events, target, model.eventByUid(events, "source")), "target-morning")
  assert.equal(model.closestUidForDay(events, target, { all_day: true }), "target-all-day")
  assert.equal(model.closestUidForDay(events, new Date("2026-08-27T12:00:00-05:00"), events[0]), "")
  assert.equal(model.dayKey(model.eventDay(events[0])), "2026-08-25")
  assert.equal(model.eventByUid(events, "missing"), null)
})

test("time grid positions duration and overlap columns", () => {
  const events = [
    { uid: "a", start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "b", start: "2026-08-25T09:30:00-05:00", end: "2026-08-25T10:30:00-05:00" },
    { uid: "c", start: "2026-08-25T10:00:00-05:00", end: "2026-08-25T11:00:00-05:00" },
    { uid: "solo", start: "2026-08-25T13:00:00-05:00", end: "2026-08-25T14:00:00-05:00" },
  ]
  assert.equal(model.timePosition(events[0], 60, 7), 120)
  assert.equal(model.durationHeight(events[0], 60), 60)
  assert.deepEqual(model.overlapColumns(events).map(event => event.column), [0, 1, 0, 0])
  assert.deepEqual(model.overlapColumns(events).map(event => event.columns), [2, 2, 2, 1])
  assert.deepEqual(model.overlapColumns(events).map(event => event.overlapGroup), [0, 0, 0, 1])
})

test("Week spatial movement uses overlap lanes before adjacent days", () => {
  const events = [
    { uid: "all-day", all_day: true, start: "2026-08-25T00:00:00-05:00", end: "2026-08-26T00:00:00-05:00" },
    { uid: "left", all_day: false, start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "right", all_day: false, start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "later", all_day: false, start: "2026-08-25T11:00:00-05:00", end: "2026-08-25T12:00:00-05:00" },
  ]
  const day = new Date("2026-08-25T12:00:00-05:00")

  assert.equal(model.moveAcrossOverlap(events, day, "left", 1), "right")
  assert.equal(model.moveAcrossOverlap(events, day, "right", -1), "left")
  assert.equal(model.moveAcrossOverlap(events, day, "right", 1), "")
  assert.equal(model.moveAcrossOverlap(events, day, "later", -1), "")
  assert.equal(model.moveWeekVertical(events, day, "all-day", 1), "left")
  assert.equal(model.moveWeekVertical(events, day, "left", -1), "all-day")
  assert.equal(model.moveWeekVertical(events, day, "left", 1), "later")
  assert.equal(model.moveWeekVertical(events, day, "right", 1), "later")
  assert.equal(model.overlapPosition(events, day, "left"), "1 of 2")
  assert.equal(model.overlapPosition(events, day, "right"), "2 of 2")
  assert.equal(model.overlapPosition(events, day, "later"), "")
})

test("event index lookup uses stable UIDs instead of object identity", () => {
  const events = [{ uid: "first" }, { uid: "second" }]

  assert.equal(model.eventIndexByUid(events, { uid: "second" }), 1)
  assert.equal(model.eventIndexByUid(events, { uid: "missing" }), -1)
})

test("cross-day movement preserves the overlap lane when times tie", () => {
  const events = [
    { uid: "source-left", all_day: false, start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "source-right", all_day: false, start: "2026-08-25T09:00:00-05:00", end: "2026-08-25T10:00:00-05:00" },
    { uid: "target-left", all_day: false, start: "2026-08-26T09:00:00-05:00", end: "2026-08-26T10:00:00-05:00" },
    { uid: "target-right", all_day: false, start: "2026-08-26T09:00:00-05:00", end: "2026-08-26T10:00:00-05:00" },
  ]
  const targetDay = new Date("2026-08-26T12:00:00-05:00")

  assert.equal(
    model.closestUidForDay(events, targetDay, model.eventByUid(events, "source-right")),
    "target-right",
  )
})

test("day filtering and duration stay correct across daylight saving boundaries", () => {
  const springForward = {
    uid: "dst-spring",
    start: "2026-03-08T01:30:00-06:00",
    end: "2026-03-08T03:30:00-05:00",
  }
  const fallBack = {
    uid: "dst-fall",
    start: "2026-11-01T01:30:00-05:00",
    end: "2026-11-01T01:30:00-06:00",
  }

  assert.deepEqual(
    model.eventsForDay([springForward], new Date("2026-03-08T12:00:00-05:00")).map(event => event.uid),
    ["dst-spring"],
  )
  assert.equal(model.durationHeight(springForward, 60), 60)
  assert.equal(model.durationHeight(fallBack, 60), 60)
})

test("clock format ring starts from the configured ISO label", () => {
  const ring = model.clockFormatRing("yyyy/MM/dd HH:mm", "dddd yyyy/MM/dd HH:mm")
  assert.equal(ring[0], "yyyy/MM/dd HH:mm")
  assert.equal(model.nextClockFormat(ring, ring[0]), "dddd yyyy/MM/dd HH:mm")
})

test("header update status is concise and reports the stalest connected provider", () => {
  const now = new Date("2026-08-27T12:00:00Z")
  assert.equal(model.updateStatus([], now), "No accounts")
  assert.equal(model.updateStatus([{ stale: true, last_sync: "2026-08-27T11:59:00Z" }], now), "Offline")
  assert.equal(model.updateStatus([{ stale: false, last_sync: "2026-08-27T11:59:45Z" }], now), "Updated just now")
  assert.equal(model.updateStatus([
    { stale: false, last_sync: "2026-08-27T11:58:00Z" },
    { stale: false, last_sync: "2026-08-27T11:55:00Z" },
  ], now), "Updated 5m ago")
  assert.equal(model.updateStatus([{ stale: false, last_sync: "2026-08-27T09:00:00Z" }], now), "Updated 3h ago")
  assert.equal(model.updateStatus([{ stale: false, last_sync: "not-a-date" }], now), "Connected")
})

test("provider labels use the product names shown to people", () => {
  assert.equal(model.providerLabel("google"), "Google")
  assert.equal(model.providerLabel("microsoft"), "Outlook")
  assert.equal(model.providerLabel("caldav"), "caldav")
  assert.equal(model.providerLabel(""), "Unknown")
})
