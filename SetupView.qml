// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Dialogs
import qs.Commons

Rectangle {
  id: root
  objectName: "setupState"

  property string provider: ""
  property var providerState: ({})
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property bool busy: false
  property string errorText: ""
  readonly property bool inputFocused: root.provider === "microsoft" && clientInput.activeFocus
  signal configureRequested(string provider, string clientId)
  signal importRequested(string source)
  signal authenticateRequested(string provider)
  signal cancelRequested()

  readonly property string providerName: provider === "microsoft" ? "Outlook.com" : "Google Calendar"
  readonly property string clientPlaceholder: "Application client ID (UUID)"

  color: root.palette.background
  radius: Style.space(10)
  border.color: root.palette.accent
  border.width: 1
  clip: true
  implicitHeight: content.implicitHeight + Style.space(44)

  function activatePrimary() {
    if (root.busy) return
    if (root.providerState.client_configured) root.authenticateRequested(root.provider)
    else if (root.provider === "google") googleCredentialsDialog.open()
    else if (clientInput.text.trim() !== "") root.configureRequested(root.provider, clientInput.text.trim())
  }
  function clearDraft() { clientInput.text = "" }

  FileDialog {
    id: googleCredentialsDialog
    title: "Choose Google Desktop credentials"
    fileMode: FileDialog.OpenFile
    nameFilters: ["Google Desktop credentials (*.json)", "JSON files (*.json)"]
    onAccepted: root.importRequested(String(selectedFile))
  }

  Flickable {
    id: setupScroll
    anchors.fill: parent
    contentWidth: width
    contentHeight: content.implicitHeight + Style.space(44)
    boundsBehavior: Flickable.StopAtBounds
    clip: true

    Column {
      id: content
      x: Style.space(22)
      y: Style.space(22)
      width: setupScroll.width - Style.space(44)
      spacing: Style.space(13)

    Row {
      width: parent.width
      height: Style.space(38)
      Text { textFormat: Text.PlainText; width: parent.width - Style.space(140); text: "CONNECT " + root.providerName.toUpperCase(); color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.title * root.textScale; font.bold: true; elide: Text.ElideRight }
      Rectangle {
        width: Style.space(132)
        height: Style.space(34)
        radius: Style.space(6)
        color: "transparent"
        border.color: root.palette.border
        border.width: 1
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          text: "Back to Settings"
          color: root.palette.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          font.bold: true
        }
        MouseArea { anchors.fill: parent; onClicked: root.cancelRequested() }
      }
    }

    Text {

      textFormat: Text.PlainText
      width: parent.width
      text: root.providerState.client_configured
        ? root.providerState.registration_source === "bundled"
          ? "Flight Deck's bundled registration is ready. Connect in the browser and return after granting read-only calendar access."
          : "Your local registration is ready. Connect in the browser and return after granting read-only calendar access."
        : root.provider === "google"
          ? "This build has no bundled Google registration. Contributors can import a Google Desktop credentials JSON file as an advanced override."
          : "This build has no bundled Microsoft registration. Contributors can enter a personal-account capable public application ID as an advanced override."
      color: root.palette.muted
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall * root.textScale
      wrapMode: Text.Wrap
    }

    Rectangle {
      width: parent.width
      height: Style.space(132)
      radius: Style.space(8)
      color: root.palette.surface
      border.color: root.palette.border
      border.width: 1

      Column {
        anchors.fill: parent
        anchors.margins: Style.space(14)
        spacing: Style.space(8)
        Text { textFormat: Text.PlainText; text: "WHAT FLIGHT DECK REQUESTS"; color: root.palette.accent; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true; font.letterSpacing: 0.8 }
        Text {
          textFormat: Text.PlainText
          width: parent.width
          text: root.provider === "microsoft"
            ? "Identity and profile so the account can be labeled\nCalendars.Read for events and calendar lists\nOffline access for automatic local refresh"
            : "Identity and email so the account can be labeled\nCalendar events read-only\nCalendar list read-only\nOffline access for automatic local refresh"
          color: root.palette.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall * root.textScale
          lineHeight: 1.35
          wrapMode: Text.Wrap
        }
      }
    }

    Rectangle {
      visible: root.provider === "microsoft" && !root.providerState.client_configured
      width: parent.width
      height: visible ? Style.space(112) : 0
      radius: Style.space(8)
      color: root.palette.surface
      border.color: clientInput.activeFocus ? root.palette.accent : root.palette.border
      border.width: clientInput.activeFocus ? 2 : 1

      Column {
        anchors.fill: parent
        anchors.margins: Style.space(12)
        spacing: Style.space(7)
        Text { textFormat: Text.PlainText; text: "MICROSOFT APPLICATION ID"; color: root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
        Rectangle {
          width: parent.width
          height: Style.space(44)
          radius: Style.space(6)
          color: Qt.rgba(1, 1, 1, 0.04)
          border.color: clientInput.activeFocus ? root.palette.accent : root.palette.border
          border.width: 1
          Text { textFormat: Text.PlainText; anchors.left: parent.left; anchors.leftMargin: Style.space(10); anchors.verticalCenter: parent.verticalCenter; visible: clientInput.text === ""; text: root.clientPlaceholder; color: root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; elide: Text.ElideRight; width: parent.width - Style.space(20) }
          TextInput {
            id: clientInput
            objectName: "publicClientInput"
            anchors.fill: parent
            anchors.leftMargin: Style.space(10)
            anchors.rightMargin: Style.space(10)
            verticalAlignment: TextInput.AlignVCenter
            color: root.palette.foreground
            selectionColor: root.palette.accent
            selectedTextColor: root.palette.background
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption * root.textScale
            maximumLength: 512
            clip: true
            selectByMouse: true
            enabled: !root.busy
            Keys.onPressed: function(event) {
              if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && text.trim() !== "") {
                root.configureRequested(root.provider, text.trim())
                event.accepted = true
              } else if (event.key === Qt.Key_Escape) {
                focus = false
                event.accepted = true
              }
            }
          }
        }
      }
    }

    Rectangle {
      width: parent.width
      height: Style.space(58)
      radius: Style.space(8)
      color: root.busy ? "transparent" : root.palette.accent
      border.color: root.palette.accent
      border.width: 1
      opacity: root.busy ? 0.65 : 1
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: root.busy ? "Working" : root.providerState.client_configured
          ? "Connect in browser" : root.provider === "google"
            ? "Choose Google Desktop JSON" : "Save ID and connect"
        color: root.busy ? root.palette.muted : root.palette.background
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall * root.textScale
        font.bold: true
      }
      MouseArea {
        anchors.fill: parent
        enabled: !root.busy && (root.providerState.client_configured || root.provider === "google" || clientInput.text.trim() !== "")
        onClicked: root.activatePrimary()
      }
    }

    Text {

      textFormat: Text.PlainText
      width: parent.width
      text: root.errorText
      color: root.palette.urgent
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption * root.textScale
      wrapMode: Text.Wrap
    }

    Text {

      textFormat: Text.PlainText
      width: parent.width
      text: root.provider === "google"
        ? root.providerState.registration_source === "bundled"
          ? "The bundled public Desktop app registration ships with Flight Deck. OAuth tokens stay in the system keyring. Calendar data stays in a private local SQLite cache. No hosted backend."
          : "Your imported Desktop app credential and tokens stay in the system keyring. Only the public client ID is saved in local settings. Calendar data stays in a private local SQLite cache. No hosted backend."
        : root.providerState.registration_source === "bundled"
          ? "The bundled public application ID ships with Flight Deck. Tokens stay in the system keyring. Calendar data stays in a private local SQLite cache. No hosted backend."
          : "Tokens stay in the system keyring. Your public application ID stays in local settings. Calendar data stays in a private local SQLite cache. No hosted backend."
      color: root.palette.muted
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption * root.textScale
      wrapMode: Text.Wrap
    }
  }
  }

  Rectangle {
    visible: setupScroll.contentHeight > setupScroll.height
    anchors.right: parent.right
    anchors.rightMargin: Style.space(5)
    width: Style.space(3)
    height: Math.max(Style.space(28), (root.height - Style.space(16)) * setupScroll.visibleArea.heightRatio)
    y: Style.space(8) + (root.height - Style.space(16)) * setupScroll.visibleArea.yPosition
    radius: width / 2
    color: root.palette.accent
    opacity: 0.72
  }
}
