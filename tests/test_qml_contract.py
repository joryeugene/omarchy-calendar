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
        self.assertEqual(manifest["version"], "1.0.0-rc.3")
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
        self.assertIn('manifest.__sourceDir', service)
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
        self.assertIn('"m  Join meeting"', detail)
        self.assertIn("CalendarModel.updateStatus([providers[i]], root.nowTime)", panel)
        self.assertNotIn('"Synced " + String(providers[i].last_sync)', panel)
        self.assertIn("CalendarModel.providerLabel(modelData.provider)", today)

    def test_header_status_is_compact_enough_not_to_overlap_navigation(self):
        panel = self.text("Panel.qml")
        self.assertIn("CalendarModel.updateStatus(root.providers, root.nowTime)", panel)
        self.assertNotIn('"Synced " + String(providers[0].last_sync', panel)

    def test_empty_error_state_explains_the_failure_and_recovery_actions(self):
        panel = self.text("Panel.qml")
        self.assertIn('root.errorText !== "" ? "CALENDAR UNAVAILABLE"', panel)
        self.assertIn('root.errorText !== "" ? root.errorText', panel)
        self.assertIn('root.errorText !== "" ? "r  Try again"', panel)
        self.assertIn('root.errorText !== "" ? "c  Calendar settings"', panel)

    def test_header_labels_actions_before_their_keyboard_hints(self):
        panel = self.text("Panel.qml")
        for label in ('"Refresh  r"', '"Settings  s"', '"Help  ?"'):
            self.assertIn(label, panel)
        for old_label in ('"r  Refresh"', '"s  Settings"', 'text: "?"'):
            self.assertNotIn(old_label, panel)

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
        self.assertNotIn('text === "J"', panel)
        self.assertNotIn('text === "O"', panel)
        self.assertNotIn("J  JOIN", panel)
        self.assertNotIn("O  SOURCE", panel)
        help_dispatch = 'if (text === "?" && !root.showSetup)'
        self.assertIn(help_dispatch, panel)
        text_handler = panel[panel.index("onTextKey: function(text)"):]
        self.assertLess(text_handler.index(help_dispatch), text_handler.index("if (root.showSettings)"))

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
        self.assertEqual(
            week.count('onClicked: root.eventSelected(String(modelData.uid || ""), parent.eventDay)'),
            2,
        )
        self.assertNotIn("allDayColumn", week)

    def test_week_keyboard_selection_keeps_the_selected_event_in_view(self):
        week = self.text("WeekView.qml")
        self.assertIn("function revealSelectedEvent()", week)
        self.assertIn("onSelectedUidChanged: Qt.callLater(revealSelectedEvent)", week)
        self.assertIn("gridFlick.contentY", week)
        self.assertIn("selectedEvent.all_day", week)
        self.assertIn("gridFlick.contentHeight, Style.space(40))", week)

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

    def test_week_selection_strip_uses_compact_padding_and_remaining_height(self):
        week = self.text("WeekView.qml")
        self.assertIn('objectName: "weekDayHeader"', week)
        self.assertIn('objectName: "weekSelectionStrip"', week)
        self.assertIn("weekLayout.spacing * 3", week)
        self.assertIn("anchors.margins: Style.space(6)", week)
        self.assertIn("height: Style.space(38)", week)
        self.assertIn("height: Style.space(30)", week)
        self.assertIn('objectName: "weekSelectionInfo"', week)
        self.assertEqual(week.count("verticalAlignment: Text.AlignVCenter"), 5)

    def test_today_keyboard_selection_keeps_the_selected_event_in_view(self):
        today = self.text("TodayView.qml")
        self.assertIn("function revealSelectedEvent()", today)
        self.assertIn("onSelectedUidChanged: Qt.callLater(revealSelectedEvent)", today)
        self.assertIn("CalendarModel.revealOffset", today)

    def test_settings_use_clear_meaningful_appearance_choices(self):
        settings = self.text("SettingsView.qml")
        panel = self.text("Panel.qml")
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
        self.assertIn('import "CalendarModel.js" as CalendarModel', settings)
        self.assertIn("CalendarModel.updateStatus([modelData], new Date())", settings)
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
            "Connect", "Disconnect", "Confirm disconnect", "Confirm reset", "Read-only", "system keyring",
        ):
            self.assertIn(label, settings + setup)
        self.assertIn("TextInput", setup)
        self.assertNotIn("TextInput.Password", setup)

    def test_private_identity_setup_is_truthful_read_only_and_secret_free(self):
        panel = self.text("Panel.qml")
        settings = self.text("SettingsView.qml")
        setup = self.text("SetupView.qml")
        for label in (
            "Private setup is not one-click", "Choose Google Desktop JSON",
            "WHAT FLIGHT DECK REQUESTS", "Connect in browser", "No hosted backend",
        ):
            self.assertIn(label, setup)
        self.assertIn("import QtQuick.Dialogs", setup)
        self.assertIn("FileDialog", setup)
        self.assertIn("FileDialog.OpenFile", setup)
        self.assertIn("onAccepted: root.importRequested(String(selectedFile))", setup)
        self.assertIn("signal importRequested(string source)", setup)
        self.assertIn('onImportRequested: function(source) { root.importGoogleDesktop(source) }', panel)
        self.assertIn("setupSurface.activatePrimary()", panel)
        self.assertIn("setupSurface.clearDraft()", panel)
        self.assertIn("Flickable", setup)
        self.assertIn("contentHeight: content.implicitHeight + Style.space(44)", setup)
        self.assertIn("system keyring", setup)
        self.assertIn("personal-account capable", setup)
        self.assertIn("Calendar events read-only", setup)
        self.assertIn("Calendars.Read", setup)
        self.assertIn('visible: root.provider === "microsoft" && !root.providerState.client_configured', setup)
        self.assertIn("implicitHeight: content.implicitHeight + Style.space(44)", setup)
        self.assertIn("height: Math.min(parent.height - Style.space(50), setupSurface.implicitHeight)", panel)
        self.assertIn("Authenticate in your browser after private provider setup", settings)
        self.assertNotIn("Connect once in your browser", settings)
        self.assertNotIn("The public release will hide this step", setup)
        self.assertNotIn("clientSecret", setup)
        self.assertNotIn("Client secret", setup)

    def test_plugin_has_no_write_action_or_em_dash(self):
        executable = "\n".join(self.text(name) for name in (
            "BarWidget.qml", "Panel.qml", "CalendarModel.js", "SettingsModel.js",
            "TodayView.qml", "WeekView.qml", "SettingsView.qml", "SetupView.qml",
            "HelpOverlay.qml", "EventDetail.qml", "Service.qml",
        ))
        all_copy = executable
        for forbidden in ("Calendars.ReadWrite", "create-event", "update-event", "delete-event"):
            self.assertNotIn(forbidden, executable)
        self.assertNotIn("—", all_copy)

    def test_qml_child_objects_are_not_separated_by_semicolons(self):
        qml = "\n".join(self.text(path.name) for path in PLUGIN.glob("*.qml"))
        self.assertIsNone(re.search(r"}\s*;\s*(?:MouseArea|Text|Rectangle|Row|Column|Item)\s*{", qml))

    def test_help_cards_use_the_named_grid_for_spacing(self):
        help_overlay = self.text("HelpOverlay.qml")
        self.assertIn("id: helpGrid", help_overlay)
        self.assertIn("helpGrid.columnSpacing", help_overlay)
        self.assertNotIn("parent.columnSpacing", help_overlay)
        self.assertIn("height: Style.space(160)", help_overlay)
        self.assertIn('["Enter / Space", "Activate control"]', help_overlay)
        self.assertIn('["m", "Join meeting"]', help_overlay)
        self.assertIn("width: Style.space(82)", help_overlay)

    def test_panel_is_split_into_focused_release_components(self):
        panel = self.text("Panel.qml")
        self.assertLess(len(panel.splitlines()), 950)
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
        self.assertIn('if (text === "a") root.applySettings()', panel)
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


if __name__ == "__main__":
    unittest.main()
