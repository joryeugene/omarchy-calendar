# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT


class QmlContractTests(unittest.TestCase):
    def text(self, name):
        return (PLUGIN / name).read_text(encoding="utf-8")

    def test_root_manifest_and_bar_expose_namespaced_calendar_service(self):
        manifest = json.loads(self.text("manifest.json"))
        bar = self.text("BarWidget.qml")
        self.assertEqual(manifest["id"], "io.github.joryeugene.omarchy-calendar")
        self.assertEqual(manifest["version"], "1.1.0")
        self.assertEqual(set(manifest["kinds"]), {"bar-widget", "service"})
        self.assertEqual(manifest["entryPoints"]["barWidget"], "BarWidget.qml")
        self.assertEqual(manifest["entryPoints"]["service"], "Service.qml")
        self.assertIn('moduleName: "io.github.joryeugene.omarchy-calendar"', bar)
        self.assertIn(
            'target: "io.github.joryeugene.omarchy-calendar"',
            self.text("Service.qml"),
        )
        self.assertIn('"yyyy/MM/dd HH:mm"', self.text("SettingsModel.js"))
        self.assertNotIn("IpcHandler", bar)
        self.assertIn("IpcHandler", self.text("Service.qml"))
        self.assertIn('source: Qt.resolvedUrl("Panel.qml")', bar)
        self.assertIn("omarchy-menu-timezone", bar)

    def test_singleton_service_runs_the_bundled_helper_without_a_shell(self):
        service = self.text("Service.qml")
        self.assertIn('property string helperPath:', service)
        self.assertIn('Qt.resolvedUrl("calendarctl")', service)
        self.assertIn('[root.helperPath, "sync"]', service)
        self.assertNotIn('command = ["sh"', service)
        self.assertIn("property bool syncing", service)
        self.assertIn("property int revision", service)
        self.assertIn("property string lastError", service)
        self.assertIn("function requestSync()", service)
        self.assertIn("interval: root.syncIntervalMinutes * 60000", service)
        self.assertEqual(service.count("IpcHandler"), 1)

    def test_panel_contains_focus_time_grid_setup_status_and_seven_days(self):
        panel = self.text("Panel.qml")
        surfaces = "\n".join(self.text(name) for name in (
            "TodayView.qml", "WeekView.qml", "EventDetail.qml",
            "HelpOverlay.qml", "SetupView.qml",
        ))
        for identity in (
            "todayFocus", "weekTimeGrid", "allDayLane", "currentTimeLine",
            "eventDetail", "shortcutLegend", "setupState"
        ):
            self.assertIn(f'objectName: "{identity}"', surfaces)
        self.assertRegex(surfaces, r"Repeater\s*\{\s*model:\s*7")
        self.assertIn('helperCommand(["view"', panel)
        self.assertIn('calendarService.requestSync()', panel)
        self.assertIn('helperCommand(["open-meeting"', panel)
        self.assertIn('helperCommand(["open-source"', panel)
        self.assertIn("Demo data", panel)

    def test_event_detail_uses_human_time_and_structured_metadata(self):
        detail = self.text("EventDetail.qml")
        panel = self.text("Panel.qml")
        today = self.text("TodayView.qml")
        self.assertIn('import "CalendarModel.js" as CalendarModel', detail)
        self.assertIn("CalendarModel.formatTime(root.eventData)", detail)
        self.assertIn('text: "EVENT DETAILS"', detail)
        self.assertIn('text: "CONNECTION"', detail)
        self.assertIn('label: "Calendar"', detail)
        self.assertIn('label: "Provider"', detail)
        self.assertIn('label: "Account"', detail)
        self.assertIn('label: "Sync"', detail)
        self.assertIn("String(root.eventData.location)", detail)
        for label in ('"m  Join"', '"No meeting"', '"o  Source"', '"No source"'):
            self.assertIn(label, detail)
        for object_name in (
            'objectName: "meetingActionLabel"',
            'objectName: "sourceActionLabel"',
            'objectName: "editActionLabel"',
            'objectName: "copyActionLabel"',
        ):
            self.assertIn(object_name, detail)
        self.assertGreaterEqual(detail.count("elide: Text.ElideRight"), 7)
        self.assertIn("CalendarModel.updateStatus([providers[i]], root.nowTime)", panel)
        self.assertNotIn('"Synced " + String(providers[i].last_sync)', panel)
        self.assertIn("CalendarModel.providerLabel(modelData.provider)", today)
        self.assertIn('["g", "Current or next event"]', self.text("HelpOverlay.qml"))

    def test_header_status_is_compact_enough_not_to_overlap_navigation(self):
        panel = self.text("Panel.qml")
        self.assertIn("CalendarModel.updateStatus(root.providers, root.nowTime)", panel)
        self.assertIn("readonly property bool updateNeedsAttention", panel)
        self.assertIn('"Needs reconnect, showing cached data"', panel)
        self.assertNotIn('"Synced " + String(providers[0].last_sync', panel)

    def test_empty_error_state_explains_the_failure_and_recovery_actions(self):
        panel = self.text("Panel.qml")
        self.assertIn('root.errorText !== "" ? "CALENDAR UNAVAILABLE"', panel)
        self.assertIn('root.errorText !== "" ? root.errorText', panel)
        self.assertIn('root.errorText !== "" ? "r  Try again"', panel)
        self.assertIn('root.errorText !== "" || root.filteredEmpty ? "c  Calendar settings"', panel)

    def test_header_uses_button_labels_without_refresh_or_help(self):
        panel = self.text("Panel.qml")
        for label in ('"t  Today"', '"w  Week"', '"n  New"', '"s  Settings"'):
            self.assertIn(label, panel)
        for removed in ('"Refresh  r"', '"Help  ?"', '"New  n"', '"Settings  s"', "text: root.updateStatus"):
            self.assertNotIn(removed, panel)

    def test_help_lives_in_the_settings_sidebar(self):
        settings = self.text("SettingsView.qml")
        panel = self.text("Panel.qml")
        self.assertIn('"About and Privacy", "Help"', settings)
        self.assertIn("HelpOverlay", settings)
        self.assertIn("visible: root.sectionIndex === 4", settings)
        self.assertIn("root.showHelp = !root.showHelp", panel)

    def test_opening_the_panel_returns_to_today(self):
        panel = self.text("Panel.qml")
        self.assertRegex(panel, r"function open\(\)[\s\S]*?root\.goCurrent\(\)")

    def test_today_control_returns_to_the_current_day(self):
        panel = self.text("Panel.qml")
        self.assertRegex(panel, r"function goToday\(\)[\s\S]*?activeTab = \"today\";[\s\S]*?root\.goCurrent\(\)")
        self.assertIn('modelData.key === "today" ? root.goToday()', panel)
        self.assertRegex(panel, r'text === "t"\)\s*root\.goToday\(\)')

    def test_panel_declares_complete_non_alt_keyboard_contract(self):
        panel = self.text("Panel.qml")
        for key in (
            '"t"', '"w"', '"j"', '"k"', '"h"', '"l"', '"["', '"]"',
            '"g"', '"m"', '"o"', '"c"', '"r"', '"?"'
        ):
            self.assertIn(key, panel)
        self.assertIn("onActivateRequested:", panel)
        self.assertIn("onCloseRequested:", panel)
        self.assertNotIn("AltModifier", panel)
        self.assertIn("CalendarKeyCatcher {", panel)
        self.assertIn("onModifiedMoveRequested:", panel)
        catcher = self.text("CalendarKeyCatcher.qml")
        self.assertIn("event.modifiers & Qt.ShiftModifier", catcher)
        for key in ("H", "J", "K", "L"):
            self.assertIn(f"event.key === Qt.Key_{key}", catcher)
        self.assertNotIn('text === "O"', panel)
        self.assertNotIn("J  JOIN", panel)
        self.assertNotIn("O  SOURCE", panel)
        help_dispatch = 'if (text === "?" && !root.showSetup && !root.showEditor)'
        self.assertIn(help_dispatch, panel)
        text_handler = panel[panel.index("onTextKey:"):]
        self.assertLess(text_handler.index(help_dispatch), text_handler.index("if (root.showSettings)"))

    def test_opening_settings_restores_keyboard_focus(self):
        panel = self.text("Panel.qml")
        settings = panel[panel.index("function openSettings"):panel.index("function updateDraft")]
        self.assertIn("Qt.callLater(function () { keyCatcher.forceActiveFocus(); });", settings)

    def test_week_navigation_tracks_day_and_uid_and_selects_all_day_cards(self):
        panel = self.text("Panel.qml")
        week = self.text("WeekView.qml")
        self.assertIn("property date selectedDay", panel)
        self.assertIn("property string selectedUid", panel)
        self.assertIn("CalendarModel.moveWithinDay", panel)
        self.assertIn("CalendarModel.closestUidForDay", panel)
        self.assertIn("function moveDay", panel)
        self.assertIn("function moveHorizontal", panel)
        self.assertIn("CalendarModel.moveAcrossOverlap", panel)
        self.assertIn("CalendarModel.moveWeekVertical", panel)
        self.assertIn("allDayFor", week)
        self.assertIn('text: root.overlapPosition ? "Overlap " + root.overlapPosition : ""', week)
        self.assertIn("root.selectedUid === String(modelData.uid", week)
        self.assertIn("root.weekDays[index]", week)
        self.assertIn("root.selectedDay", week)
        self.assertIn("property date eventDay", week)
        self.assertEqual(
            week.count("property date eventDay: CalendarModel.eventDay(modelData)"),
            2,
        )
        self.assertEqual(week.count("onTapped: root.eventSelected(String(modelData.uid"), 2)
        self.assertNotIn("allDayColumn", week)

    def test_week_keyboard_selection_keeps_the_selected_event_in_view(self):
        week = self.text("WeekView.qml")
        self.assertIn("function revealSelectedEvent()", week)
        self.assertIn("onSelectedUidChanged: Qt.callLater(revealSelectedEvent)", week)
        self.assertIn("gridFlick.contentY", week)
        self.assertIn("selectedEvent.all_day", week)
        self.assertIn("gridFlick.contentHeight, Style.space(56))", week)

    def test_both_views_expose_clickable_period_navigation_and_now(self):
        panel = self.text("Panel.qml")
        navigator = self.text("DateNavigator.qml")
        self.assertIn('objectName: "dateNavigator"', navigator)
        self.assertIn('objectName: "previousPeriodButton"', navigator)
        self.assertIn('objectName: "nextPeriodButton"', navigator)
        self.assertIn('objectName: "nowButton"', navigator)
        self.assertIn("onPreviousRequested: root.stepPeriod(-1)", panel)
        self.assertIn("onNextRequested: root.stepPeriod(1)", panel)
        self.assertIn("onNowRequested: root.goCurrent()", panel)
        self.assertIn('text === "g"', panel)
        self.assertIn("CalendarModel.periodState", panel)

    def test_calendar_visibility_is_grouped_local_and_applies_to_both_views(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        model = self.text("SettingsModel.js")
        self.assertIn("hiddenCalendars", model)
        self.assertIn("visibleCalendarEvents", panel)
        self.assertIn("calendars: root.calendars", panel)
        self.assertIn('objectName: "calendarVisibilityList"', settings)
        self.assertIn("Show all", settings)
        self.assertIn("Hide all", settings)
        self.assertIn("toggleCalendar", settings)
        self.assertIn("id: calendarScroll", settings)
        self.assertIn("function bulkControlCount()", settings)
        self.assertIn("function groupControlIndex(provider, visible)", settings)
        self.assertIn("setProviderVisible(group.provider, show)", settings)
        self.assertIn("root.groupControlIndex(providerCalendarGroup.modelData.provider, true)", settings)
        self.assertIn("root.groupControlIndex(providerCalendarGroup.modelData.provider, false)", settings)
        self.assertIn("Calendars appear here after the first successful sync.", settings)
        self.assertNotIn("after their first event is cached", settings)

    def test_week_selection_strip_uses_compact_padding_and_remaining_height(self):
        week = self.text("WeekView.qml")
        self.assertIn('objectName: "weekDayHeader"', week)
        self.assertIn('objectName: "weekSelectionStrip"', week)
        self.assertIn("weekLayout.spacing * 3", week)
        self.assertIn("anchors.margins: Style.space(6)", week)
        self.assertIn("height: Style.space(38)", week)
        self.assertIn("height: Style.space(30)", week)
        self.assertIn('objectName: "weekSelectionInfo"', week)
        self.assertGreaterEqual(week.count("verticalAlignment: Text.AlignVCenter"), 5)

    def test_today_keyboard_selection_keeps_the_selected_event_in_view(self):
        today = self.text("TodayView.qml")
        self.assertIn("function revealSelectedEvent()", today)
        self.assertIn("onSelectedUidChanged: Qt.callLater(revealSelectedEvent)", today)
        self.assertIn("CalendarModel.revealOffset", today)

    def test_settings_use_clear_meaningful_appearance_choices(self):
        settings = self.text("SettingsView.qml")
        panel = self.text("Panel.qml")
        self.assertIn('visible: root.activeTab === "today" && !root.showSettings && !root.showSetup', panel)
        self.assertIn('visible: root.activeTab === "week" && !root.showSettings && !root.showSetup', panel)
        self.assertIn('label: "Roomy"', settings)
        self.assertIn('label: "On"', settings)
        self.assertIn('label: "Off"', settings)
        self.assertIn('objectName: "densityPreview"', settings)
        self.assertNotIn('label: "Comfortable"', settings)
        self.assertNotIn('label: "Restrained"', settings)
        self.assertNotIn('label: "Reduced"', settings)
        self.assertIn("previewSettings.animations", panel)

    def test_calendar_settings_are_reachable_and_drive_bounded_helper_commands(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        setup = self.text("SetupView.qml")
        self.assertIn(
            "Flight Deck Calendar puts Google Calendar and Outlook in one Omarchy panel. Accounts are read-only by default.",
            settings,
        )
        self.assertIn('modelData.editing ? "Editing enabled" : "Connected and read-only"', settings)
        self.assertIn("calendar.events.owned", settings)
        self.assertIn("Calendars.ReadWrite", settings)
        self.assertIn('import "SettingsModel.js" as SettingsModel', settings)
        self.assertIn('signal enableEditingRequested(string provider, string accountId)', settings)
        self.assertIn('signal disconnectRequested(string provider, string accountId)', settings)
        self.assertIn('helperCommand(["enable-editing", provider, "--account", accountId])', panel)
        self.assertIn('objectName: "settingsSurface"', settings)
        self.assertIn('objectName: "publicClientInput"', setup)
        for state in (
            "showSettings", "setupProviders", "setupProvider", "pendingDisconnect",
            "accountBusy", "accountError",
        ):
            self.assertIn(state, panel)
        for command in (
            'helperCommand(["setup-status"',
            'helperCommand(["configure-client"',
            'helperCommand(["import-google-desktop-app"',
            'helperCommand(["disconnect"',
            'helperCommand(["auth"',
            'helperCommand(["reset-local-data"',
        ):
            self.assertIn(command, panel)
        for label in (
            "Connect", "Disconnect", "Confirm", "Confirm reset", "read-only", "system keyring",
        ):
            self.assertIn(label, settings + setup)
        self.assertIn("TextInput", setup)
        self.assertNotIn("TextInput.Password", setup)

    def test_identity_setup_skips_local_inputs_for_complete_bundles_and_stays_secret_free(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        setup = self.text("SetupView.qml")
        for label in (
            "This build has no bundled Google registration", "Import Google Desktop credentials JSON (advanced)",
            "WHAT FLIGHT DECK REQUESTS", "Connect in browser", "No hosted backend",
            "Flight Deck's bundled registration is ready",
        ):
            self.assertIn(label, setup)
        self.assertIn("import QtQuick.Dialogs", setup)
        self.assertIn("FileDialog", setup)
        self.assertIn("FileDialog.OpenFile", setup)
        self.assertIn("onAccepted: root.importRequested(String(selectedFile))", setup)
        self.assertIn("signal importRequested(string source)", setup)
        self.assertRegex(panel, r"onImportRequested:\s*function\s*\(source\)\s*\{\s*root\.importGoogleDesktop\(source\)")
        self.assertIn("setupSurface.activatePrimary()", panel)
        self.assertIn("setupSurface.clearDraft()", panel)
        self.assertIn("Flickable", setup)
        self.assertIn("contentHeight: content.implicitHeight + Style.space(44)", setup)
        self.assertIn("system keyring", setup)
        self.assertIn("personal-account capable", setup)
        self.assertIn("Calendar events read-only", setup)
        self.assertIn("Calendars.Read", setup)
        self.assertIn('visible: root.provider === "microsoft" && !root.providerState.client_configured', setup)
        self.assertIn('registration_source: ""', panel)
        self.assertIn('root.providerState.registration_source === "bundled"', setup)
        self.assertIn("Flight Deck's bundled registration is ready", setup)
        self.assertIn("Your local registration is ready", setup)
        self.assertIn(
            "root.authenticateRequested(root.provider, root.accessChoice)",
            setup,
        )
        self.assertIn("function cycleAccess(direction)", setup)
        self.assertIn("setupSurface.cycleAccess(dx)", panel)
        self.assertIn('text === "h" || text === "l"', panel)
        self.assertIn("implicitHeight: content.implicitHeight + Style.space(44)", setup)
        self.assertIn("height: Math.min(parent.height - Style.space(50), setupSurface.implicitHeight)", panel)
        self.assertIn("Authenticate in your browser when connecting", settings)
        self.assertNotIn("The public release will hide this step", setup)
        self.assertNotIn("clientSecret", setup)
        self.assertNotIn("Client secret", setup)

    def test_write_layer_is_opt_in_and_em_dash_free(self):
        executable = "\n".join(self.text(name) for name in (
            "BarWidget.qml", "Panel.qml", "CalendarModel.js", "SettingsModel.js",
            "TodayView.qml", "WeekView.qml", "SettingsView.qml", "SetupView.qml",
            "HelpOverlay.qml", "EventDetail.qml", "EventEditor.qml", "CopyResultOffer.qml",
            "EventEditorModel.js", "Service.qml",
        ))
        all_copy = executable
        for required in (
            "Read only", "Read and edit", "enable-editing", "create-event", "update-event",
            "copy-event", "delete-event",
        ):
            self.assertIn(required, executable)
        for forbidden in ("sendUpdates", "this and following"):
            self.assertNotIn(forbidden, executable.lower())
        self.assertNotIn("Private builds require provider registration", executable)
        self.assertNotIn("—", all_copy)

    def test_event_editor_matches_the_approved_keyboard_and_pointer_contract(self):
        panel = self.text("Panel.qml")
        editor = self.text("EventEditor.qml")
        copy_result = self.text("CopyResultOffer.qml")
        week = self.text("WeekView.qml")
        model = self.text("EventEditorModel.js")
        self.assertIn('import "EventEditorModel.js" as EventEditorModel', panel)
        self.assertIn("EventEditor {", panel)
        for state in (
            "showEditor", "editorDraft", "editorMode", "mutationBusy", "pendingCopiedOriginalUid",
            "confirmCopiedOriginalDelete",
        ):
            self.assertIn(state, panel)
        for shortcut in ('text === "n"', 'text === "e"', 'text === "d"'):
            self.assertIn(shortcut, panel)
        self.assertIn('sequences: ["Ctrl+Return", "Ctrl+Enter"]', editor)
        self.assertIn("onActivated: root.submit()", editor)
        self.assertIn("Ctrl+Enter", editor)
        self.assertIn("Esc", editor)
        self.assertIn("function beginCreate", panel)
        self.assertIn("((Number(value || 0) % 1440) + 1440) % 1440", panel)
        self.assertIn("function beginEdit", panel)
        self.assertIn("function beginDuplicate", panel)
        self.assertIn("function saveDraft", panel)
        self.assertIn("function cancelDraft", panel)
        self.assertIn('if (root.showEditor && String(root.editorDraft.source_uid || "") === String(uid || ""))', panel)
        self.assertIn("function resetInteraction()", editor)
        self.assertGreaterEqual(panel.count("editorSurface.resetInteraction()"), 3)
        for field in (
            "Title", "Calendar", "Day", "Start", "End", "All-day", "Location", "Notes",
            "Recurrence", "Online meeting",
        ):
            self.assertIn(field, editor)
        for label in (
            "This occurrence", "Entire series", "Copy event", "Delete original",
            "Generate a new meeting", "Keep existing meeting link",
        ):
            self.assertIn(label.lower(), (editor + panel + copy_result).lower())
        self.assertIn("DragHandler", week)
        self.assertIn('objectName: "eventResizeHandle"', week)
        self.assertIn('objectName: "draftMoveHandle"', week)
        self.assertIn('objectName: "draftResizeHandle"', week)
        self.assertIn('root.eventDragged(root.editingUid', week)
        self.assertIn('root.eventResized(root.editingUid', week)
        self.assertEqual(week.count("onGrabChanged: function (transition)"), 6)
        self.assertEqual(week.count("transition === PointerDevice.CancelGrabExclusive"), 6)
        self.assertEqual(week.count("transition !== PointerDevice.UngrabExclusive"), 6)
        self.assertNotIn("onActiveChanged: if (!active && persistentTranslation", week)
        self.assertIn('root.editingDraft ? String(root.editingDraft.title', week)
        self.assertIn("emptySlotRequested", week)
        self.assertIn("eventDragged", week)
        self.assertIn("eventResized", week)
        self.assertIn("EventEditorModel.shift", panel)
        self.assertIn("function destinations", model)
        self.assertIn("item.sync_enabled !== false", editor)
        self.assertIn("EventEditorModel.toggleAllDay(root.draft)", editor)
        self.assertIn("EventEditorModel.meetingOptions(root.draft, root.eventData, root.calendars)", editor)
        self.assertIn("account_label", editor)
        self.assertIn("EventEditorModel.visibleControls(root.draft, root.mode, root.recurring, root.hasMeeting, root.canDelete)", editor)
        self.assertIn("root.copyMeetingRequested()", editor)
        for update in (
            'onTextEdited: root.draftUpdated(EventEditorModel.withDay(root.draft, text))',
            'EventEditorModel.withTime(root.draft, "start", text)',
            'EventEditorModel.withTime(root.draft, "end", text)',
            'onTextEdited: root.updateRecurrence("count", Number(text))',
            'onTextEdited: root.updateRecurrence("until", text)',
        ):
            self.assertIn(update, editor)
        self.assertIn("EventEditorModel.toggleWeekday(root.draft", editor)
        self.assertIn("EventEditorModel.withCalendar(", editor)
        self.assertIn('next.scope = "series"', editor)
        self.assertIn('function setScope(value)', editor)
        self.assertIn('frequency: root.mode === "update" ? "preserve" : "none"', editor)
        self.assertIn('root.actionNotice = "Meeting link copied"', panel)
        self.assertIn("noticeText: root.actionNotice", panel)
        self.assertIn("text: root.noticeText", editor)
        self.assertIn('root.actionNotice = String(result.notice || (', panel)
        self.assertIn('completedAction === "delete-event" ? "Event deleted"', panel)
        self.assertEqual(panel.count("confirmed: true"), 2)
        self.assertIn('completedAction === "copy-event" ? "Copy saved" : "Event saved"', panel)
        self.assertIn('root.actionNotice !== "" ? root.actionNotice', panel)
        self.assertIn('objectName: "editorScrollAffordance"', editor)
        self.assertIn("editorScroll.contentHeight > editorScroll.height", editor)
        self.assertEqual(editor.count('inputMask: "99:99"'), 2)
        self.assertEqual(editor.count("visible: !root.draft.all_day"), 2)
        self.assertGreaterEqual(editor.count("autoScroll: activeFocus"), 2)
        for name in ("startMinus", "startPlus", "endMinus", "endPlus", "editorKeyboardHints"):
            self.assertIn(f'objectName: "{name}"', editor)
        self.assertGreaterEqual(editor.count("TimeStepButton {"), 4)
        self.assertIn('text: "h / l  Change value\\nj / k  Change field\\nCtrl+Enter  Save\\nEsc  Cancel"', editor)
        self.assertIn("function revealDeleteConfirmation()", editor)
        self.assertGreaterEqual(editor.count("root.revealDeleteConfirmation()"), 2)
        self.assertIn(
            "onContentHeightChanged: if (root.confirmDelete || root.statusNeedsReveal())",
            editor,
        )
        self.assertIn('text: root.recurring && !root.seriesOnly ? "This occurrence"', editor)
        self.assertIn('text: "Entire series"', editor)
        self.assertIn('text: parent.modelData', editor)
        self.assertNotIn('text: parent.modelData.slice(0, 1)', editor)
        self.assertIn('frequency !== "none" && frequency !== "preserve"', editor)
        self.assertRegex(editor, r'visible:\s*root\.canDelete\s*\n\s*width: parent\.width')
        self.assertRegex(panel, r'function deleteDraft\(scope\) \{\s*if \(root\.editorMode !== "update"\)\s*return;')
        self.assertNotIn("needsPermission", editor)
        self.assertIn("calendars: root.editableCalendars()", panel)
        self.assertIn("function requestWriteIntent", panel)
        self.assertIn("onDuplicateRequested: root.beginDuplicate(root.editorSource)", panel)
        self.assertIn('root.unsupportedEvent ? "Duplicate"', editor)
        cancel_draft = panel[panel.index("function cancelDraft()") : panel.index("function startMutation")]
        self.assertIn("keyCatcher.forceActiveFocus()", cancel_draft)
        self.assertIn("root.selectedUid = root.editorReturnUid", cancel_draft)
        self.assertIn("root.selectedDay = new Date(root.editorReturnDay)", cancel_draft)
        begin_create = panel[panel.index("function openCreateDraft(day, minute)") : panel.index("function openEditDraft")]
        self.assertIn("root.editorReturnUid = root.selectedUid", begin_create)
        self.assertIn("root.editorReturnDay = new Date(root.selectedDay)", begin_create)
        self.assertIn('settingsSurface.focusAccountAction(decision.provider, decision.account_id, "enable")', panel)
        self.assertIn('root.confirmDelete ? "x  Confirm delete" : "x  Delete original"', copy_result)
        self.assertIn('objectName: "copyResultMessage"', copy_result)
        self.assertRegex(copy_result, r'objectName:\s*"copyResultMessage"[\s\S]{0,700}?maximumLineCount:\s*2')
        self.assertRegex(panel, r'onDeleteRequested:\s*if \(root\.pendingCopiedOriginalUid !== ""\)\s*root\.deleteCopiedOriginal\(\)')
        self.assertIn('text: "k  Keep both"', copy_result)
        move_handler = panel[panel.index("onMoveRequested:"):panel.index("onActivateRequested:")]
        self.assertIn('if (root.pendingCopiedOriginalUid !== "")', move_handler)
        self.assertIn("if (dy < 0) root.keepBothCopies()", move_handler)
        self.assertRegex(
            panel,
            r"onTabRequested:\s*function\s*\(direction\)\s*\{\s*if \(!root\.showSettings && !root\.showSetup && !root\.showEditor\)",
        )

    def test_copy_mode_preserves_explicit_occurrence_or_series_deletion_scope(self):
        editor = self.text("EventEditor.qml")
        panel = self.text("Panel.qml")

        self.assertIn('Boolean(eventData &&', editor)
        self.assertIn('root.pendingCopiedOriginalScope = String(result.original_scope || "single")', panel)
        self.assertIn('root.pendingCopiedOriginalSeriesRevision = String(result.original_series_revision || "")', panel)
        self.assertIn("expected_revision: root.editorDraft.source_revision", panel)
        self.assertIn("series_revision: root.editorDraft.series_revision", panel)
        self.assertIn("expected_revision: root.pendingCopiedOriginalRevision", panel)
        self.assertIn("series_revision: root.pendingCopiedOriginalSeriesRevision", panel)
        self.assertIn('series_transfer_guard: root.pendingCopiedOriginalScope === "series"', panel)
        self.assertIn("root.eventData.has_attendees", editor)
        self.assertIn("Events with attendees are duplicate-only", editor)

    def test_series_master_editor_has_no_occurrence_actions(self):
        editor = self.text("EventEditor.qml")

        self.assertIn("readonly property bool seriesOnly: root.draft.series_only === true", editor)
        self.assertIn('next.scope = root.seriesOnly ? "series" : value', editor)
        self.assertRegex(editor, r"visible:\s*root\.recurring && !root\.seriesOnly")
        self.assertIn('root.deleteRequested(root.seriesOnly ? "series" : "single")', editor)
        self.assertIn('root.recurring && !root.seriesOnly ? "This occurrence"', editor)

    def test_every_successful_copy_shows_a_bounded_result_with_safe_actions(self):
        panel = self.text("Panel.qml")
        result = self.text("CopyResultOffer.qml")

        self.assertIn('root.pendingCopiedOriginalUid = String(result.original_uid || "")', panel)
        self.assertIn("delete_original_needs_permission", panel)
        self.assertIn("delete_original_reason", panel)
        self.assertIn("function enableCopiedOriginalEditing()", panel)
        self.assertIn('objectName: "copyResultOffer"', result)
        self.assertIn('objectName: "copyResultMessage"', result)
        self.assertIn("maximumLineCount: 2", result)
        self.assertIn("elide: Text.ElideRight", result)
        self.assertIn('text: "k  Keep both"', result)
        self.assertIn('root.needsPermission ? "e  Enable editing"', result)
        self.assertIn("visible: root.canDeleteOriginal || root.needsPermission", result)
        self.assertIn("root.needsPermission ? root.enableEditingRequested() : root.deleteRequested()", result)
        self.assertRegex(result, r"height:\s*Style\.space\(112\)")

    def test_copy_permission_upgrade_enables_delete_without_deleting_automatically(self):
        panel = self.text("Panel.qml")

        self.assertIn('root.copyEditAuthorizationPending = true', panel)
        self.assertIn('var copiedOriginalUpgrade = root.copyEditAuthorizationPending', panel)
        self.assertIn('else if (copiedOriginalUpgrade && root.pendingCopiedOriginalUid !== "")', panel)
        self.assertIn('root.pendingCopiedOriginalDeleteAvailable = true', panel)
        self.assertIn('root.pendingCopiedOriginalNeedsPermission = false', panel)
        self.assertNotRegex(
            panel,
            r'copyEditAuthorizationPending[\s\S]{0,500}?startMutation\("delete-event"',
        )

    def test_copy_result_rechecks_source_health_before_delete(self):
        panel = self.text("Panel.qml")

        self.assertIn("readonly property bool pendingCopiedOriginalOffline: root.copySourceOffline()", panel)
        self.assertIn("function copySourceOffline()", panel)
        self.assertRegex(
            panel,
            r'function deleteCopiedOriginal\(\) \{[\s\S]{0,180}?pendingCopiedOriginalOffline\)\s*return;',
        )
        self.assertIn(
            "canDeleteOriginal: root.pendingCopiedOriginalDeleteAvailable && !root.pendingCopiedOriginalOffline",
            panel,
        )
        self.assertIn(
            "needsPermission: root.pendingCopiedOriginalNeedsPermission && !root.pendingCopiedOriginalOffline",
            panel,
        )

    def test_editor_inputs_return_to_keyboard_navigation_with_tab(self):
        editor = self.text("EventEditor.qml")
        panel = self.text("Panel.qml")

        self.assertIn("signal inputNavigationRequested(int direction)", editor)
        self.assertIn("Qt.Key_Tab", editor)
        self.assertIn("Qt.Key_Backtab", editor)
        self.assertIn("onInputNavigationRequested", panel)

    def test_editor_fields_bound_long_content_inside_their_controls(self):
        editor = self.text("EventEditor.qml")

        for input_id in (
            "titleInput", "dayInput", "startInput", "endInput",
            "locationInput", "countInput", "untilInput",
        ):
            self.assertRegex(editor, rf"id:\s*{input_id}[\s\S]{{0,500}}?clip:\s*true")
        self.assertIn("id: notesScroll", editor)
        self.assertIn("contentHeight: Math.max(height, notesInput.contentHeight)", editor)
        self.assertRegex(editor, r"id:\s*notesScroll[\s\S]{0,300}?clip:\s*true")

    def test_nonrecurring_choice_resets_hidden_ending_fields(self):
        editor = self.text("EventEditor.qml")

        self.assertIn('recurrence.end = "never"', editor)
        self.assertIn('recurrence.count = 0', editor)
        self.assertIn('recurrence.until = ""', editor)

    def test_delete_obeys_editor_safety_and_permission_state(self):
        editor = self.text("EventEditor.qml")
        panel = self.text("Panel.qml")

        self.assertIn("readonly property bool canDelete:", editor)
        self.assertIn("EventEditorModel.visibleControls(root.draft, root.mode, root.recurring, root.hasMeeting, root.canDelete)", editor)
        self.assertRegex(editor, r'visible:\s*root\.canDelete\s*\n\s*width: parent\.width')
        self.assertIn('var decision = EventEditorModel.writeDecision(kind, event, root.calendars, root.setupProviders)', panel)
        self.assertIn('if (decision.action === "settings")', panel)
        self.assertIn('root.openSettings(0)', panel)

    def test_conflict_reload_preserves_the_editor_draft(self):
        panel = self.text("Panel.qml")

        self.assertIn("EventEditorModel.isMutationConflict(failure)", panel)
        self.assertRegex(
            panel,
            r'if \(EventEditorModel\.isMutationConflict\(failure\)\) \{\s*root\.loadView\(\);\s*root\.refreshProviders\(\);\s*\}',
        )

    def test_all_day_drafts_have_a_local_drag_overlay(self):
        week = self.text("WeekView.qml")
        panel = self.text("Panel.qml")

        self.assertIn("root.editingDraft && root.editingDraft.all_day", week)
        self.assertIn("root.eventDragged(root.editingUid", week)
        self.assertRegex(
            panel,
            r'function openCreateDraft\(day, minute\)[\s\S]{0,500}?selectedDay = new Date\(day \|\| root\.selectedDay\);[\s\S]{0,120}?selectedUid = "";',
        )

    def test_dragging_an_unselected_event_synchronizes_panel_selection(self):
        panel = self.text("Panel.qml")
        shift_draft = panel[
            panel.index("function shiftDraft") : panel.index("function cancelDraft")
        ]

        self.assertRegex(
            shift_draft,
            r"var source = root\.cachedEvent\(uid\);[\s\S]*?"
            r"root\.selectUid\(uid, CalendarModel\.eventDay\(source\)\);[\s\S]*?"
            r'root\.requestWriteIntent\("move", source',
        )

    def test_week_selection_strip_reserves_room_for_all_actions(self):
        week = self.text("WeekView.qml")

        self.assertIn("width: parent.width * (root.overlapPosition ? 0.27 : 0.43)", week)
        self.assertIn("width: parent.width * 0.32", week)

    def test_mutations_send_event_json_through_stdin_only(self):
        panel = self.text("Panel.qml")
        self.assertIn("stdinEnabled: true", panel)
        self.assertIn('write(mutationPayload + "\\n")', panel)
        self.assertIn("root.mutationPayload = JSON.stringify(payload)", panel)
        self.assertNotRegex(panel, r'helperCommand\(\["(?:create|update|copy|delete)-event",')

    def test_every_qml_text_object_forces_plain_text(self):
        for path in sorted(PLUGIN.glob("*.qml")):
            source = path.read_text(encoding="utf-8")
            text_objects = re.findall(r"\bText\s*\{", source)
            protected = re.findall(
                r"\bText\s*\{\s*(?:id\s*:\s*\w+\s*)?textFormat\s*:\s*Text\.PlainText\b",
                source,
            )
            self.assertEqual(
                len(protected),
                len(text_objects),
                f"{path.name} leaves a Text object on AutoText",
            )

    def test_qml_child_objects_are_not_separated_by_semicolons(self):
        qml = "\n".join(self.text(path.name) for path in PLUGIN.glob("*.qml"))
        self.assertIsNone(re.search(r"}\s*;\s*(?:MouseArea|Text|Rectangle|Row|Column|Item)\s*{", qml))

    def test_help_cards_use_the_named_grid_for_spacing(self):
        help_overlay = self.text("HelpOverlay.qml")
        self.assertIn("id: helpGrid", help_overlay)
        self.assertIn("helpGrid.columnSpacing", help_overlay)
        self.assertNotIn("parent.columnSpacing", help_overlay)
        self.assertIn("height: Style.space(164)", help_overlay)
        self.assertIn("anchors.margins: Style.space(6)", help_overlay)
        self.assertIn('["Enter / Space", "Activate control"]', help_overlay)
        self.assertIn('["m", "Join meeting"]', help_overlay)
        self.assertIn("width: Style.space(96)", help_overlay)

    def test_help_overlay_documents_editor_recurrence_and_copy_result_keys(self):
        help_overlay = self.text("HelpOverlay.qml")

        for row in (
            '["r", "Refresh calendars"]',
            '["?", "Toggle help"]',
            '["s", "Open Settings"]',
            '["c", "Open Calendars"]',
            '["h / l", "Move between sections"]',
            '["j / k", "Move between controls"]',
            '["n / e / d", "New, edit, or duplicate"]',
            '["Shift+H / L", "Move draft one day"]',
            '["Shift+J / K", "Move draft 15 minutes"]',
            '["j / k", "Move between editor fields"]',
            '["h / l", "Change the field value"]',
            '["Enter", "Choose recurrence scope or delete"]',
            '["Ctrl+Enter", "Save the draft"]',
            '["Esc", "Cancel the draft"]',
            '["k", "Keep both copies"]',
            '["e", "Enable source editing"]',
            '["x", "Delete or confirm original"]',
        ):
            self.assertIn(row, help_overlay)

    def test_panel_is_split_into_focused_release_components(self):
        panel = self.text("Panel.qml")
        self.assertLess(len(panel.splitlines()), 1650)
        for name in (
            "TodayView.qml", "WeekView.qml", "SettingsView.qml",
            "SetupView.qml", "HelpOverlay.qml", "EventDetail.qml",
        ):
            self.assertTrue((PLUGIN / name).is_file(), name)
        self.assertIn("TodayView", panel)
        self.assertIn("WeekView", panel)
        self.assertIn("SettingsView", panel)
        self.assertIn("SetupView", panel)
        self.assertIn("HelpOverlay", panel)
        self.assertIn("EventDetail", self.text("TodayView.qml"))

    def test_settings_surface_covers_the_release_schema_and_keyboard_flow(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        self.assertIn('import "SettingsModel.js" as SettingsModel', panel)
        for key in (
            "theme", "density", "textScale", "animations", "defaultView",
            "weekStartHour", "weekEndHour", "timeFormat",
            "syncIntervalMinutes", "format", "formatAlt",
            "verticalFormat", "verticalFormatAlt", "hiddenCalendars",
        ):
            self.assertIn(key, panel + settings)
        for label in ("Calendars", "Appearance", "Preferences", "About and Privacy"):
            self.assertIn(label, settings)
        for preset in ("Kinetic Tokyo Night", "Follow Omarchy", "High Contrast"):
            self.assertIn(preset, settings)
        for function in ("openSettings", "applySettings", "cancelSettings", "updateDraft"):
            self.assertIn(f"function {function}", panel)
        self.assertIn('text === "s"', panel)
        self.assertIn('text === "c"', panel)
        self.assertIn('text === "a"', panel)
        self.assertRegex(panel, r'if \(text === "a"\)\s+root\.applySettings\(\)')
        self.assertIn("SettingsModel.normalize", panel)
        self.assertIn("SettingsModel.palette", panel)
        self.assertIn("root.cycleControl(index, -1)", settings)

    def test_settings_footer_reserves_space_for_apply_and_cancel(self):
        settings = self.text("SettingsView.qml")
        self.assertIn("height: parent.height - Style.space(168)", settings)
        self.assertNotIn("height: parent.height - Style.space(100)", settings)

    def test_settings_keyboard_hint_is_anchored_above_the_rounded_edge(self):
        settings = self.text("SettingsView.qml")
        self.assertIn('objectName: "settingsKeyboardHint"', settings)
        self.assertIn("anchors.bottom: parent.bottom", settings)
        self.assertNotIn("parent.height - Style.space(292)", settings)

    def test_panel_uses_the_semantic_key_catcher_once_per_keypress(self):
        panel = self.text("Panel.qml")
        self.assertEqual(panel.count("onActivateRequested:"), 1)
        self.assertEqual(panel.count("onCloseRequested:"), 1)
        self.assertNotIn("Keys.onPressed", panel)

    def test_reset_is_two_step_and_google_setup_has_no_secret_field(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        setup = self.text("SetupView.qml")
        self.assertIn("pendingReset", panel + settings)
        self.assertIn("Confirm reset", settings)
        self.assertIn('helperCommand(["reset-local-data"]', panel)
        self.assertNotIn("clientSecret", setup)
        self.assertNotIn("Client secret", setup)

    def test_bar_rereads_canonical_inline_settings_after_reload(self):
        bar = self.text("BarWidget.qml")
        self.assertIn("shellConfig", bar)
        self.assertIn("canonicalSettings", bar)
        self.assertIn("root.canonicalSettings", bar)
        self.assertIn("calendarService.syncIntervalMinutes", bar)

    def test_empty_state_does_not_cover_an_open_event_draft(self):
        panel = self.text("Panel.qml")
        self.assertIn("visible: root.showEmptyState", panel)
        self.assertIn(
            '&& (!root.hasConnectedAccount || root.errorText !== "" || root.filteredEmpty)',
            panel,
        )

    def test_host_bar_api_is_called_through_its_scoped_setter(self):
        panel = self.text("Panel.qml")
        setup = self.text("SetupView.qml")
        self.assertIn('typeof root.bar.setCenterHoverRevealSuppressed === "function"', panel)
        self.assertIn("root.bar.setCenterHoverRevealSuppressed(value)", panel)
        self.assertIn("options: FileDialog.DontUseNativeDialog", setup)

    def test_google_setup_prefers_browser_auth_and_keeps_the_json_import(self):
        setup = self.text("SetupView.qml")
        self.assertIn('"Connect in browser"', setup)
        self.assertIn("Import Google Desktop credentials JSON (advanced)", setup)
        self.assertIn('visible: root.provider === "google"', setup)
        self.assertIn("googleCredentialsDialog.open()", setup)

    def test_connected_accounts_hide_the_empty_state_card(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        self.assertIn("hasConnectedAccount", panel)
        self.assertIn("showEmptyState", panel)
        self.assertIn("!root.hasConnectedAccount", panel)
        self.assertNotIn("NO EVENTS IN THIS PERIOD", panel)
        self.assertIn('objectName: "emptyStateClose"', panel)
        self.assertIn('modelData.kind === "add" ? "Add account"', settings)
        self.assertNotIn("Add account", panel)


if __name__ == "__main__":
    unittest.main()
