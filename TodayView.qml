// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import qs.Commons
import "CalendarModel.js" as CalendarModel

Item {
  id: root
  objectName: "todayFocus"

  property date day: new Date()
  property var events: []
  property var selectedEvent: null
  property string selectedUid: ""
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property string density: "compact"
  property int motionDuration: 140
  property string providerStatus: ""
  property string actionError: ""
  signal eventSelected(string uid, date day)
  signal meetingRequested()
  signal sourceRequested()

  readonly property int rowHeight: Style.space(density === "roomy" ? 84 : 58)
  readonly property int rowSpacing: Style.space(density === "roomy" ? 12 : 6)

  function revealSelectedEvent() {
    if (!visible || !selectedUid) return
    var selectedIndex = -1
    for (var i = 0; i < events.length; i++) {
      if (String(events[i].uid || "") === selectedUid) {
        selectedIndex = i
        break
      }
    }
    if (selectedIndex < 0) return
    var itemY = selectedIndex * (rowHeight + rowSpacing)
    agenda.contentY = CalendarModel.revealOffset(
      agenda.contentY, agenda.height, itemY, rowHeight, agenda.contentHeight, Style.space(16))
  }

  onSelectedUidChanged: Qt.callLater(revealSelectedEvent)
  onVisibleChanged: if (visible) Qt.callLater(revealSelectedEvent)

  Row {
    anchors.fill: parent
    anchors.margins: Style.space(16)
    spacing: Style.space(14)

    Rectangle {
      width: parent.width * 0.57
      height: parent.height
      color: "transparent"
      border.color: root.palette.border || "#3b4261"
      border.width: 1
      radius: Style.space(10)

      Text {

        textFormat: Text.PlainText
        id: todayTitle
        anchors.left: parent.left
        anchors.leftMargin: Style.space(18)
        anchors.top: parent.top
        anchors.topMargin: Style.space(16)
        width: parent.width - Style.space(36)
        text: Qt.formatDate(root.day, "dddd, MMMM d")
        color: root.palette.foreground || "white"
        font.family: root.fontFamily
        font.pixelSize: Style.font.title * root.textScale
        font.bold: true
        elide: Text.ElideRight
      }

      Text {

        textFormat: Text.PlainText
        anchors.left: todayTitle.left
        anchors.top: todayTitle.bottom
        anchors.topMargin: Style.space(3)
        text: root.events.length === 1 ? "1 event" : String(root.events.length) + " events"
        color: root.palette.muted || "#9aa5ce"
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption * root.textScale
      }

      Flickable {
        id: agenda
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: todayTitle.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: Style.space(16)
        anchors.rightMargin: Style.space(10)
        anchors.topMargin: Style.space(30)
        anchors.bottomMargin: Style.space(10)
        contentHeight: agendaColumn.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
          id: agendaColumn
          width: agenda.width - Style.space(10)
          spacing: root.rowSpacing

          Repeater {
            model: root.events
            Rectangle {
              required property var modelData
              width: agendaColumn.width
              height: root.rowHeight
              radius: Style.space(7)
              color: root.selectedUid === String(modelData.uid || "")
                ? Qt.rgba(0.478, 0.635, 0.969, 0.20)
                : root.palette.surface || "#1f2335"
              border.color: root.selectedUid === String(modelData.uid || "")
                ? root.palette.accent : root.palette.border
              border.width: 1
              Behavior on color { enabled: root.motionDuration > 0; ColorAnimation { duration: root.motionDuration } }

              Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Style.space(4)
                radius: 2
                color: modelData.calendar_color || root.palette.accent
              }

              Text {

                textFormat: Text.PlainText
                anchors.left: parent.left
                anchors.leftMargin: Style.space(15)
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(76)
                text: CalendarModel.formatTime(modelData).split(" to ")[0]
                color: root.palette.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption * root.textScale
              }

              Column {
                anchors.left: parent.left
                anchors.leftMargin: Style.space(98)
                anchors.right: meetingLabel.left
                anchors.rightMargin: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.space(3)
                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: String(modelData.title || "Untitled event")
                  color: root.palette.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body * root.textScale
                  font.bold: true
                  elide: Text.ElideRight
                }
                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: String(modelData.calendar_name || "") + "  " + CalendarModel.providerLabel(modelData.provider)
                  color: root.palette.muted
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption * root.textScale
                  elide: Text.ElideRight
                }
              }

              Text {

                textFormat: Text.PlainText
                id: meetingLabel
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.meeting_url ? "m  Meeting" : ""
                color: root.palette.positive
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption * root.textScale
              }

              MouseArea {
                anchors.fill: parent
                onClicked: root.eventSelected(String(modelData.uid || ""), root.day)
              }
            }
          }

          Item { width: 1; height: Style.space(26) }
        }

        Rectangle {
          visible: agenda.contentHeight > agenda.height
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.bottom: parent.bottom
          width: Style.space(3)
          radius: width / 2
          color: Qt.rgba(1, 1, 1, 0.08)
          Rectangle {
            width: parent.width
            height: Math.max(Style.space(24), parent.height * agenda.height / agenda.contentHeight)
            y: agenda.contentHeight <= agenda.height ? 0
              : (parent.height - height) * agenda.contentY / (agenda.contentHeight - agenda.height)
            radius: width / 2
            color: root.palette.accent
          }
        }
      }
    }

    EventDetail {
      objectName: "eventDetail"
      width: parent.width * 0.43 - parent.spacing
      height: parent.height
      eventData: root.selectedEvent
      palette: root.palette
      fontFamily: root.fontFamily
      textScale: root.textScale
      providerStatus: root.providerStatus
      actionError: root.actionError
      motionDuration: root.motionDuration
      onMeetingRequested: root.meetingRequested()
      onSourceRequested: root.sourceRequested()
    }
  }
}
