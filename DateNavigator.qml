// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import qs.Commons
import "CalendarModel.js" as CalendarModel

Rectangle {
  id: root
  objectName: "dateNavigator"

  property string view: "today"
  property date cursorDate: new Date()
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property int motionDuration: 140

  signal previousRequested()
  signal nextRequested()
  signal nowRequested()

  function periodLabel() {
    if (view === "today") return Qt.formatDate(cursorDate, "dddd, MMMM d, yyyy")
    var start = CalendarModel.startOfWeek(cursorDate)
    var end = CalendarModel.addDays(start, 6)
    if (start.getFullYear() !== end.getFullYear())
      return Qt.formatDate(start, "MMM d, yyyy") + " to " + Qt.formatDate(end, "MMM d, yyyy")
    if (start.getMonth() !== end.getMonth())
      return Qt.formatDate(start, "MMM d") + " to " + Qt.formatDate(end, "MMM d, yyyy")
    return Qt.formatDate(start, "MMMM d") + " to " + Qt.formatDate(end, "d, yyyy")
  }

  color: root.palette.background
  border.color: root.palette.border
  border.width: 0

  Row {
    anchors.centerIn: parent
    spacing: Style.space(8)

    Rectangle {
      objectName: "previousPeriodButton"
      width: Style.space(38)
      height: Style.space(32)
      radius: Style.space(6)
      color: previousHover.hovered ? Qt.rgba(0.478, 0.635, 0.969, 0.18) : "transparent"
      border.color: root.palette.border
      border.width: 1
      Text { anchors.centerIn: parent; text: "‹"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.title * root.textScale; font.bold: true }
      HoverHandler { id: previousHover }
      MouseArea { anchors.fill: parent; onClicked: root.previousRequested() }
    }

    Text {
      width: Style.space(290)
      height: Style.space(32)
      text: root.periodLabel()
      color: root.palette.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall * root.textScale
      font.bold: true
      horizontalAlignment: Text.AlignHCenter
      verticalAlignment: Text.AlignVCenter
      elide: Text.ElideRight
    }

    Rectangle {
      objectName: "nextPeriodButton"
      width: Style.space(38)
      height: Style.space(32)
      radius: Style.space(6)
      color: nextHover.hovered ? Qt.rgba(0.478, 0.635, 0.969, 0.18) : "transparent"
      border.color: root.palette.border
      border.width: 1
      Text { anchors.centerIn: parent; text: "›"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.title * root.textScale; font.bold: true }
      HoverHandler { id: nextHover }
      MouseArea { anchors.fill: parent; onClicked: root.nextRequested() }
    }

    Rectangle {
      objectName: "nowButton"
      width: Style.space(84)
      height: Style.space(32)
      radius: Style.space(6)
      color: nowHover.hovered ? root.palette.accent : Qt.rgba(0.478, 0.635, 0.969, 0.14)
      border.color: root.palette.accent
      border.width: 1
      Behavior on color { enabled: root.motionDuration > 0; ColorAnimation { duration: root.motionDuration } }
      Text { anchors.centerIn: parent; text: "Now  g"; color: nowHover.hovered ? root.palette.background : root.palette.accent; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
      HoverHandler { id: nowHover }
      MouseArea { anchors.fill: parent; onClicked: root.nowRequested() }
    }
  }
}
