// SPDX-License-Identifier: GPL-3.0-or-later
var MS_PER_DAY = 86400000
var DEFAULT_FORMATS = [
  "yyyy/MM/dd HH:mm",
  "dddd yyyy/MM/dd HH:mm",
  "HH:mm",
  "dddd HH:mm"
]

function pad2(value) {
  return (Number(value) < 10 ? "0" : "") + Number(value)
}

function dayKey(value) {
  var date = value instanceof Date ? value : new Date(value)
  return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate())
}

function localMidnight(value) {
  var date = value instanceof Date ? new Date(value.getTime()) : new Date(value)
  date.setHours(0, 0, 0, 0)
  return date
}

function addDays(value, amount) {
  var date = localMidnight(value)
  date.setDate(date.getDate() + Number(amount || 0))
  return date
}

function startOfWeek(value) {
  var date = localMidnight(value)
  var mondayOffset = (date.getDay() + 6) % 7
  date.setDate(date.getDate() - mondayOffset)
  return date
}

function weekDays(value) {
  var start = startOfWeek(value)
  var days = []
  for (var i = 0; i < 7; i++) days.push(addDays(start, i))
  return days
}

function periodState(cursorDate, selectedDay, view, amount) {
  var distance = Number(amount || 0) * (view === "week" ? 7 : 1)
  return {
    cursorDate: addDays(cursorDate, distance),
    selectedDay: addDays(selectedDay, distance)
  }
}

function visibleCalendarEvents(events, hiddenCalendarKeys) {
  var hidden = hiddenCalendarKeys || []
  if (hidden.length === 0) return events || []
  return (events || []).filter(function(event) {
    return !event.calendar_key || hidden.indexOf(String(event.calendar_key)) === -1
  })
}

function eventsForRange(events, start, end) {
  var from = new Date(start).getTime()
  var to = new Date(end).getTime()
  return (events || []).filter(function(event) {
    return new Date(event.end).getTime() > from && new Date(event.start).getTime() < to
  }).sort(function(a, b) {
    if (Boolean(a.all_day) !== Boolean(b.all_day)) return a.all_day ? -1 : 1
    return new Date(a.start).getTime() - new Date(b.start).getTime()
  })
}

function eventsForDay(events, value) {
  var start = localMidnight(value)
  return eventsForRange(events, start, addDays(start, 1))
}

function eventsForWeek(events, value) {
  var start = startOfWeek(value)
  return eventsForRange(events, start, addDays(start, 7))
}

function eventByUid(events, uid) {
  for (var i = 0; i < (events || []).length; i++)
    if (String(events[i].uid || "") === String(uid || "")) return events[i]
  return null
}

function eventIndexByUid(events, eventOrUid) {
  var uid = eventOrUid && typeof eventOrUid === "object" ? eventOrUid.uid : eventOrUid
  for (var i = 0; i < (events || []).length; i++)
    if (String(events[i].uid || "") === String(uid || "")) return i
  return -1
}

function eventDay(event) {
  return event && event.start ? localMidnight(event.start) : null
}

function moveWithinDay(events, value, uid, amount) {
  var ordered = eventsForDay(events, value)
  if (ordered.length === 0) return ""
  var current = -1
  for (var i = 0; i < ordered.length; i++)
    if (String(ordered[i].uid || "") === String(uid || "")) { current = i; break }
  if (current < 0) return String(ordered[Number(amount) < 0 ? ordered.length - 1 : 0].uid || "")
  var target = Math.max(0, Math.min(ordered.length - 1, current + Number(amount || 0)))
  return String(ordered[target].uid || "")
}

function verticalAnchor(event) {
  if (!event || event.all_day) return -1
  var start = new Date(event.start)
  return start.getHours() * 60 + start.getMinutes()
}

