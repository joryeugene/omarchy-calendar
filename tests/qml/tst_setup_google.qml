// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtTest
import QtQuick.Dialogs
import "../.." as FlightDeck

TestCase {
    id: testCase
    name: "SetupGoogle"
    width: 900
    height: 700
    visible: true
    when: windowShown

    property var events: []
    readonly property var colors: ({
        background: "#16161e", surface: "#1f2335", foreground: "#c0caf5",
        muted: "#9aa5ce", accent: "#7aa2f7", border: "#3b4261",
        positive: "#9ece6a", urgent: "#f7768e"
    })

    FlightDeck.SetupView {
        id: setup
        anchors.fill: parent
        provider: "google"
        providerState: ({ client_configured: true, registration_source: "bundled" })
        palette: testCase.colors
        onAuthenticateRequested: function (provider, access) { testCase.events.push(["auth", provider, access]) }
        onImportRequested: function (source) { testCase.events.push(["import", source]) }
        onConfigureRequested: function (provider, clientId) { testCase.events.push(["configure", provider, clientId]) }
    }

    function init() {
        events = [];
        setup.accessChoice = "read";
    }

    function test_bundled_google_primary_action_authenticates_in_browser() {
        verify(typeof setup.activatePrimary === "function");
        setup.activatePrimary();
        compare(events.length, 1);
        compare(events[0], ["auth", "google", "read"]);
    }

    function test_edit_choice_is_forwarded_to_browser_auth() {
        setup.accessChoice = "edit";
        setup.activatePrimary();
        compare(events[0], ["auth", "google", "edit"]);
    }

    function test_google_still_authenticates_in_browser_without_a_local_bundle() {
        setup.providerState = ({ client_configured: false, registration_source: "" });
        setup.activatePrimary();
        compare(events.length, 1);
        compare(events[0], ["auth", "google", "read"]);
    }

    function test_google_keeps_the_json_import_control() {
        var control = findChild(setup, "googleJsonImport");
        verify(control !== null);
        verify(control.visible);
        var dialog = findChild(setup, "googleCredentialsDialog");
        verify(dialog !== null);
        compare(dialog.fileMode, FileDialog.OpenFile);
    }
}