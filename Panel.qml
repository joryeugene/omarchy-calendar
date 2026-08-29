// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "CalendarModel.js" as CalendarModel
import "SettingsModel.js" as SettingsModel

Panel {
  id: root
  moduleName: "io.github.joryeugene.omarchy-calendar"
  ipcTarget: "io.github.joryeugene.omarchy-calendar"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  property var calendarService: null
  readonly property string helperPath: calendarService ? calendarService.helperPath : ""
  readonly property var barIdentity: hostWidget || root

  property string activeTab: "today"
  property date cursorDate: new Date()
  property date selectedDay: new Date()
  property date nowTime: new Date()
  property string selectedUid: ""
  property var pendingAnchorEvent: null
  property var cachedEvents: []
  property var calendars: []
  property var providers: []
  property bool demoData: false
  property bool loading: false
  property bool showHelp: false
  property bool showSettings: false
  property bool showSetup: false
  property bool expandedDetails: false
  property string setupProvider: ""
  property var setupProviders: [
    { provider: "google", label: "Google", client_configured: false, connected: false, accounts: 0, stale: false, last_sync: "", last_error: "" },
    { provider: "microsoft", label: "Outlook", client_configured: false, connected: false, accounts: 0, stale: false, last_sync: "", last_error: "" }
  ]
  property bool accountBusy: false
  property string accountError: ""
  property string errorText: ""
  property string actionError: ""
  property string pendingDisconnect: ""
  property bool pendingReset: false
  property bool pendingNow: false
  property bool viewReloadPending: false
  property var settingsSnapshot: SettingsModel.normalize({})
  property var settingsDraft: SettingsModel.normalize({})

  readonly property var appliedSettings: SettingsModel.normalize(settings)
  readonly property var previewSettings: showSettings ? settingsDraft : appliedSettings
  readonly property int motionDuration: previewSettings.animations ? 140 : 0
  readonly property real textScale: Number(previewSettings.textScale || 1)
  readonly property var palette: SettingsModel.palette(previewSettings.theme, {
    background: Color.background,
    surface: Color.popups.background,
    foreground: bar ? bar.foreground : Color.foreground,
    muted: Color.muted,
    accent: Color.accent,
    urgent: Color.urgent
  })
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property var events: CalendarModel.visibleCalendarEvents(cachedEvents, previewSettings.hiddenCalendars)
  readonly property bool filteredEmpty: cachedEvents.length > 0 && events.length === 0
  readonly property var dayEvents: CalendarModel.eventsForDay(events, cursorDate)
  readonly property var weekEvents: CalendarModel.eventsForWeek(events, cursorDate)
  readonly property var visibleEvents: activeTab === "today" ? dayEvents : weekEvents
  readonly property var selectedEvent: CalendarModel.eventByUid(visibleEvents, selectedUid)
  readonly property var weekDays: CalendarModel.weekDays(cursorDate)
  readonly property int hourHeight: Style.space(previewSettings.density === "roomy" ? 68 : 46)
  readonly property int gridStartHour: Number(previewSettings.weekStartHour)
  readonly property int gridEndHour: Number(previewSettings.weekEndHour)
  readonly property bool syncing: calendarService ? calendarService.syncing : false
  readonly property string updateStatus: root.demoData ? "Demo" : root.syncing ? "Updating" : CalendarModel.updateStatus(root.providers, root.nowTime)

  Timer {
    interval: 60000
    running: root.opened
    repeat: true
    triggeredOnStart: true
    onTriggered: root.nowTime = new Date()
  }

  Component.onCompleted: {
    root.activeTab = root.appliedSettings.defaultView
    root.settingsDraft = SettingsModel.normalize(root.settings)
    if (root.calendarService)
      root.calendarService.syncIntervalMinutes = root.appliedSettings.syncIntervalMinutes
  }

  function open() {
    root.controller.show()
    Qt.callLater(function() {
      if (!root.opened) return
      root.setCenterHoverRevealSuppressed(true)
      root.loadView()
      root.loadSetupStatus()
    })
  }
  function close() {
    root.setCenterHoverRevealSuppressed(false)
    root.showHelp = false
    root.showSettings = false
    root.showSetup = false
    root.pendingReset = false
    root.pendingDisconnect = ""
    root.controller.hide()
  }
  function toggle() { root.opened ? root.close() : root.open() }
  function refresh() { root.loadView() }
  function closeForPopoutSwitch() { root.close() }
  function setCenterHoverRevealSuppressed(value) {
    if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
  }
  function switchPanel(direction) {
    if (root.bar && root.bar.switchPanelFrom)
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }
  function helperCommand(arguments) {
    return helperPath ? [helperPath].concat(arguments) : []
  }
  function queryStart() {
    return (activeTab === "today" ? CalendarModel.localMidnight(cursorDate)
      : CalendarModel.startOfWeek(cursorDate)).toISOString()
  }
  function queryEnd() {
    var start = activeTab === "today" ? CalendarModel.localMidnight(cursorDate)
      : CalendarModel.startOfWeek(cursorDate)
    return CalendarModel.addDays(start, activeTab === "today" ? 1 : 7).toISOString()
  }
  function loadView() {
    if (viewProcess.running) {
      viewReloadPending = true
      return
    }
    viewReloadPending = false
    loading = true
    errorText = ""
    if (!helperPath) {
      loading = false
      errorText = "Calendar helper is unavailable"
      return
    }
    viewProcess.command = helperCommand(["view", "--from", queryStart(), "--to", queryEnd()])
    viewProcess.running = true
  }
  function applyView(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      cachedEvents = payload.events || []
      calendars = payload.calendars || []
      providers = payload.providers || []
      demoData = payload.demo === true
      var dayItems = CalendarModel.eventsForDay(events, selectedDay)
      var revealNow = pendingNow
      if (pendingNow)
        selectedUid = CalendarModel.nowSelectionUid(events, selectedDay, nowTime)
      else if (pendingAnchorEvent)
        selectedUid = CalendarModel.closestUidForDay(events, selectedDay, pendingAnchorEvent)
      else if (!CalendarModel.eventByUid(dayItems, selectedUid)) {
        var initialIndex = CalendarModel.initialSelection(dayItems, new Date())
        selectedUid = initialIndex >= 0 ? String(dayItems[initialIndex].uid || "") : ""
      }
      pendingNow = false
      pendingAnchorEvent = null
      errorText = ""
      if (revealNow) Qt.callLater(function() {
        if (root.activeTab === "week") weekSurface.showNow()
        else todaySurface.revealSelectedEvent()
      })
    } catch (error) {
      errorText = "Could not read the local calendar cache"
    }
  }
  function refreshProviders() {
    if (!calendarService) {
      errorText = "Calendar service is unavailable"
      return
    }
    calendarService.requestSync()
  }
  function loadSetupStatus() {
    if (!helperPath || setupProcess.running) return
    setupProcess.command = helperCommand(["setup-status"])
    setupProcess.running = true
  }
  function applySetupStatus(raw) {
    try {
      var payload = JSON.parse(String(raw || "{}"))
      setupProviders = payload.providers || setupProviders
      demoData = payload.demo === true
    } catch (error) {
      accountError = "Could not read account setup status"
    }
  }
  function providerSetup(provider) {
    for (var i = 0; i < setupProviders.length; i++)
      if (setupProviders[i].provider === provider) return setupProviders[i]
    return { provider: provider, label: provider, client_configured: false, connected: false }
  }
  function providerStatusFor(event) {
    if (!event) return ""
    for (var i = 0; i < providers.length; i++) {
      if (providers[i].provider === event.provider && providers[i].account_id === event.account_id) {
        if (providers[i].stale) return "Offline, showing cached data"
        return CalendarModel.updateStatus([providers[i]], root.nowTime)
      }
    }
    return demoData ? "Demo data" : "Local cache"
  }
  function setTab(tab) {
    activeTab = tab
    cursorDate = selectedDay
    selectedUid = ""
    loadView()
  }
  function moveSelection(amount) {
    selectedUid = activeTab === "week"
      ? CalendarModel.moveWeekVertical(events, selectedDay, selectedUid, amount)
      : CalendarModel.moveWithinDay(events, selectedDay, selectedUid, amount)
  }
  function moveHorizontal(amount) {
    if (activeTab === "week") {
      var overlapTarget = CalendarModel.moveAcrossOverlap(events, selectedDay, selectedUid, amount)
      if (overlapTarget) {
        selectedUid = overlapTarget
        return
      }
    }
    moveDay(amount)
  }
  function moveDay(amount) {
    var anchor = selectedEvent
    var previousWeek = CalendarModel.dayKey(CalendarModel.startOfWeek(selectedDay))
    selectedDay = CalendarModel.addDays(selectedDay, amount)
    cursorDate = selectedDay
    selectedUid = CalendarModel.closestUidForDay(events, selectedDay, anchor)
    if (activeTab === "today" || previousWeek !== CalendarModel.dayKey(CalendarModel.startOfWeek(selectedDay))) {
      pendingAnchorEvent = anchor
      loadView()
    }
  }
  function stepPeriod(amount) {
    pendingAnchorEvent = selectedEvent
    var next = CalendarModel.periodState(cursorDate, selectedDay, activeTab, amount)
    cursorDate = next.cursorDate
    selectedDay = next.selectedDay
    selectedUid = ""
    loadView()
  }
  function goCurrent() {
    nowTime = new Date()
    cursorDate = nowTime
    selectedDay = cursorDate
    selectedUid = ""
    pendingAnchorEvent = null
    pendingNow = true
    loadView()
  }
  function selectUid(uid, day) {
    selectedUid = String(uid || "")
    var event = CalendarModel.eventByUid(visibleEvents, selectedUid)
    selectedDay = day || CalendarModel.eventDay(event) || selectedDay
    cursorDate = selectedDay
  }
  function openMeeting() {
    if (!selectedEvent || !selectedEvent.meeting_url || actionProcess.running) return
    actionProcess.command = helperCommand(["open-meeting", selectedEvent.uid])
    actionProcess.running = true
  }
  function openSource() {
    if (!selectedEvent || !selectedEvent.provider_url || actionProcess.running) return
    actionProcess.command = helperCommand(["open-source", selectedEvent.uid])
    actionProcess.running = true
  }
  function seedDemo() {
    if (demoProcess.running) return
    demoProcess.command = helperCommand(["demo", "seed"])
    demoProcess.running = true
  }
  function openSettings(section) {
    root.showHelp = false
    root.showSetup = false
    root.settingsSnapshot = SettingsModel.normalize(root.settings)
    root.settingsDraft = SettingsModel.normalize(root.settings)
    root.showSettings = true
    settingsSurface.sectionIndex = Math.max(0, Math.min(3, Number(section || 0)))
    settingsSurface.controlIndex = 0
  }
  function updateDraft(key, value) {
    root.settingsDraft = SettingsModel.withValue(root.settingsDraft, key, value)
    if (key === "hiddenCalendars") Qt.callLater(root.ensureVisibleSelection)
  }
  function ensureVisibleSelection() {
    var dayItems = CalendarModel.eventsForDay(root.events, root.selectedDay)
    if (CalendarModel.eventByUid(dayItems, root.selectedUid)) return
    var index = CalendarModel.initialSelection(dayItems, root.nowTime)
    root.selectedUid = index >= 0 ? String(dayItems[index].uid || "") : ""
  }
  function persistSettings(values) {
    var entry = { id: root.moduleName }
    for (var existing in root.settings) if (existing !== "id" && existing !== "motion") entry[existing] = root.settings[existing]
    for (var key in values) entry[key] = values[key]
    root.settings = entry
    if (root.hostWidget && "settings" in root.hostWidget) root.hostWidget.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }
  function applySettings() {
    var next = SettingsModel.normalize(root.settingsDraft)
    persistSettings(next)
    if (calendarService) calendarService.syncIntervalMinutes = next.syncIntervalMinutes
    root.showSettings = false
    root.pendingReset = false
  }
  function cancelSettings() {
    root.settingsDraft = SettingsModel.normalize(root.settingsSnapshot)
    root.showSettings = false
    root.pendingReset = false
    root.pendingDisconnect = ""
    Qt.callLater(root.ensureVisibleSelection)
  }
  function openSetup(provider) {
    root.setupProvider = provider
    setupSurface.clearDraft()
    root.accountError = ""
    root.showSettings = false
    root.showSetup = true
  }
  function configureClient(provider, clientId) {
    if (configureProcess.running || !String(clientId || "").trim()) return
    root.setupProvider = provider
    root.accountBusy = true
    root.accountError = ""
    configureProcess.command = helperCommand(["configure-client", provider, String(clientId).trim()])
    configureProcess.running = true
  }
  function importGoogleDesktop(source) {
    if (importProcess.running || !String(source || "").trim()) return
    root.setupProvider = "google"
    root.accountBusy = true
    root.accountError = ""
    importProcess.command = helperCommand(["import-google-desktop-app", String(source)])
    importProcess.running = true
  }
  function authenticate(provider) {
    if (authProcess.running) return
    root.setupProvider = provider
    root.accountBusy = true
    root.accountError = ""
    authProcess.command = helperCommand(["auth", provider])
    authProcess.running = true
  }
  function requestDisconnect(provider) {
    if (pendingDisconnect !== provider) {
      pendingDisconnect = provider
      return
    }
    pendingDisconnect = ""
    accountBusy = true
    disconnectProcess.command = helperCommand(["disconnect", provider])
    disconnectProcess.running = true
  }
  function requestReset() {
    if (!pendingReset) {
      pendingReset = true
      return
    }
    if (resetProcess.running) return
    accountBusy = true
    resetProcess.command = helperCommand(["reset-local-data"])
    resetProcess.running = true
  }

  Process {
    id: viewProcess
    stdout: StdioCollector { onStreamFinished: root.applyView(text) }
    stderr: StdioCollector { id: viewError; waitForEnd: true }
    onExited: function(exitCode) {
      root.loading = false
      if (exitCode !== 0 && root.events.length === 0)
        root.errorText = String(viewError.text || "Calendar helper failed").trim()
      if (root.viewReloadPending) Qt.callLater(root.loadView)
    }
  }
  Process {
    id: setupProcess
    stdout: StdioCollector { onStreamFinished: root.applySetupStatus(text) }
    stderr: StdioCollector { id: setupError; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.accountError = String(setupError.text || "Account status failed").trim()
    }
  }
  Process {
    id: configureProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: configureError; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode === 0) root.authenticate(root.setupProvider)
      else {
        root.accountBusy = false
        root.accountError = String(configureError.text || "Could not save the public client ID").trim()
      }
      root.loadSetupStatus()
    }
  }
  Process {
    id: importProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: importError; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode === 0) root.authenticate("google")
      else {
        root.accountBusy = false
        root.accountError = String(importError.text || "Could not import Google Desktop credentials").trim()
      }
      root.loadSetupStatus()
    }
  }
  Process {
    id: authProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: authError; waitForEnd: true }
    onExited: function(exitCode) {
      root.accountBusy = false
      if (exitCode !== 0) root.accountError = String(authError.text || "Connection failed").trim()
      else {
        root.showSetup = false
        root.openSettings(0)
      }
      root.loadView()
      root.loadSetupStatus()
    }
  }
  Process {
    id: disconnectProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: disconnectError; waitForEnd: true }
    onExited: function(exitCode) {
      root.accountBusy = false
      if (exitCode !== 0) root.accountError = String(disconnectError.text || "Disconnect failed").trim()
      root.loadView()
      root.loadSetupStatus()
    }
  }
  Process {
    id: resetProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: resetError; waitForEnd: true }
    onExited: function(exitCode) {
      root.accountBusy = false
      root.pendingReset = false
      if (exitCode !== 0) root.accountError = String(resetError.text || "Reset failed").trim()
      root.loadView()
      root.loadSetupStatus()
    }
  }
  Process {
    id: demoProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: demoError; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0) root.errorText = String(demoError.text || "Demo setup failed").trim()
      root.loadView()
      root.loadSetupStatus()
    }
  }
  Process {
    id: actionProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: actionStderr; waitForEnd: true }
    onExited: function(exitCode) {
      root.actionError = exitCode === 0 ? "" : String(actionStderr.text || "Action unavailable").trim()
    }
  }

  Connections {
    target: root.calendarService
    function onRevisionChanged() {
      if (root.calendarService && root.calendarService.lastError)
        root.errorText = root.calendarService.lastError
      root.loadView()
      root.loadSetupStatus()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(1080))
    contentHeight: panel.fittedContentHeight(Style.space(720))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: root.showSetup && setupSurface.inputFocused
      onMoveRequested: function(dx, dy) {
        if (root.showSettings) {
          if (dx !== 0) settingsSurface.moveSection(dx)
          else if (dy !== 0) settingsSurface.moveControl(dy)
        } else if (!root.showHelp && !root.showSetup) {
          if (dx !== 0) root.moveHorizontal(dx)
          else if (dy !== 0) root.moveSelection(dy)
        }
      }
      onActivateRequested: {
        if (root.showSetup) setupSurface.activatePrimary()
        else if (root.showSettings) settingsSurface.activateCurrent()
        else root.expandedDetails = !root.expandedDetails
      }
      onCloseRequested: root.handleEscape()
      onTabRequested: function(direction) { if (!root.showSettings && !root.showSetup) root.switchPanel(direction) }
      onTextKey: function(text) {
        if (text === "?" && !root.showSetup) {
          root.showHelp = !root.showHelp
          return
        }
        if (root.showHelp) return
        if (root.showSettings) {
          if (text === "a") root.applySettings()
          else if (text === "h") settingsSurface.moveSection(-1)
          else if (text === "l") settingsSurface.moveSection(1)
          else if (text === "j") settingsSurface.moveControl(1)
          else if (text === "k") settingsSurface.moveControl(-1)
          else if (text === "c") { settingsSurface.sectionIndex = 0; settingsSurface.controlIndex = 0 }
          return
        }
        if (root.showSetup) return
        if (text === "t") root.setTab("today")
        else if (text === "w") root.setTab("week")
        else if (text === "j") root.moveSelection(1)
        else if (text === "k") root.moveSelection(-1)
        else if (text === "h") root.moveHorizontal(-1)
        else if (text === "l") root.moveHorizontal(1)
        else if (text === "[") root.stepPeriod(-1)
        else if (text === "]") root.stepPeriod(1)
        else if (text === "g") root.goCurrent()
        else if (text === "m") root.openMeeting()
        else if (text === "o") root.openSource()
        else if (text === "c") root.openSettings(0)
        else if (text === "s") root.openSettings(1)
        else if (text === "r") root.refreshProviders()
      }
      Rectangle {
        anchors.fill: parent
        color: root.palette.background

        Column {
          anchors.fill: parent

          Rectangle {
            width: parent.width
            height: Style.space(58)
            color: root.palette.surface
            border.color: root.palette.border
            border.width: 0

            Text {

              textFormat: Text.PlainText
              anchors.left: parent.left
              anchors.leftMargin: Style.space(18)
              anchors.verticalCenter: parent.verticalCenter
              text: "FLIGHT DECK"
              color: root.palette.accent
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body * root.textScale
              font.bold: true
              font.letterSpacing: 1.2
            }

            Row {
              anchors.centerIn: parent
              spacing: Style.space(8)
              Repeater {
                model: [{ key: "today", label: "t  Today" }, { key: "week", label: "w  Week" }]
                Rectangle {
                  required property var modelData
                  width: Style.space(108)
                  height: Style.space(34)
                  radius: Style.space(6)
                  color: root.activeTab === modelData.key ? root.palette.accent : "transparent"
                  border.color: root.activeTab === modelData.key ? root.palette.accent : root.palette.border
                  border.width: 1
                  Behavior on color { enabled: root.motionDuration > 0; ColorAnimation { duration: root.motionDuration } }
                  Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: modelData.label; color: root.activeTab === modelData.key ? root.palette.background : root.palette.foreground; font.family: root.contentFontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
                  MouseArea { anchors.fill: parent; onClicked: root.setTab(modelData.key) }
                }
              }
            }

            Row {
              anchors.right: parent.right
              anchors.rightMargin: Style.space(16)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(10)
              Text { textFormat: Text.PlainText; text: root.updateStatus; color: root.demoData ? "#e0af68" : root.syncing ? root.palette.accent : root.updateStatus === "Offline" ? root.palette.urgent : root.palette.muted; font.family: root.contentFontFamily; font.pixelSize: Style.font.caption * root.textScale }
              Text { textFormat: Text.PlainText; text: "Refresh  r"; color: root.syncing ? root.palette.muted : root.palette.foreground; font.family: root.contentFontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true; MouseArea { anchors.fill: parent; enabled: !root.syncing; onClicked: root.refreshProviders() } }
              Text { textFormat: Text.PlainText; text: "Settings  s"; color: root.showSettings ? root.palette.accent : root.palette.foreground; font.family: root.contentFontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true; MouseArea { anchors.fill: parent; onClicked: root.openSettings(1) } }
              Text { textFormat: Text.PlainText; text: "Help  ?"; color: root.showHelp ? root.palette.accent : root.palette.foreground; font.family: root.contentFontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true; MouseArea { anchors.fill: parent; onClicked: root.showHelp = !root.showHelp } }
            }
          }

          Item {
            width: parent.width
            height: parent.height - Style.space(58)

            DateNavigator {
              id: dateNavigator
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              height: Style.space(46)
              visible: !root.showSettings && !root.showSetup
              view: root.activeTab
              cursorDate: root.cursorDate
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
              motionDuration: root.motionDuration
              onPreviousRequested: root.stepPeriod(-1)
              onNextRequested: root.stepPeriod(1)
              onNowRequested: root.goCurrent()
            }

            TodayView {
              id: todaySurface
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: dateNavigator.bottom
              anchors.bottom: parent.bottom
              visible: root.activeTab === "today"
              day: root.cursorDate
              events: root.dayEvents
              selectedEvent: root.selectedEvent
              selectedUid: root.selectedUid
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
              density: root.previewSettings.density
              motionDuration: root.motionDuration
              providerStatus: root.providerStatusFor(root.selectedEvent)
              actionError: root.actionError
              onEventSelected: function(uid, day) { root.selectUid(uid, day) }
              onMeetingRequested: root.openMeeting()
              onSourceRequested: root.openSource()
            }

            WeekView {
              id: weekSurface
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: dateNavigator.bottom
              anchors.bottom: parent.bottom
              visible: root.activeTab === "week"
              events: root.events
              weekDays: root.weekDays
              selectedDay: root.selectedDay
              selectedUid: root.selectedUid
              selectedEvent: root.selectedEvent
              nowTime: root.nowTime
              startHour: root.gridStartHour
              endHour: root.gridEndHour
              hourHeight: root.hourHeight
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
              motionDuration: root.motionDuration
              onEventSelected: function(uid, day) { root.selectUid(uid, day) }
            }

            Rectangle {
              visible: !root.loading && root.events.length === 0 && !root.showSettings && !root.showSetup
              anchors.centerIn: parent
              width: Style.space(560)
              height: Style.space(240)
              radius: Style.space(12)
              color: root.palette.surface
              border.color: root.errorText !== "" ? root.palette.urgent : root.palette.border
              border.width: 1
              Column {
                anchors.fill: parent
                anchors.margins: Style.space(22)
                spacing: Style.space(14)
                Text { textFormat: Text.PlainText; text: root.errorText !== "" ? "CALENDAR UNAVAILABLE" : root.filteredEmpty ? "NO VISIBLE EVENTS" : "YOUR CALENDAR COCKPIT IS READY"; color: root.errorText !== "" ? root.palette.urgent : root.palette.accent; font.family: root.contentFontFamily; font.pixelSize: Style.font.title * root.textScale; font.bold: true }
                Text { textFormat: Text.PlainText; width: parent.width; text: root.errorText !== "" ? root.errorText : root.filteredEmpty ? "Every cached calendar in this period is hidden. Open Calendar settings to show one or more." : "Connect Google Calendar or personal Outlook.com in Settings. Private builds require provider registration once; everything remains read-only and local."; color: root.palette.foreground; font.family: root.contentFontFamily; font.pixelSize: Style.font.bodySmall * root.textScale; wrapMode: Text.Wrap }
                Rectangle {
                  width: parent.width
                  height: Style.space(44)
                  radius: Style.space(7)
                  color: root.palette.accent
                  Text {
                    textFormat: Text.PlainText
                    anchors.centerIn: parent
                    text: root.errorText !== "" ? "r  Try again" : root.filteredEmpty ? "c  Calendar visibility" : "c  Connect calendars"
                    color: root.palette.background
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.bodySmall * root.textScale
                    font.bold: true
                  }
                  MouseArea { anchors.fill: parent; onClicked: root.errorText !== "" ? root.loadView() : root.openSettings(0) }
                }
                Rectangle {
                  width: parent.width
                  height: Style.space(40)
                  radius: Style.space(7)
                  color: "transparent"
                  border.color: root.palette.border
                  border.width: 1
                  Text {
                    textFormat: Text.PlainText
                    anchors.centerIn: parent
                    text: root.errorText !== "" ? "c  Calendar settings" : "Load fictional demo data"
                    color: root.palette.foreground
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.caption * root.textScale
                    font.bold: true
                  }
                  MouseArea { anchors.fill: parent; onClicked: root.errorText !== "" ? root.openSettings(0) : root.seedDemo() }
                }
              }
            }

            SettingsView {
              id: settingsSurface
              anchors.fill: parent
              anchors.margins: Style.space(12)
              visible: root.showSettings
              z: 20
              draft: root.settingsDraft
              providers: root.setupProviders
              calendars: root.calendars
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
              pendingReset: root.pendingReset
              pendingDisconnect: root.pendingDisconnect
              busy: root.accountBusy
              errorText: root.accountError
              onUpdateRequested: function(key, value) { root.updateDraft(key, value) }
              onApplyRequested: root.applySettings()
              onCancelRequested: root.cancelSettings()
              onSetupRequested: function(provider) { root.openSetup(provider) }
              onDisconnectRequested: function(provider) { root.requestDisconnect(provider) }
              onResetRequested: root.requestReset()
            }

            SetupView {
              id: setupSurface
              anchors.centerIn: parent
              width: Math.min(parent.width - Style.space(60), Style.space(720))
              height: Math.min(parent.height - Style.space(50), setupSurface.implicitHeight)
              visible: root.showSetup
              z: 30
              provider: root.setupProvider
              providerState: root.providerSetup(root.setupProvider)
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
              busy: root.accountBusy
              errorText: root.accountError
              onConfigureRequested: function(provider, clientId) { root.configureClient(provider, clientId) }
              onImportRequested: function(source) { root.importGoogleDesktop(source) }
              onAuthenticateRequested: function(provider) { root.authenticate(provider) }
              onCancelRequested: { root.showSetup = false; root.openSettings(0) }
            }

            HelpOverlay {
              anchors.centerIn: parent
              width: Math.min(parent.width - Style.space(80), Style.space(720))
              height: Math.min(parent.height - Style.space(80), Style.space(420))
              visible: root.showHelp
              z: 40
              palette: root.palette
              fontFamily: root.contentFontFamily
              textScale: root.textScale
            }

            Rectangle {
              visible: root.loading && root.events.length === 0
              anchors.fill: parent
              color: Qt.rgba(0, 0, 0, 0.58)
              z: 50
              Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "Loading local calendar"; color: root.palette.accent; font.family: root.contentFontFamily; font.pixelSize: Style.font.body * root.textScale; font.bold: true }
            }
          }
        }
      }
    }
  }

  function handleEscape() {
    if (root.pendingReset) root.pendingReset = false
    else if (root.pendingDisconnect !== "") root.pendingDisconnect = ""
    else if (root.showSetup) { root.showSetup = false; root.openSettings(0) }
    else if (root.showHelp) root.showHelp = false
    else if (root.showSettings) root.cancelSettings()
    else if (root.expandedDetails) root.expandedDetails = false
    else root.close()
  }
}