function closestUidForDay(events, value, anchorEvent) {
  var ordered = eventsForDay(events, value)
  if (ordered.length === 0) return ""
  if (!anchorEvent) return String(ordered[0].uid || "")
  var allDay = ordered.filter(function(event) { return event.all_day })
  if (anchorEvent.all_day)
    return String((allDay[0] || ordered[0]).uid || "")
  var timed = overlapColumns(ordered.filter(function(event) { return !event.all_day }))
  if (timed.length === 0) return String(allDay[0].uid || "")

  var anchor = verticalAnchor(anchorEvent)
  var sourceColumn = 0
  var sourceDay = eventDay(anchorEvent)
  if (sourceDay) {
    var sourceLayout = overlapColumns(eventsForDay(events, sourceDay).filter(function(event) { return !event.all_day }))
    for (var sourceIndex = 0; sourceIndex < sourceLayout.length; sourceIndex++)
      if (String(sourceLayout[sourceIndex].uid || "") === String(anchorEvent.uid || "")) {
        sourceColumn = sourceLayout[sourceIndex].column
        break
      }
  }
  var best = timed[0]
  var bestDistance = Math.abs(verticalAnchor(best) - anchor)
  var bestColumnDistance = Math.abs(best.column - sourceColumn)
  for (var i = 1; i < timed.length; i++) {
    var distance = Math.abs(verticalAnchor(timed[i]) - anchor)
    var columnDistance = Math.abs(timed[i].column - sourceColumn)
    if (distance < bestDistance || (distance === bestDistance && columnDistance < bestColumnDistance)) {
      best = timed[i]
      bestDistance = distance
      bestColumnDistance = columnDistance
    }
  }
  return String(best.uid || "")
}

function initialSelection(events, now) {
  if (!events || events.length === 0) return -1
  var current = (now instanceof Date ? now : new Date(now)).getTime()
  for (var i = 0; i < events.length; i++)
    if (new Date(events[i].end).getTime() > current) return i
  return events.length - 1
}

function nowSelectionUid(events, value, now) {
  var ordered = eventsForDay(events, value)
  if (ordered.length === 0) return ""
  var current = (now instanceof Date ? now : new Date(now)).getTime()
  var timed = ordered.filter(function(event) { return !event.all_day })
  if (timed.length === 0) return String(ordered[0].uid || "")
  var best = timed[0]
  var bestDistance = Infinity
  for (var i = 0; i < timed.length; i++) {
    var start = new Date(timed[i].start).getTime()
    var end = new Date(timed[i].end).getTime()
    var distance = current < start ? start - current : current >= end ? current - end : 0
    if (distance < bestDistance || (distance === bestDistance && start >= current)) {
      best = timed[i]
      bestDistance = distance
    }
  }
  return String(best.uid || "")
}

function revealOffset(currentOffset, viewportSize, itemStart, itemSize, contentSize, padding) {
  var maximum = Math.max(0, Number(contentSize) - Number(viewportSize))
  var next = Math.max(0, Math.min(maximum, Number(currentOffset)))
  var inset = Math.max(0, Number(padding || 0))
  if (Number(itemStart) < next + inset)
    next = Number(itemStart) - inset
  else if (Number(itemStart) + Number(itemSize) > next + Number(viewportSize) - inset)
    next = Number(itemStart) + Number(itemSize) - Number(viewportSize) + inset
  return Math.max(0, Math.min(maximum, next))
}

function timePosition(event, hourHeight, startHour) {
  var start = new Date(event.start)
  var minutes = start.getHours() * 60 + start.getMinutes() - Number(startHour || 0) * 60
  return Math.max(0, minutes * Number(hourHeight) / 60)
}

function durationHeight(event, hourHeight) {
  var minutes = Math.max(1, (new Date(event.end).getTime() - new Date(event.start).getTime()) / 60000)
  return Math.max(22, minutes * Number(hourHeight) / 60)
}

