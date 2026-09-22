// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "CalendarModel.js" as CalendarModel
import "EventEditorModel.js" as EventEditorModel
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
    property bool showEditor: false
    property bool expandedDetails: false
    property var editorDraft: ({})
    property var editorSource: null
    property string editorMode: "create"
    property string editorReturnUid: ""
    property var editorReturnDay: null
    property var pendingWriteIntent: null
    property string editingAuthProvider: ""
    property string editingAuthAccountId: ""
    property bool mutationBusy: false
    property string mutationError: ""
    property string mutationPayload: ""
    property string mutationAction: ""
    property string pendingCopiedOriginalUid: ""
    property string pendingCopiedOriginalScope: "single"
    property string pendingCopiedOriginalRevision: ""
    property string pendingCopiedOriginalSeriesRevision: ""
    property string pendingCopiedOriginalProvider: ""
    property string pendingCopiedOriginalAccountId: ""
    property bool pendingCopiedOriginalDeleteAvailable: false
    property bool pendingCopiedOriginalNeedsPermission: false
    property string pendingCopiedOriginalReason: ""
    readonly property bool pendingCopiedOriginalOffline: root.copySourceOffline()
    property bool confirmCopiedOriginalDelete: false
    property string copyResultError: ""
    property bool copyEditAuthorizationPending: false
    property string setupProvider: ""
    property var setupProviders: [
        {
            provider: "google",
            label: "Google",
            client_configured: false,
            registration_source: "",
            connected: false,
            accounts: 0,
            editing_account_ids: [],
            stale: false,
            last_sync: "",
            last_error: ""
        },
        {
            provider: "microsoft",
            label: "Outlook",
            client_configured: false,
            registration_source: "",
            connected: false,
            accounts: 0,
            editing_account_ids: [],
            stale: false,
            last_sync: "",
            last_error: ""
        }
    ]
    property bool accountBusy: false
    property string accountError: ""
    property string errorText: ""
    property string actionError: ""
    property string actionNotice: ""
    property string actionKind: ""
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
    readonly property bool hasConnectedAccount: {
        for (var i = 0; i < setupProviders.length; i++)
            if (setupProviders[i] && setupProviders[i].connected)
                return true;
        return false;
    }
    // The empty-state card is only for states the user can act on: a helper
    // error, every calendar hidden, or no account connected yet. A connected
    // account with no events in the period shows nothing, matching Week.
    readonly property bool showEmptyState: !root.loading && root.events.length === 0
        && !root.showSettings && !root.showSetup && !root.showEditor
        && (!root.hasConnectedAccount || root.errorText !== "" || root.filteredEmpty)
    readonly property var dayEvents: CalendarModel.eventsForDay(events, cursorDate)
    readonly property var weekEvents: CalendarModel.eventsForWeek(events, cursorDate)
    readonly property var visibleEvents: activeTab === "today" ? dayEvents : weekEvents
    readonly property var selectedEvent: CalendarModel.eventByUid(visibleEvents, selectedUid)
    readonly property var weekDays: CalendarModel.weekDays(cursorDate)
    readonly property int hourHeight: Style.space(previewSettings.density === "roomy" ? 68 : 46)
    readonly property int gridStartHour: Number(previewSettings.weekStartHour)
    readonly property int gridEndHour: Number(previewSettings.weekEndHour)
    readonly property bool syncing: calendarService ? calendarService.syncing : false
    readonly property string updateStatus: root.actionNotice !== "" ? root.actionNotice : root.demoData ? "Demo" : root.syncing ? "Updating" : CalendarModel.updateStatus(root.providers, root.nowTime)
    readonly property bool updateNeedsAttention: root.updateStatus.indexOf("reconnect") >= 0 || root.updateStatus.indexOf("stale") >= 0 || root.updateStatus.indexOf("Offline") >= 0
    Timer {
        interval: 60000
        running: root.opened
        repeat: true
        triggeredOnStart: true
        onTriggered: root.nowTime = new Date()
    }
    Timer {
        id: actionNoticeTimer
        interval: 4000
        onTriggered: root.actionNotice = ""
    }
    Component.onCompleted: {
        root.activeTab = root.appliedSettings.defaultView;
        root.settingsDraft = SettingsModel.normalize(root.settings);
        if (root.calendarService)
            root.calendarService.syncIntervalMinutes = root.appliedSettings.syncIntervalMinutes;
    }
    function open() {
        root.controller.show();
        Qt.callLater(function () {
            if (!root.opened)
                return;
            root.setCenterHoverRevealSuppressed(true);
            // The panel stays loaded between summons and can outlive a day
            // boundary, so always open on today rather than a stale cursor.
            root.goCurrent();
            root.loadSetupStatus();
        });
    }
    function close() {
        root.setCenterHoverRevealSuppressed(false);
        root.cancelDraft();
        root.pendingWriteIntent = null;
        root.showHelp = false;
        root.showSettings = false;
        root.showSetup = false;
        root.pendingReset = false;
        root.pendingDisconnect = "";
        root.controller.hide();
    }
    function toggle() { root.opened ? root.close() : root.open(); }
    function refresh() { root.loadView(); }
    function closeForPopoutSwitch() { root.close(); }
    function setCenterHoverRevealSuppressed(value) {
        if (!root.bar)
            return;
        if (typeof root.bar.setCenterHoverRevealSuppressed === "function")
            root.bar.setCenterHoverRevealSuppressed(value);
        else if ("centerHoverRevealSuppressed" in root.bar)
            root.bar.centerHoverRevealSuppressed = value;
    }
    function switchPanel(direction) {
        if (root.bar && root.bar.switchPanelFrom)
            return root.bar.switchPanelFrom(root.barIdentity, direction);
        return false;
    }
    function helperCommand(arguments) { return helperPath ? [helperPath].concat(arguments) : []; }
    function queryStart() { return (activeTab === "today" ? CalendarModel.localMidnight(cursorDate) : CalendarModel.startOfWeek(cursorDate)).toISOString(); }
    function queryEnd() {
        var start = activeTab === "today" ? CalendarModel.localMidnight(cursorDate) : CalendarModel.startOfWeek(cursorDate);
        return CalendarModel.addDays(start, activeTab === "today" ? 1 : 7).toISOString();
    }
    function loadView() {
        if (viewProcess.running) {
            viewReloadPending = true;
            return;
        }
        viewReloadPending = false;
        loading = true;
        errorText = "";
        if (!helperPath) {
            loading = false;
            errorText = "Calendar helper is unavailable";
            return;
        }
        viewProcess.command = helperCommand(["view", "--from", queryStart(), "--to", queryEnd()]);
        viewProcess.running = true;
    }
    function applyView(raw) {
        try {
            var payload = JSON.parse(String(raw || "{}"));
            cachedEvents = payload.events || [];
            calendars = payload.calendars || [];
            providers = payload.providers || [];
            demoData = payload.demo === true;
            var dayItems = CalendarModel.eventsForDay(events, selectedDay);
            var revealNow = pendingNow;
            if (pendingNow)
                selectedUid = CalendarModel.nowSelectionUid(events, selectedDay, nowTime);
            else if (pendingAnchorEvent)
                selectedUid = CalendarModel.closestUidForDay(events, selectedDay, pendingAnchorEvent);
            else if (!CalendarModel.eventByUid(dayItems, selectedUid)) {
                var initialIndex = CalendarModel.initialSelection(dayItems, new Date());
                selectedUid = initialIndex >= 0 ? String(dayItems[initialIndex].uid || "") : "";
            }
            pendingNow = false;
            pendingAnchorEvent = null;
            errorText = "";
            if (revealNow)
                Qt.callLater(function () {
                    if (root.activeTab === "week")
                        weekSurface.showNow();
                    else
                        todaySurface.revealSelectedEvent();
                });
        } catch (error) {
            errorText = "Could not read the local calendar cache";
        }
    }
    function refreshProviders() {
        if (!calendarService) {
            errorText = "Calendar service is unavailable";
            return;
        }
        calendarService.requestSync();
    }
    function loadSetupStatus() {
        if (!helperPath || setupProcess.running)
            return;
        setupProcess.command = helperCommand(["setup-status"]);
        setupProcess.running = true;
    }
    function applySetupStatus(raw) {
        try {
            var payload = JSON.parse(String(raw || "{}"));
            setupProviders = payload.providers || setupProviders;
            demoData = payload.demo === true;
        } catch (error) {
            accountError = "Could not read account setup status";
        }
    }
    function providerSetup(provider) {
        for (var i = 0; i < setupProviders.length; i++)
            if (setupProviders[i].provider === provider)
                return setupProviders[i];
        return {
            provider: provider,
            label: provider,
            client_configured: false,
            registration_source: "",
            connected: false
        };
    }
    function providerStatusFor(event) {
        if (!event)
            return "";
        for (var i = 0; i < providers.length; i++) {
            if (providers[i].provider === event.provider && providers[i].account_id === event.account_id) {
                if (providers[i].stale)
                    return providers[i].connected === false ? "Needs reconnect, showing cached data" : "Offline, showing cached data";
                return CalendarModel.updateStatus([providers[i]], root.nowTime);
            }
        }
        return demoData ? "Demo data" : "Local cache";
    }
    function copySourceOffline() {
        for (var i = 0; i < providers.length; i++) if (providers[i].provider === pendingCopiedOriginalProvider && providers[i].account_id === pendingCopiedOriginalAccountId) return providers[i].connected === false || providers[i].stale === true;
        return false;
    }
    function setTab(tab) {
        activeTab = tab;
        cursorDate = selectedDay;
        selectedUid = "";
        loadView();
    }
    function moveSelection(amount) {
        selectedUid = activeTab === "week" ? CalendarModel.moveWeekVertical(events, selectedDay, selectedUid, amount) : CalendarModel.moveWithinDay(events, selectedDay, selectedUid, amount);
    }
    function moveHorizontal(amount) {
        if (activeTab === "week") {
            var overlapTarget = CalendarModel.moveAcrossOverlap(events, selectedDay, selectedUid, amount);
            if (overlapTarget) {
                selectedUid = overlapTarget;
                return;
            }
        }
        moveDay(amount);
    }
    function moveDay(amount) {
        var anchor = selectedEvent;
        var previousWeek = CalendarModel.dayKey(CalendarModel.startOfWeek(selectedDay));
        selectedDay = CalendarModel.addDays(selectedDay, amount);
        cursorDate = selectedDay;
        selectedUid = CalendarModel.closestUidForDay(events, selectedDay, anchor);
        if (activeTab === "today" || previousWeek !== CalendarModel.dayKey(CalendarModel.startOfWeek(selectedDay))) {
            pendingAnchorEvent = anchor;
            loadView();
        }
    }
    function stepPeriod(amount) {
        pendingAnchorEvent = selectedEvent;
        var next = CalendarModel.periodState(cursorDate, selectedDay, activeTab, amount);
        cursorDate = next.cursorDate;
        selectedDay = next.selectedDay;
        selectedUid = "";
        loadView();
    }
    function goCurrent() {
        nowTime = new Date();
        cursorDate = nowTime;
        selectedDay = cursorDate;
        selectedUid = "";
        pendingAnchorEvent = null;
        pendingNow = true;
        loadView();
    }
    function goToday() {
        activeTab = "today";
        goCurrent();
    }
    function selectUid(uid, day) {
        selectedUid = String(uid || "");
        var event = CalendarModel.eventByUid(visibleEvents, selectedUid);
        selectedDay = day || CalendarModel.eventDay(event) || selectedDay;
        cursorDate = selectedDay;
    }
    function openMeeting() {
        if (!selectedEvent || !selectedEvent.meeting_url || actionProcess.running)
            return;
        root.actionKind = "open";
        actionProcess.command = helperCommand(["open-meeting", selectedEvent.uid]);
        actionProcess.running = true;
    }
    function openSource() {
        if (!selectedEvent || !selectedEvent.provider_url || actionProcess.running)
            return;
        root.actionKind = "open";
        actionProcess.command = helperCommand(["open-source", selectedEvent.uid]);
        actionProcess.running = true;
    }
    function copyMeeting() {
        var source = root.editorSource || root.selectedEvent;
        if (!source || !source.meeting_url || actionProcess.running)
            return;
        root.actionNotice = "";
        root.actionKind = "copy";
        actionProcess.command = helperCommand(["copy-meeting", source.uid]);
        actionProcess.running = true;
    }
    function cachedEvent(uid) { return CalendarModel.eventByUid(root.cachedEvents, String(uid || "")); }
    function calendarForKey(key) {
        for (var i = 0; i < root.calendars.length; i++)
            if (String(root.calendars[i].key || "") === String(key || ""))
                return root.calendars[i];
        return null;
    }
    function providerCanEdit(provider, accountId) {
        var state = root.providerSetup(provider);
        var accounts = state.editing_account_ids || [];
        return accounts.indexOf(String(accountId || "")) >= 0;
    }
    function editableCalendars() {
        return EventEditorModel.editableDestinations(root.calendars, root.setupProviders);
    }
    function selectedEditAction() {
        var action = EventEditorModel.editAction(root.selectedEvent, root.calendars, root.setupProviders);
        return action === "Enable editing" ? "enable" : action === "Cannot edit" ? "cannot" : "edit";
    }
    function editorOffline() {
        var calendar = root.calendarForKey(root.editorDraft.calendar_key);
        if (!calendar)
            return false;
        for (var i = 0; i < root.providers.length; i++) {
            var provider = root.providers[i];
            if (provider.provider === calendar.provider && provider.account_id === calendar.account_id)
                return provider.connected === false || provider.stale === true;
        }
        return false;
    }
    function minuteKey(value) {
        var minute = ((Number(value || 0) % 1440) + 1440) % 1440;
        var hour = Math.floor(minute / 60);
        var remainder = minute % 60;
        return (hour < 10 ? "0" : "") + hour + ":" + (remainder < 10 ? "0" : "") + remainder;
    }
    function openCreateDraft(day, minute) {
        root.editorReturnUid = root.selectedUid;
        root.editorReturnDay = new Date(root.selectedDay);
        var eventDay = CalendarModel.dayKey(day || root.selectedDay); root.selectedDay = new Date(day || root.selectedDay); root.cursorDate = root.selectedDay; root.selectedUid = "";
        var startMinute = Number.isFinite(Number(minute)) ? Number(minute) : 9 * 60;
        root.editorSource = null;
        root.editorDraft = EventEditorModel.newDraft(eventDay, root.minuteKey(startMinute), root.minuteKey(startMinute + 60), root.editableCalendars());
        root.editorMode = "create";
        root.mutationError = "";
        root.showHelp = false;
        root.showSettings = false;
        root.showSetup = false;
        root.showEditor = true; editorSurface.resetInteraction();
    }
    function openEditDraft(event) {
        var source = event || root.selectedEvent;
        if (!source)
            return;
        root.editorSource = source;
        root.editorDraft = EventEditorModel.eventDraft(source, false, null, root.editableCalendars());
        root.editorMode = "update";
        root.mutationError = "";
        root.showHelp = false;
        root.showSettings = false;
        root.showSetup = false;
        root.showEditor = true; editorSurface.resetInteraction();
    }
    function openDuplicateDraft(event) {
        var source = event || root.selectedEvent;
        if (!source)
            return;
        root.editorSource = source;
        root.editorDraft = EventEditorModel.eventDraft(source, true, null, root.editableCalendars());
        root.editorMode = "copy";
        root.mutationError = "";
        root.showHelp = false;
        root.showSettings = false;
        root.showSetup = false;
        root.showEditor = true; editorSurface.resetInteraction();
    }
    function beginCreate(day, minute) { root.requestWriteIntent("create", null, day, minute, 0, 0); }
    function beginEdit(event) { root.requestWriteIntent("edit", event, null, 0, 0, 0); }
    function beginDuplicate(event) { root.requestWriteIntent("duplicate", event, null, 0, 0, 0); }
    function requestWriteIntent(kind, event, day, minute, dayAmount, minuteAmount, durationAmount) {
        var decision = EventEditorModel.writeDecision(kind, event, root.calendars, root.setupProviders);
        var intent = { kind: kind, uid: event ? String(event.uid || "") : "", day: CalendarModel.dayKey(day || root.selectedDay), minute: Number(minute || 0), dayAmount: Number(dayAmount || 0), minuteAmount: Number(minuteAmount || 0), durationAmount: Number(durationAmount || 0) };
        if (decision.action === "blocked") {
            root.actionNotice = decision.reason;
            actionNoticeTimer.restart();
        } else if (decision.action === "settings") {
            root.pendingWriteIntent = intent;
            root.accountError = "";
            root.openSettings(0);
            settingsSurface.focusAccountAction(decision.provider, decision.account_id, "enable");
        } else root.performWriteIntent(intent);
    }
    function performWriteIntent(intent) {
        var source = intent.uid ? root.cachedEvent(intent.uid) : null;
        if (intent.kind === "create") root.openCreateDraft(new Date(intent.day + "T12:00:00"), intent.minute);
        else if (intent.kind === "duplicate") root.openDuplicateDraft(source);
        else {
            root.openEditDraft(source);
            if (intent.kind === "move") root.moveActiveDraft(intent.dayAmount, intent.minuteAmount, intent.durationAmount);
        }
    }
    function followDraftDay() {
        var day = new Date(String(root.editorDraft.day) + "T12:00:00");
        var previousWeek = CalendarModel.dayKey(CalendarModel.startOfWeek(root.selectedDay));
        root.selectedDay = day;
        root.cursorDate = day;
        if (root.activeTab === "today" || previousWeek !== CalendarModel.dayKey(CalendarModel.startOfWeek(day))) root.loadView();
    }
    function moveActiveDraft(dayAmount, minuteAmount, durationAmount) {
        if (root.editorDraft.all_day && minuteAmount !== 0) {
            root.actionNotice = "All-day events move by day only.";
            actionNoticeTimer.restart();
            return;
        }
        root.updateEditorDraft(EventEditorModel.shift(root.editorDraft, dayAmount, minuteAmount, durationAmount));
        root.followDraftDay();
    }
    function updateEditorDraft(next) {
        root.editorDraft = next;
        root.editorMode = EventEditorModel.mode(next, root.editorSource);
        root.mutationError = "";
    }
    function shiftDraft(uid, dayAmount, minuteAmount, durationAmount) {
        if (root.showEditor && String(root.editorDraft.source_uid || "") === String(uid || "")) {
            if (Number(durationAmount || 0) !== 0) root.updateEditorDraft(EventEditorModel.shift(root.editorDraft, 0, 0, Number(durationAmount)));
            else root.moveActiveDraft(Number(dayAmount || 0), Number(minuteAmount || 0));
            return;
        }
        var source = root.cachedEvent(uid);
        if (!source)
            return;
        root.selectUid(uid, CalendarModel.eventDay(source));
        root.requestWriteIntent("move", source, null, 0, Number(dayAmount || 0), Number(minuteAmount || 0), Number(durationAmount || 0));
    }
    function cancelDraft() {
        if (root.mutationBusy)
            return;
        var restoreCreateSelection = root.editorMode === "create" && root.editorReturnDay;
        root.showEditor = false;
        root.editorDraft = ({});
        root.editorSource = null;
        root.editorMode = "create";
        root.mutationError = "";
        if (restoreCreateSelection) {
            root.selectedDay = new Date(root.editorReturnDay);
            root.cursorDate = root.selectedDay;
            root.selectedUid = root.editorReturnUid;
        }
        root.editorReturnUid = "";
        root.editorReturnDay = null;
        Qt.callLater(function () { keyCatcher.forceActiveFocus(); });
    }
    function startMutation(action, payload) {
        if (root.mutationBusy || root.helperPath === "")
            return;
        root.mutationBusy = true;
        root.mutationError = "";
        root.mutationAction = action;
        root.mutationPayload = JSON.stringify(payload);
        mutationProcess.command = root.helperCommand([action]);
        mutationProcess.running = true;
    }
    function saveDraft() {
        if (!root.showEditor || root.editorOffline())
            return;
        var action = root.editorMode === "copy" ? "copy-event" : root.editorMode === "update" ? "update-event" : "create-event";
        root.startMutation(action, root.editorDraft);
    }
    function deleteDraft(scope) {
        if (root.editorMode !== "update")
            return;
        if (!root.editorSource || root.editorOffline()) return;
        if (!editorSurface.canDelete) return;
        root.startMutation("delete-event", {
            uid: root.editorSource.uid, confirmed: true,
            scope: scope,
            expected_revision: root.editorDraft.source_revision,
            series_revision: root.editorDraft.series_revision
        });
    }
    function enableEditingFor(provider, accountId) {
        if (!provider || !accountId || editAuthProcess.running)
            return;
        root.accountBusy = true;
        root.accountError = "";
        root.editingAuthProvider = provider;
        root.editingAuthAccountId = accountId;
        editAuthProcess.command = root.helperCommand(["enable-editing", provider, "--account", accountId]);
        editAuthProcess.running = true;
    }
    function enableCopiedOriginalEditing() {
        if (!root.pendingCopiedOriginalNeedsPermission || editAuthProcess.running)
            return;
        root.copyEditAuthorizationPending = true;
        root.accountBusy = true;
        root.copyResultError = "";
        editAuthProcess.command = root.helperCommand(["enable-editing", root.pendingCopiedOriginalProvider, "--account", root.pendingCopiedOriginalAccountId]);
        editAuthProcess.running = true;
    }
    function deleteCopiedOriginal() {
        if (!root.pendingCopiedOriginalUid || root.pendingCopiedOriginalOffline)
            return;
        if (root.pendingCopiedOriginalNeedsPermission) {
            root.enableCopiedOriginalEditing();
            return;
        }
        if (!root.pendingCopiedOriginalDeleteAvailable)
            return;
        if (!root.confirmCopiedOriginalDelete) {
            root.confirmCopiedOriginalDelete = true;
            return;
        }
        root.confirmCopiedOriginalDelete = false;
        root.startMutation("delete-event", {
            uid: root.pendingCopiedOriginalUid, confirmed: true,
            scope: root.pendingCopiedOriginalScope, expected_revision: root.pendingCopiedOriginalRevision,
            series_revision: root.pendingCopiedOriginalSeriesRevision,
            series_transfer_guard: root.pendingCopiedOriginalScope === "series"
        });
    }
    function keepBothCopies() {
        root.pendingCopiedOriginalUid = "";
        root.pendingCopiedOriginalScope = "single";
        root.pendingCopiedOriginalRevision = "";
        root.pendingCopiedOriginalSeriesRevision = "";
        root.pendingCopiedOriginalProvider = "";
        root.pendingCopiedOriginalAccountId = "";
        root.pendingCopiedOriginalDeleteAvailable = false;
        root.pendingCopiedOriginalNeedsPermission = false;
        root.pendingCopiedOriginalReason = "";
        root.confirmCopiedOriginalDelete = false;
        root.copyResultError = "";
    }
    function seedDemo() {
        if (demoProcess.running)
            return;
        demoProcess.command = helperCommand(["demo", "seed"]);
        demoProcess.running = true;
    }
    function openSettings(section) {
        root.cancelDraft();
        root.showHelp = false;
        root.showSetup = false;
        root.settingsSnapshot = SettingsModel.normalize(root.settings);
        root.settingsDraft = SettingsModel.normalize(root.settings);
        root.showSettings = true;
        settingsSurface.sectionIndex = Math.max(0, Math.min(3, Number(section || 0)));
        settingsSurface.controlIndex = 0;
        Qt.callLater(function () { keyCatcher.forceActiveFocus(); });
    }
    function updateDraft(key, value) {
        root.settingsDraft = SettingsModel.withValue(root.settingsDraft, key, value);
        if (key === "hiddenCalendars")
            Qt.callLater(root.ensureVisibleSelection);
    }
    function ensureVisibleSelection() {
        var dayItems = CalendarModel.eventsForDay(root.events, root.selectedDay);
        if (CalendarModel.eventByUid(dayItems, root.selectedUid))
            return;
        var index = CalendarModel.initialSelection(dayItems, root.nowTime);
        root.selectedUid = index >= 0 ? String(dayItems[index].uid || "") : "";
    }
    function persistSettings(values) {
        var entry = {
            id: root.moduleName
        };
        for (var existing in root.settings)
            if (existing !== "id" && existing !== "motion")
                entry[existing] = root.settings[existing];
        for (var key in values)
            entry[key] = values[key];
        root.settings = entry;
        if (root.hostWidget && "settings" in root.hostWidget)
            root.hostWidget.settings = entry;
        if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
            root.bar.shell.updateEntryInline(root.moduleName, entry);
    }
    function applySettings() {
        var next = SettingsModel.normalize(root.settingsDraft);
        persistSettings(next);
        if (calendarService)
            calendarService.syncIntervalMinutes = next.syncIntervalMinutes;
        root.showSettings = false;
        root.pendingReset = false;
        root.pendingWriteIntent = null;
    }
    function cancelSettings() {
        root.settingsDraft = SettingsModel.normalize(root.settingsSnapshot);
        root.showSettings = false;
        root.pendingReset = false;
        root.pendingDisconnect = "";
        root.pendingWriteIntent = null;
        root.accountError = "";
        Qt.callLater(root.ensureVisibleSelection);
    }
    function openSetup(provider) {
        root.setupProvider = provider;
        setupSurface.clearDraft();
        root.accountError = "";
        root.showSettings = false;
        root.showSetup = true;
    }
    function configureClient(provider, clientId) {
        if (configureProcess.running || !String(clientId || "").trim())
            return;
        root.setupProvider = provider;
        root.accountBusy = true;
        root.accountError = "";
        configureProcess.command = helperCommand(["configure-client", provider, String(clientId).trim()]);
        configureProcess.running = true;
    }
    function importGoogleDesktop(source) {
        if (importProcess.running || !String(source || "").trim())
            return;
        root.setupProvider = "google";
        root.accountBusy = true;
        root.accountError = "";
        importProcess.command = helperCommand(["import-google-desktop-app", String(source)]);
        importProcess.running = true;
    }
    function authenticate(provider, access) {
        if (authProcess.running)
            return;
        root.setupProvider = provider;
        root.accountBusy = true;
        root.accountError = "";
        authProcess.command = helperCommand(["auth", provider, "--access", access || "read"]);
        authProcess.running = true;
    }
    function requestDisconnect(provider, accountId) {
        var key = provider + ":" + String(accountId || "");
        if (pendingDisconnect !== key) {
            pendingDisconnect = key;
            return;
        }
        pendingDisconnect = "";
        accountBusy = true;
        disconnectProcess.command = helperCommand(["disconnect", provider].concat(accountId ? ["--account", accountId] : []));
        disconnectProcess.running = true;
    }
    function markEditing(provider, accountId) {
        var next = [];
        for (var i = 0; i < root.setupProviders.length; i++) {
            var state = {};
            for (var key in root.setupProviders[i]) state[key] = root.setupProviders[i][key];
            if (state.provider === provider) {
                state.editing_account_ids = (state.editing_account_ids || []).slice();
                if (state.editing_account_ids.indexOf(accountId) < 0) state.editing_account_ids.push(accountId);
                state.editing = true;
            }
            next.push(state);
        }
        root.setupProviders = next;
    }
    function requestReset() {
        if (!pendingReset) {
            pendingReset = true;
            return;
        }
        if (resetProcess.running)
            return;
        accountBusy = true;
        resetProcess.command = helperCommand(["reset-local-data"]);
        resetProcess.running = true;
    }
    Process {
        id: viewProcess
        stdout: StdioCollector {
            onStreamFinished: root.applyView(text)
        }
        stderr: StdioCollector {
            id: viewError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            root.loading = false;
            if (exitCode !== 0 && root.events.length === 0)
                root.errorText = String(viewError.text || "Calendar helper failed").trim();
            if (root.viewReloadPending)
                Qt.callLater(root.loadView);
        }
    }
    Process {
        id: setupProcess
        stdout: StdioCollector {
            onStreamFinished: root.applySetupStatus(text)
        }
        stderr: StdioCollector {
            id: setupError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            if (exitCode !== 0)
                root.accountError = String(setupError.text || "Account status failed").trim();
        }
    }
    Process {
        id: configureProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: configureError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            if (exitCode === 0)
                root.authenticate(root.setupProvider, setupSurface.accessChoice);
            else {
                root.accountBusy = false;
                root.accountError = String(configureError.text || "Could not save the public client ID").trim();
            }
            root.loadSetupStatus();
        }
    }
    Process {
        id: importProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: importError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            if (exitCode === 0)
                root.authenticate("google", setupSurface.accessChoice);
            else {
                root.accountBusy = false;
                root.accountError = String(importError.text || "Could not import Google Desktop credentials").trim();
            }
            root.loadSetupStatus();
        }
    }
    Process {
        id: authProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: authError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            root.accountBusy = false;
            if (exitCode !== 0)
                root.accountError = String(authError.text || "Connection failed").trim();
            else {
                root.showSetup = false;
                root.openSettings(0);
            }
            root.loadView();
            root.loadSetupStatus();
        }
    }
    Process {
        id: disconnectProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: disconnectError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            root.accountBusy = false;
            if (exitCode !== 0)
                root.accountError = String(disconnectError.text || "Disconnect failed").trim();
            root.loadView();
            root.loadSetupStatus();
        }
    }
    Process {
        id: resetProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: resetError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            root.accountBusy = false;
            root.pendingReset = false;
            if (exitCode !== 0)
                root.accountError = String(resetError.text || "Reset failed").trim();
            root.loadView();
            root.loadSetupStatus();
        }
    }
    Process {
        id: editAuthProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: editAuthError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            var copiedOriginalUpgrade = root.copyEditAuthorizationPending;
            root.copyEditAuthorizationPending = false;
            root.accountBusy = false;
            if (exitCode !== 0) {
                var failure = String(editAuthError.text || "Could not enable editing").trim();
                if (copiedOriginalUpgrade)
                    root.copyResultError = failure;
                else {
                    root.accountError = failure;
                    root.showSettings = true;
                    settingsSurface.focusAccountAction(root.editingAuthProvider, root.editingAuthAccountId, "enable");
                }
            } else if (copiedOriginalUpgrade && root.pendingCopiedOriginalUid !== "") {
                root.pendingCopiedOriginalDeleteAvailable = true;
                root.pendingCopiedOriginalNeedsPermission = false;
                root.pendingCopiedOriginalReason = "Editing enabled. Delete the original when ready.";
            } else {
                root.markEditing(root.editingAuthProvider, root.editingAuthAccountId);
                root.accountError = "";
                if (root.pendingWriteIntent) {
                    var intent = root.pendingWriteIntent;
                    root.pendingWriteIntent = null;
                    root.performWriteIntent(intent);
                }
            }
            root.editingAuthProvider = "";
            root.editingAuthAccountId = "";
            root.loadSetupStatus();
        }
    }
    Process {
        id: mutationProcess
        stdinEnabled: true
        stdout: StdioCollector {
            id: mutationStdout
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: mutationStderr
            waitForEnd: true
        }
        onStarted: {
            write(mutationPayload + "\n");
            mutationPayload = "";
        }
        onExited: function (exitCode) {
            var completedAction = root.mutationAction;
            var wasCopiedOriginalDelete = completedAction === "delete-event" && root.pendingCopiedOriginalUid !== "" && !root.showEditor;
            if (exitCode === 0) {
                try {
                    var result = JSON.parse(String(mutationStdout.text || "{}"));
                    if (completedAction === "copy-event") {
                        root.pendingCopiedOriginalUid = String(result.original_uid || "");
                        root.pendingCopiedOriginalScope = String(result.original_scope || "single");
                        root.pendingCopiedOriginalRevision = String(result.original_revision || "");
                        root.pendingCopiedOriginalSeriesRevision = String(result.original_series_revision || "");
                        root.pendingCopiedOriginalProvider = String(result.original_provider || "");
                        root.pendingCopiedOriginalAccountId = String(result.original_account_id || "");
                        root.pendingCopiedOriginalDeleteAvailable = result.delete_original_available === true;
                        root.pendingCopiedOriginalNeedsPermission = result.delete_original_needs_permission === true;
                        root.pendingCopiedOriginalReason = String(result.delete_original_reason || "");
                        root.confirmCopiedOriginalDelete = false;
                        root.copyResultError = "";
                    } else if (wasCopiedOriginalDelete) {
                        root.keepBothCopies();
                    }
                    if (result.event && result.event.uid)
                        root.selectedUid = String(result.event.uid);
                    root.actionNotice = String(result.notice || (completedAction === "delete-event" ? "Event deleted"
                        : completedAction === "copy-event" ? "Copy saved" : "Event saved"));
                    if (root.actionNotice !== "") actionNoticeTimer.restart();
                    root.showEditor = false;
                    root.editorDraft = ({});
                    root.editorSource = null;
                    root.editorMode = "create";
                    root.mutationError = "";
                    root.loadView();
                    root.refreshProviders();
                    Qt.callLater(function () { keyCatcher.forceActiveFocus(); });
                } catch (error) {
                    root.mutationError = "The provider returned an unreadable response. Your draft is preserved.";
                }
            } else {
                var failure = String(mutationStderr.text || "The calendar change failed").trim();
                if (wasCopiedOriginalDelete)
                    root.copyResultError = "The copy was saved, but the original remains. " + failure;
                else
                    root.mutationError = failure;
                if (EventEditorModel.isMutationConflict(failure)) { root.loadView(); root.refreshProviders(); }
            }
            root.mutationBusy = false;
            root.mutationAction = "";
        }
    }
    Process {
        id: demoProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: demoError
            waitForEnd: true
        }
        onExited: function (exitCode) {
            if (exitCode !== 0)
                root.errorText = String(demoError.text || "Demo setup failed").trim();
            root.loadView();
            root.loadSetupStatus();
        }
    }
    Process {
        id: actionProcess
        stdout: StdioCollector {
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: actionStderr
            waitForEnd: true
        }
        onExited: function (exitCode) {
            root.actionError = exitCode === 0 ? "" : String(actionStderr.text || "Action unavailable").trim();
            if (exitCode === 0 && root.actionKind === "copy") {
                root.actionNotice = "Meeting link copied";
                actionNoticeTimer.restart();
            }
            root.actionKind = "";
        }
    }
    Connections {
        target: root.calendarService
        function onRevisionChanged() {
            if (root.calendarService && root.calendarService.lastError)
                root.errorText = root.calendarService.lastError;
            root.loadView();
            root.loadSetupStatus();
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
        contentWidth: panel.fittedContentWidth(root.showEditor ? Style.space(1400) : Style.space(1080))
        contentHeight: panel.fittedContentHeight(Style.space(720))
        CalendarKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            blocked: (root.showSetup && setupSurface.inputFocused) || (root.showEditor && editorSurface.inputFocused)
            onModifiedMoveRequested: function (dx, dy) { root.shiftDraft(root.selectedUid, dx, dy * 15, 0); }
            onMoveRequested: function (dx, dy) {
                if (root.pendingCopiedOriginalUid !== "") { if (dy < 0) root.keepBothCopies(); return; }
                if (root.showEditor) {
                    if (dx !== 0)
                        editorSurface.adjustCurrent(dx);
                    else if (dy !== 0)
                        editorSurface.moveField(dy);
                } else if (root.showSetup && dx !== 0) {
                    setupSurface.cycleAccess(dx);
                } else if (root.showSettings) {
                    if (dx !== 0)
                        settingsSurface.moveSection(dx);
                    else if (dy !== 0)
                        settingsSurface.moveControl(dy);
                } else if (!root.showHelp && !root.showSetup) {
                    if (dx !== 0)
                        root.moveHorizontal(dx);
                    else if (dy !== 0)
                        root.moveSelection(dy);
                }
            }
            onActivateRequested: {
                if (root.pendingCopiedOriginalUid !== "")
                    return;
                else if (root.showEditor)
                    editorSurface.activateCurrent();
                else if (root.showSetup)
                    setupSurface.activatePrimary();
                else if (root.showSettings)
                    settingsSurface.activateCurrent();
                else
                    root.expandedDetails = !root.expandedDetails;
            }
            onDeleteRequested: if (root.pendingCopiedOriginalUid !== "")
                root.deleteCopiedOriginal()
            onCloseRequested: root.handleEscape()
            onTabRequested: function (direction) {
                if (!root.showSettings && !root.showSetup && !root.showEditor)
                    root.switchPanel(direction);
            }
            onTextKey: function (text) {
                if (root.pendingCopiedOriginalUid !== "") {
                    if (text === "e" && root.pendingCopiedOriginalNeedsPermission)
                        root.enableCopiedOriginalEditing();
                    return;
                }
                if (text === "?" && !root.showSetup && !root.showEditor) {
                    root.showHelp = !root.showHelp;
                    return;
                }
                if (root.showHelp)
                    return;
                if (root.showEditor) {
                    if (text === "h")
                        editorSurface.adjustCurrent(-1);
                    else if (text === "l")
                        editorSurface.adjustCurrent(1);
                    else if (text === "j")
                        editorSurface.moveField(1);
                    else if (text === "k")
                        editorSurface.moveField(-1);
                    return;
                }
                if (root.showSettings) {
                    if (text === "a")
                        root.applySettings();
                    else if (text === "h")
                        settingsSurface.moveSection(-1);
                    else if (text === "l")
                        settingsSurface.moveSection(1);
                    else if (text === "j")
                        settingsSurface.moveControl(1);
                    else if (text === "k")
                        settingsSurface.moveControl(-1);
                    else if (text === "c") {
                        settingsSurface.sectionIndex = 0;
                        settingsSurface.controlIndex = 0;
                    }
                    return;
                }
                if (root.showSetup) {
                    if (text === "h" || text === "l") setupSurface.cycleAccess(text === "h" ? -1 : 1);
                    return;
                }
                if (text === "t")
                    root.goToday();
                else if (text === "w")
                    root.setTab("week");
                else if (text === "j")
                    root.moveSelection(1);
                else if (text === "k")
                    root.moveSelection(-1);
                else if (text === "h")
                    root.moveHorizontal(-1);
                else if (text === "l")
                    root.moveHorizontal(1);
                else if (text === "[")
                    root.stepPeriod(-1);
                else if (text === "]")
                    root.stepPeriod(1);
                else if (text === "g")
                    root.goCurrent();
                else if (text === "m")
                    root.openMeeting();
                else if (text === "o")
                    root.openSource();
                else if (text === "n")
                    root.beginCreate(root.selectedDay, 9 * 60);
                else if (text === "e")
                    root.beginEdit(root.selectedEvent);
                else if (text === "d")
                    root.beginDuplicate(root.selectedEvent);
                else if (text === "c")
                    root.openSettings(0);
                else if (text === "s")
                    root.openSettings(1);
                else if (text === "r")
                    root.refreshProviders();
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
                                model: [
                                    {
                                        key: "today",
                                        label: "t  Today",
                                        kind: "tab"
                                    },
                                    {
                                        key: "week",
                                        label: "w  Week",
                                        kind: "tab"
                                    },
                                    {
                                        key: "new",
                                        label: "n  New",
                                        kind: "new"
                                    },
                                    {
                                        key: "settings",
                                        label: "s  Settings",
                                        kind: "settings"
                                    }
                                ]
                                Rectangle {
                                    required property var modelData
                                    readonly property bool active: modelData.kind === "tab" ? root.activeTab === modelData.key : modelData.kind === "new" ? root.showEditor && root.editorMode === "create" : root.showSettings
                                    width: Style.space(modelData.kind === "settings" ? 128 : 108)
                                    height: Style.space(34)
                                    radius: Style.space(6)
                                    color: active ? root.palette.accent : "transparent"
                                    border.color: active ? root.palette.accent : root.palette.border
                                    border.width: 1
                                    Behavior on color {
                                        enabled: root.motionDuration > 0
                                        ColorAnimation {
                                            duration: root.motionDuration
                                        }
                                    }
                                    Text {
                                        textFormat: Text.PlainText
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: active ? root.palette.background : root.palette.foreground
                                        font.family: root.contentFontFamily
                                        font.pixelSize: Style.font.caption * root.textScale
                                        font.bold: true
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            if (modelData.kind === "tab")
                                                modelData.key === "today" ? root.goToday() : root.setTab(modelData.key);
                                            else if (modelData.kind === "new")
                                                root.beginCreate(root.selectedDay, 9 * 60);
                                            else
                                                root.openSettings(1);
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Item {
                        width: parent.width
                        height: parent.height - Style.space(58)
                        DateNavigator {
                            id: dateNavigator
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.rightMargin: root.showEditor ? Style.space(352) : 0
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
                            anchors.rightMargin: root.showEditor ? Style.space(352) : 0
                            anchors.top: dateNavigator.bottom
                            anchors.bottom: parent.bottom
                            visible: root.activeTab === "today" && !root.showSettings && !root.showSetup
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
                            editAction: root.selectedEditAction()
                            actionError: root.actionError
                            onEventSelected: function (uid, day) {
                                root.selectUid(uid, day);
                            }
                            onMeetingRequested: root.openMeeting()
                            onSourceRequested: root.openSource()
                            onEditRequested: root.beginEdit(root.selectedEvent)
                            onDuplicateRequested: root.beginDuplicate(root.selectedEvent)
                            }
                        WeekView {
                            id: weekSurface
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.rightMargin: root.showEditor ? Style.space(352) : 0
                            anchors.top: dateNavigator.bottom
                            anchors.bottom: parent.bottom
                            visible: root.activeTab === "week" && !root.showSettings && !root.showSetup
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
                            editAction: root.selectedEditAction()
                            editingDraft: root.showEditor ? root.editorDraft : null
                            editingUid: root.showEditor ? String(root.editorDraft.source_uid || "") : ""
                            onEventSelected: function (uid, day) {
                                root.selectUid(uid, day);
                            }
                            onEmptySlotRequested: function (day, minute) {
                                root.beginCreate(day, minute);
                            }
                            onEventDragged: function (uid, dayAmount, minuteAmount) {
                                root.shiftDraft(uid, dayAmount, minuteAmount, 0);
                            }
                            onEventResized: function (uid, minuteAmount) {
                                root.shiftDraft(uid, 0, 0, minuteAmount);
                            }
                            onMeetingRequested: root.openMeeting()
                            onSourceRequested: root.openSource()
                            onEditRequested: root.beginEdit(root.selectedEvent)
                            onDuplicateRequested: root.beginDuplicate(root.selectedEvent)
                            }
                        EventEditor {
                            id: editorSurface
                            anchors.top: parent.top
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            width: Style.space(352)
                            visible: root.showEditor
                            z: 30
                            draft: root.editorDraft
                            eventData: root.editorSource
                            calendars: root.editableCalendars()
                            mode: root.editorMode
                            palette: root.palette
                            fontFamily: root.contentFontFamily
                            textScale: root.textScale
                            busy: root.mutationBusy || root.accountBusy
                            offline: root.editorOffline()
                            errorText: root.mutationError
                            noticeText: root.actionNotice
                            onDraftUpdated: function (next) {
                                root.updateEditorDraft(next);
                            }
                            onSaveRequested: root.saveDraft()
                            onCancelRequested: root.cancelDraft()
                            onDeleteRequested: function (scope) { root.deleteDraft(scope); }
                            onDuplicateRequested: root.beginDuplicate(root.editorSource)
                            onCopyMeetingRequested: root.copyMeeting()
                            onInputNavigationRequested: function (direction) {
                                editorSurface.moveField(direction);
                                keyCatcher.forceActiveFocus();
                            }
                            }
                        CopyResultOffer {
                            visible: root.pendingCopiedOriginalUid !== ""
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: Style.space(18)
                            width: Math.min(parent.width - Style.space(40), Style.space(560))
                            z: 35
                            palette: root.palette
                            fontFamily: root.contentFontFamily
                            textScale: root.textScale
                            reason: root.pendingCopiedOriginalOffline ? "The source account is offline. The copy is saved and the original remains." : root.pendingCopiedOriginalReason
                            errorText: root.copyResultError
                            canDeleteOriginal: root.pendingCopiedOriginalDeleteAvailable && !root.pendingCopiedOriginalOffline
                            needsPermission: root.pendingCopiedOriginalNeedsPermission && !root.pendingCopiedOriginalOffline
                            confirmDelete: root.confirmCopiedOriginalDelete
                            busy: root.mutationBusy || root.accountBusy
                            onKeepRequested: root.keepBothCopies()
                            onDeleteRequested: root.deleteCopiedOriginal()
                            onEnableEditingRequested: root.enableCopiedOriginalEditing()
                        }
                        Rectangle {
                            visible: root.showEmptyState
                            anchors.centerIn: parent
                            width: Style.space(560)
                            height: Style.space(240)
                            radius: Style.space(12)
                            color: root.palette.surface
                            border.color: root.errorText !== "" ? root.palette.urgent : root.palette.border
                            border.width: 1
                            Rectangle {
                                objectName: "emptyStateClose"
                                width: Style.space(30)
                                height: Style.space(30)
                                radius: Style.space(6)
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.topMargin: Style.space(12)
                                anchors.rightMargin: Style.space(12)
                                color: "transparent"
                                border.color: root.palette.border
                                border.width: 1
                                Text {
                                    textFormat: Text.PlainText
                                    anchors.centerIn: parent
                                    text: "X"
                                    color: root.palette.muted
                                    font.family: root.contentFontFamily
                                    font.pixelSize: Style.font.caption * root.textScale
                                    font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: root.close()
                                }
                            }
                            Column {
                                anchors.fill: parent
                                anchors.margins: Style.space(22)
                                spacing: Style.space(14)
                                Text {
                                    textFormat: Text.PlainText
                                    text: root.errorText !== "" ? "CALENDAR UNAVAILABLE" : root.filteredEmpty ? "NO VISIBLE EVENTS" : "YOUR CALENDAR COCKPIT IS READY"
                                    color: root.errorText !== "" ? root.palette.urgent : root.palette.accent
                                    font.family: root.contentFontFamily
                                    font.pixelSize: Style.font.title * root.textScale
                                    font.bold: true
                                }
                                Text {
                                    textFormat: Text.PlainText
                                    width: parent.width
                                    text: root.errorText !== "" ? root.errorText : root.filteredEmpty ? "Every cached calendar in this period is hidden. Open Calendar settings to show one or more." : "Connect Google Calendar or Outlook in Settings. Read-only access is the default."
                                    color: root.palette.foreground
                                    font.family: root.contentFontFamily
                                    font.pixelSize: Style.font.bodySmall * root.textScale
                                    wrapMode: Text.Wrap
                                }
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
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: root.errorText !== "" ? root.loadView() : root.openSettings(0)
                                    }
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
                                        text: root.errorText !== "" || root.filteredEmpty ? "c  Calendar settings" : "Load fictional demo data"
                                        color: root.palette.foreground
                                        font.family: root.contentFontFamily
                                        font.pixelSize: Style.font.caption * root.textScale
                                        font.bold: true
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: root.errorText !== "" || root.filteredEmpty ? root.openSettings(0) : root.seedDemo()
                                    }
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
                            providerHealth: root.providers
                            calendars: root.calendars
                            palette: root.palette
                            fontFamily: root.contentFontFamily
                            textScale: root.textScale
                            pendingReset: root.pendingReset
                            pendingDisconnect: root.pendingDisconnect
                            busy: root.accountBusy
                            errorText: root.accountError
                            onUpdateRequested: function (key, value) {
                                root.updateDraft(key, value);
                            }
                            onApplyRequested: root.applySettings()
                            onCancelRequested: root.cancelSettings()
                            onSetupRequested: function (provider) {
                                root.openSetup(provider);
                            }
                            onEnableEditingRequested: function (provider, accountId) {
                                root.enableEditingFor(provider, accountId);
                            }
                            onDisconnectRequested: function (provider, accountId) {
                                root.requestDisconnect(provider, accountId);
                            }
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
                            onConfigureRequested: function (provider, clientId) {
                                root.configureClient(provider, clientId);
                            }
                            onImportRequested: function (source) {
                                root.importGoogleDesktop(source);
                            }
                            onAuthenticateRequested: function (provider, access) {
                                root.authenticate(provider, access);
                            }
                            onCancelRequested: {
                                root.showSetup = false;
                                root.openSettings(0);
                            }
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
                            Text {
                                textFormat: Text.PlainText
                                anchors.centerIn: parent
                                text: "Loading local calendar"
                                color: root.palette.accent
                                font.family: root.contentFontFamily
                                font.pixelSize: Style.font.body * root.textScale
                                font.bold: true
                            }
                        }
                    }
                }
            }
        }
    }
    function handleEscape() {
        if (root.pendingReset)
            root.pendingReset = false;
        else if (root.pendingDisconnect !== "")
            root.pendingDisconnect = "";
        else if (root.pendingCopiedOriginalUid !== "")
            root.keepBothCopies();
        else if (root.showEditor && editorSurface.confirmDelete)
            editorSurface.confirmDelete = false;
        else if (root.showEditor)
            root.cancelDraft();
        else if (root.showSetup) {
            root.showSetup = false;
            root.openSettings(0);
        } else if (root.showHelp)
            root.showHelp = false;
        else if (root.showSettings)
            root.cancelSettings();
        else if (root.expandedDetails)
            root.expandedDetails = false;
        else
            root.close();
    }
}
