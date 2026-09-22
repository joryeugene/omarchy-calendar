// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import "../.." as FlightDeck

TestCase {
    id: testCase
    name: "SettingsActions"
    width: 1080
    height: 720
    visible: true
    when: windowShown

    property var activated: []
    readonly property var colors: ({
        background: "#16161e", surface: "#1f2335", foreground: "#c0caf5",
        muted: "#9aa5ce", accent: "#7aa2f7", border: "#3b4261",
        positive: "#9ece6a", urgent: "#f7768e"
    })

    FlightDeck.SettingsView {
        id: settings
        anchors.fill: parent
        draft: ({ hiddenCalendars: [] })
        providers: [
            { provider: "google", label: "Google", connected: true, editing_account_ids: [] },
            { provider: "microsoft", label: "Outlook", connected: false, editing_account_ids: [] }
        ]
        providerHealth: [
            { provider: "google", account_id: "one", connected: true, stale: false },
            { provider: "google", account_id: "two", connected: true, stale: false }
        ]
        calendars: [
            { key: "one", provider: "google", account_id: "one", account_label: "one@example.com", name: "One" },
            { key: "two", provider: "google", account_id: "two", account_label: "two@example.com", name: "Two" }
        ]
        palette: testCase.colors
        onEnableEditingRequested: function(provider, accountId) { testCase.activated.push(["enable", provider, accountId]) }
        onDisconnectRequested: function(provider, accountId) { testCase.activated.push(["disconnect", provider, accountId]) }
        onSetupRequested: function(provider) { testCase.activated.push(["connect", provider, ""]) }
        onApplyRequested: testCase.activated.push(["apply", "", ""])
        onCancelRequested: testCase.activated.push(["cancel", "", ""])
    }

    function init() {
        activated = [];
        settings.sectionIndex = 0;
        settings.controlIndex = 0;
    }

    function test_read_only_accounts_have_separate_enable_and_disconnect_actions() {
        verify(typeof settings.focusAccountAction === "function");
        compare(settings.sections[0], "Accounts and Calendars");
        compare(settings.accountActionCount(), 6);
        settings.activateCurrent();
        compare(activated[0], ["enable", "google", "one"]);
        settings.moveControl(1);
        settings.activateCurrent();
        compare(activated[1], ["disconnect", "google", "one"]);
        settings.moveControl(1);
        settings.activateCurrent();
        compare(activated[2], ["enable", "google", "two"]);
    }

    function test_connected_provider_offers_add_account() {
        var index = settings.accountActionIndex("google", "", "add");
        verify(index >= 0);
        settings.controlIndex = index;
        settings.activateCurrent();
        compare(activated[0], ["connect", "google", ""]);
    }

    function test_focus_targets_the_exact_account_action_and_footer_is_navigable() {
        settings.focusAccountAction("google", "two", "enable");
        compare(settings.controlIndex, 2);
        settings.controlIndex = settings.footerBaseIndex();
        settings.activateCurrent();
        compare(activated[0][0], "cancel");
        settings.moveControl(1);
        settings.activateCurrent();
        compare(activated[1][0], "apply");
    }
}