function overlapColumns(events) {
  var sorted = (events || []).slice().sort(function(a, b) {
    return new Date(a.start).getTime() - new Date(b.start).getTime()
  })
  var mapped = []
  var ends = []
  var group = 0
  var groupStart = 0
  var groupEnd = -Infinity
  for (var i = 0; i < sorted.length; i++) {
    var start = new Date(sorted[i].start).getTime()
    if (mapped.length > groupStart && start >= groupEnd) {
      for (var finished = groupStart; finished < mapped.length; finished++)
        mapped[finished].columns = Math.max(1, ends.length)
      group++
      groupStart = mapped.length
      groupEnd = -Infinity
      ends = []
    }
    var column = 0
    while (column < ends.length && start < ends[column]) column++
    if (column === ends.length) ends.push(0)
    var end = new Date(sorted[i].end).getTime()
    ends[column] = end
    groupEnd = Math.max(groupEnd, end)
    var copy = {}
    for (var key in sorted[i]) copy[key] = sorted[i][key]
    copy.column = column
    copy.overlapGroup = group
    mapped.push(copy)
  }
  for (var remaining = groupStart; remaining < mapped.length; remaining++)
    mapped[remaining].columns = Math.max(1, ends.length)
  return mapped
}

function timedLayoutForDay(events, value) {
  return overlapColumns(eventsForDay(events, value).filter(function(event) { return !event.all_day }))
}

function moveAcrossOverlap(events, value, uid, amount) {
  var layout = timedLayoutForDay(events, value)
  var current = eventByUid(layout, uid)
  if (!current || current.columns < 2) return ""
  var targetColumn = current.column + (Number(amount) < 0 ? -1 : 1)
  if (targetColumn < 0 || targetColumn >= current.columns) return ""
  var currentStart = new Date(current.start).getTime()
  var currentEnd = new Date(current.end).getTime()
  var candidates = layout.filter(function(event) {
    return event.overlapGroup === current.overlapGroup && event.column === targetColumn
  })
  if (candidates.length === 0) return ""
  var direct = candidates.filter(function(event) {
    return new Date(event.start).getTime() < currentEnd && new Date(event.end).getTime() > currentStart
  })
  if (direct.length > 0) candidates = direct
  var best = candidates[0]
  var bestDistance = Math.abs(new Date(best.start).getTime() - currentStart)
  for (var i = 1; i < candidates.length; i++) {
    var distance = Math.abs(new Date(candidates[i].start).getTime() - currentStart)
    if (distance < bestDistance) {
      best = candidates[i]
      bestDistance = distance
    }
  }
  return String(best.uid || "")
}

function moveWeekVertical(events, value, uid, amount) {
  var ordered = eventsForDay(events, value)
  if (ordered.length === 0) return ""
  var direction = Number(amount) < 0 ? -1 : 1
  var allDay = ordered.filter(function(event) { return event.all_day })
  var layout = timedLayoutForDay(events, value)
  var current = eventByUid(ordered, uid)
  if (!current) {
    if (direction < 0) return String((layout[layout.length - 1] || allDay[allDay.length - 1]).uid || "")
    return String((allDay[0] || layout[0]).uid || "")
  }
  if (current.all_day) {
    var allDayIndex = eventIndexByUid(allDay, current)
    var allDayTarget = allDayIndex + direction
    if (allDayTarget >= 0 && allDayTarget < allDay.length) return String(allDay[allDayTarget].uid || "")
    if (direction > 0 && layout.length > 0) return String(layout[0].uid || "")
    return String(current.uid || "")
  }

  var positioned = eventByUid(layout, uid)
  var currentStart = new Date(current.start).getTime()
  var candidates = layout.filter(function(event) {
    var start = new Date(event.start).getTime()
    return direction > 0 ? start > currentStart : start < currentStart
  })
  if (candidates.length === 0) {
    if (direction < 0 && allDay.length > 0) return String(allDay[allDay.length - 1].uid || "")
    return String(current.uid || "")
  }
  var best = candidates[0]
  var bestDistance = Math.abs(new Date(best.start).getTime() - currentStart)
  var bestColumnDistance = Math.abs(best.column - positioned.column)
  for (var i = 1; i < candidates.length; i++) {
    var distance = Math.abs(new Date(candidates[i].start).getTime() - currentStart)
    var columnDistance = Math.abs(candidates[i].column - positioned.column)
    if (distance < bestDistance || (distance === bestDistance && columnDistance < bestColumnDistance)) {
      best = candidates[i]
      bestDistance = distance
      bestColumnDistance = columnDistance
    }
  }
  return String(best.uid || "")
}

