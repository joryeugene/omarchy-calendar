// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import qs.Commons
import "CalendarModel.js" as CalendarModel

Rectangle {
  id: root

  property var eventData: null
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property string providerStatus: ""
  property string actionError: ""
  property int motionDuration: 140
  signal meetingRequested()
  signal sourceRequested()

  readonly property bool hasMeeting: !!(eventData && eventData.meeting_url)
  readonly property bool hasSource: !!(eventData && eventData.provider_url)
  readonly property var metadataRows: [
    { label: "Calendar", value: eventData ? String(eventData.calendar_name || "Unknown") : "None selected" },
    { label: "Provider", value: eventData ? CalendarModel.providerLabel(eventData.provider) : "None selected" },
    { label: "Account", value: eventData ? String(eventData.account_label || "Local account") : "None selected" },
    { label: "Sync", value: providerStatus || (eventData ? "Local cache" : "Not available") }
  ]

  color: palette.surface || "#1f2335"
  radius: Style.space(10)
  border.color: palette.border || "#3b4261"
  border.width: 1

  Column {
    id: header
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.margins: Style.space(18)
    spacing: Style.space(7)

    Text {
      width: parent.width
      text: root.eventData ? String(root.eventData.title || "Untitled event") : "Select an event"
      color: root.palette.foreground || "white"
      font.family: root.fontFamily
      font.pixelSize: Style.font.title * root.textScale
      font.bold: true
      wrapMode: Text.Wrap
      maximumLineCount: 2
      elide: Text.ElideRight
    }

    Text {
      width: parent.width
      text: root.eventData
        ? CalendarModel.formatTime(root.eventData)
        : "Use j and k to move through the agenda."
      color: root.palette.accent || "#7aa2f7"
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall * root.textScale
      wrapMode: Text.Wrap
    }

    Text {
      width: parent.width
      visible: !!(root.eventData && root.eventData.location)
      text: root.eventData ? String(root.eventData.location) : ""
      color: root.palette.positive || "#9ece6a"
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption * root.textScale
      font.bold: true
      elide: Text.ElideRight
    }
  }

  Rectangle {
    id: divider
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.leftMargin: Style.space(18)
    anchors.rightMargin: Style.space(18)
    anchors.top: header.bottom
    anchors.topMargin: Style.space(12)
    height: 1
    color: root.palette.border || "#3b4261"
  }

  Row {
    id: actionRow
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.margins: Style.space(18)
    height: Style.space(42)
    spacing: Style.space(8)

    Rectangle {
      width: (parent.width - parent.spacing) / 2
      height: parent.height
      radius: Style.space(6)
      color: root.hasMeeting ? root.palette.accent : "transparent"
      border.color: root.hasMeeting ? root.palette.accent : root.palette.border
      opacity: root.hasMeeting ? 1 : 0.72
      Behavior on color { enabled: root.motionDuration > 0; ColorAnimation { duration: root.motionDuration } }
      Text {
        anchors.centerIn: parent
        text: root.hasMeeting ? "m  Join meeting" : "No meeting link"
        color: root.hasMeeting ? root.palette.background : root.palette.muted
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption * root.textScale
        font.bold: true
      }
      MouseArea { anchors.fill: parent; enabled: root.hasMeeting; onClicked: root.meetingRequested() }
    }

    Rectangle {
      width: (parent.width - parent.spacing) / 2
      height: parent.height
      radius: Style.space(6)
      color: "transparent"
      border.color: root.hasSource ? root.palette.accent : root.palette.border
      opacity: root.hasSource ? 1 : 0.72
      Text {
        anchors.centerIn: parent
        text: root.hasSource ? "o  Source" : "No source link"
        color: root.hasSource ? root.palette.foreground : root.palette.muted
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption * root.textScale
        font.bold: true
      }
      MouseArea { anchors.fill: parent; enabled: root.hasSource; onClicked: root.sourceRequested() }
    }
  }

  Rectangle {
    id: metadataCard
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: actionRow.top
    anchors.leftMargin: Style.space(18)
    anchors.rightMargin: Style.space(18)
    anchors.bottomMargin: Style.space(12)
    height: Style.space(146) + Math.max(0, root.textScale - 1) * Style.space(40)
    radius: Style.space(7)
    color: Qt.rgba(1, 1, 1, 0.025)
    border.color: root.palette.border
    border.width: 1

    Column {
      anchors.fill: parent
      anchors.margins: Style.space(12)
      spacing: Style.space(6)

      Text {
        text: "CONNECTION"
        color: root.palette.accent
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption * root.textScale
        font.bold: true
        font.letterSpacing: 0.8
      }

      Repeater {
        model: root.metadataRows
        Row {
          required property var modelData
          width: parent.width
          height: Style.space(20) * root.textScale
          Text {
            width: Style.space(78)
            text: modelData.label
            color: root.palette.muted
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption * root.textScale
          }
          Text {
            width: parent.width - Style.space(78)
            text: modelData.value
            color: root.palette.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption * root.textScale
            elide: Text.ElideRight
          }
        }
      }
    }
  }

  Rectangle {
    id: descriptionCard
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: divider.bottom
    anchors.bottom: metadataCard.top
    anchors.leftMargin: Style.space(18)
    anchors.rightMargin: Style.space(18)
    anchors.topMargin: Style.space(12)
    anchors.bottomMargin: Style.space(12)
    radius: Style.space(7)
    color: Qt.rgba(1, 1, 1, 0.018)
    border.color: root.palette.border
    border.width: 1

    Text {
      id: detailLabel
      anchors.left: parent.left
      anchors.top: parent.top
      anchors.margins: Style.space(12)
      text: "EVENT DETAILS"
      color: root.palette.accent
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption * root.textScale
      font.bold: true
      font.letterSpacing: 0.8
    }

    Flickable {
      id: detailScroll
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: detailLabel.bottom
      anchors.bottom: parent.bottom
      anchors.leftMargin: Style.space(12)
      anchors.rightMargin: Style.space(9)
      anchors.topMargin: Style.space(9)
      anchors.bottomMargin: Style.space(10)
      contentHeight: detailColumn.implicitHeight + Style.space(8)
      clip: true
      boundsBehavior: Flickable.StopAtBounds

      Column {
        id: detailColumn
        width: detailScroll.width - Style.space(8)
        spacing: Style.space(10)

        Text {
          width: parent.width
          text: root.eventData && root.eventData.description
            ? String(root.eventData.description)
            : root.eventData ? "No description was provided." : "Select an event to see its details."
          color: root.eventData && root.eventData.description
            ? root.palette.foreground : root.palette.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall * root.textScale
          lineHeight: 1.35
          wrapMode: Text.Wrap
        }

        Text {
          width: parent.width
          visible: root.actionError !== ""
          text: root.actionError
          color: root.palette.urgent || "#f7768e"
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          wrapMode: Text.Wrap
        }
      }

      Rectangle {
        visible: detailScroll.contentHeight > detailScroll.height
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Style.space(3)
        radius: width / 2
        color: Qt.rgba(1, 1, 1, 0.08)
        Rectangle {
          width: parent.width
          height: Math.max(Style.space(24), parent.height * detailScroll.height / detailScroll.contentHeight)
          y: detailScroll.contentHeight <= detailScroll.height ? 0
            : (parent.height - height) * detailScroll.contentY / (detailScroll.contentHeight - detailScroll.height)
          radius: width / 2
          color: root.palette.accent
        }
      }
    }
  }
}