function overlapPosition(events, value, uid) {
  var current = eventByUid(timedLayoutForDay(events, value), uid)
  if (!current || current.columns < 2) return ""
  return String(current.column + 1) + " of " + String(current.columns)
}

function formatTime(event) {
  if (!event) return ""
  if (event.all_day) return "All day"
  var start = new Date(event.start)
  var end = new Date(event.end)
  return QtDate(start) + " to " + QtDate(end)
}

function QtDate(date) {
  var hours = date.getHours()
  var minutes = pad2(date.getMinutes())
  return pad2(hours) + ":" + minutes
}

function clockFormatRing(configured, alternate) {
  var ring = []
  var values = [configured, alternate].concat(DEFAULT_FORMATS)
  for (var i = 0; i < values.length; i++) {
    var value = String(values[i] || "")
    if (value && ring.indexOf(value) === -1) ring.push(value)
  }
  return ring
}

function nextClockFormat(ring, current) {
  if (!ring || ring.length === 0) return ""
  var index = ring.indexOf(String(current || ""))
  return ring[(index + 1 + ring.length) % ring.length]
}

function providerLabel(provider) {
  var key = String(provider || "")
  if (key === "google") return "Google"
  if (key === "microsoft") return "Outlook"
  return key || "Unknown"
}

function updateStatus(providers, now) {
  if (!providers || providers.length === 0) return "No accounts"
  var unhealthy = []
  var healthy = 0
  for (var i = 0; i < providers.length; i++) {
    if (providers[i].stale || providers[i].connected === false) unhealthy.push(providers[i])
    else healthy++
  }
  if (unhealthy.length > 0) {
    var disconnected = unhealthy.filter(function(provider) { return provider.connected === false })
    if (disconnected.length === 1) return providerLabel(disconnected[0].provider) + " needs reconnect"
    if (disconnected.length > 1) return "Accounts need reconnect"
    if (healthy > 0 && unhealthy.length === 1) return providerLabel(unhealthy[0].provider) + " stale"
    if (healthy > 0) return "Some calendars stale"
    return "Offline, cached"
  }

  var oldest = Infinity
  for (var j = 0; j < providers.length; j++) {
    var timestamp = new Date(providers[j].last_sync || "").getTime()
    if (!isNaN(timestamp)) oldest = Math.min(oldest, timestamp)
  }
  if (oldest === Infinity) return "Connected"

  var current = (now instanceof Date ? now : new Date(now)).getTime()
  var minutes = Math.max(0, Math.floor((current - oldest) / 60000))
  if (minutes < 1) return "Updated just now"
  if (minutes < 60) return "Updated " + minutes + "m ago"
  var hours = Math.floor(minutes / 60)
  if (hours < 24) return "Updated " + hours + "h ago"
  return "Updated " + Math.floor(hours / 24) + "d ago"
}

if (typeof module !== "undefined") module.exports = {
  dayKey: dayKey,
  localMidnight: localMidnight,
  addDays: addDays,
  startOfWeek: startOfWeek,
  weekDays: weekDays,
  periodState: periodState,
  visibleCalendarEvents: visibleCalendarEvents,
  eventsForRange: eventsForRange,
  eventsForDay: eventsForDay,
  eventsForWeek: eventsForWeek,
  eventByUid: eventByUid,
  eventIndexByUid: eventIndexByUid,
  eventDay: eventDay,
  moveWithinDay: moveWithinDay,
  closestUidForDay: closestUidForDay,
  initialSelection: initialSelection,
  nowSelectionUid: nowSelectionUid,
  revealOffset: revealOffset,
  timePosition: timePosition,
  durationHeight: durationHeight,
  overlapColumns: overlapColumns,
  moveAcrossOverlap: moveAcrossOverlap,
  moveWeekVertical: moveWeekVertical,
  overlapPosition: overlapPosition,
  formatTime: formatTime,
  clockFormatRing: clockFormatRing,
  nextClockFormat: nextClockFormat,
  providerLabel: providerLabel,
  updateStatus: updateStatus
}
