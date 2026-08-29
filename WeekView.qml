// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import qs.Commons
import "CalendarModel.js" as CalendarModel

Item {
  id: root
  objectName: "weekTimeGrid"

  property var events: []
  property var weekDays: []
  property date selectedDay: new Date()
  property string selectedUid: ""
  property var selectedEvent: null
  property date nowTime: new Date()
  property int startHour: 7
  property int endHour: 20
  property int hourHeight: Style.space(52)
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property int motionDuration: 140
  signal eventSelected(string uid, date day)

  readonly property int timeGutter: Style.space(58)
  readonly property int topPadding: Style.space(14)
  readonly property int gridHeight: (endHour - startHour) * hourHeight
  readonly property string overlapPosition: CalendarModel.overlapPosition(events, selectedDay, selectedUid)

  function allDayFor(day) {
    return CalendarModel.eventsForDay(events, day).filter(function(event) { return event.all_day })
  }
  function timedFor(day) {
    return CalendarModel.overlapColumns(
      CalendarModel.eventsForDay(events, day).filter(function(event) { return !event.all_day })
    )
  }
  function isCurrentWeek() {
    if (weekDays.length === 0) return false
    return CalendarModel.dayKey(CalendarModel.startOfWeek(weekDays[0])) ===
      CalendarModel.dayKey(CalendarModel.startOfWeek(nowTime))
  }
  function currentTimeY() {
    return topPadding + ((nowTime.getHours() + nowTime.getMinutes() / 60) - startHour) * hourHeight
  }
  function centerCurrentTime() {
    if (!visible || !isCurrentWeek()) return
    var target = Math.max(0, Math.min(gridFlick.contentHeight - gridFlick.height,
      currentTimeY() - gridFlick.height * 0.36))
    gridFlick.contentY = target
  }
  function revealSelectedEvent() {
    if (!visible || !selectedEvent || selectedEvent.all_day) return
    var eventY = topPadding + CalendarModel.timePosition(selectedEvent, hourHeight, startHour)
    var eventHeight = CalendarModel.durationHeight(selectedEvent, hourHeight)
    gridFlick.contentY = CalendarModel.revealOffset(
      gridFlick.contentY, gridFlick.height, eventY, eventHeight,
      gridFlick.contentHeight, Style.space(40))
  }
  function showNow() {
    centerCurrentTime()
    Qt.callLater(revealSelectedEvent)
  }

  onVisibleChanged: if (visible) Qt.callLater(centerCurrentTime)
  onSelectedUidChanged: Qt.callLater(revealSelectedEvent)
  Component.onCompleted: Qt.callLater(centerCurrentTime)

  Column {
    id: weekLayout
    anchors.fill: parent
    anchors.margins: Style.space(6)
    spacing: Style.space(5)

    Row {
      id: weekHeader
      objectName: "weekDayHeader"
      width: parent.width
      height: Style.space(38)
      Item { width: root.timeGutter; height: 1 }
      Repeater {
        model: 7
        Rectangle {
          required property int index
          width: (weekLayout.width - root.timeGutter) / 7
          height: parent.height
          radius: Style.space(6)
          property date day: root.weekDays[index] || new Date()
          property bool selected: CalendarModel.dayKey(day) === CalendarModel.dayKey(root.selectedDay)
          property bool today: CalendarModel.dayKey(day) === CalendarModel.dayKey(root.nowTime)
          color: selected ? Qt.rgba(0.478, 0.635, 0.969, 0.22)
            : today ? Qt.rgba(0.478, 0.635, 0.969, 0.09) : "transparent"
          border.color: selected ? root.palette.accent : "transparent"
          border.width: 1
          Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: Qt.formatDate(parent.day, "ddd  d")
            color: parent.selected || parent.today ? root.palette.accent : root.palette.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall * root.textScale
            font.bold: parent.selected || parent.today
          }
        }
      }
    }

    Row {
      id: allDayLane
      objectName: "allDayLane"
      width: parent.width
      height: Style.space(52)
      Item {
        width: root.timeGutter
        height: parent.height
        Text {
          textFormat: Text.PlainText
          anchors.right: parent.right
          anchors.rightMargin: Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          text: "ALL DAY"
          color: root.palette.muted
          font.family: root.fontFamily
          font.pixelSize: Math.max(9, Style.font.caption * root.textScale)
        }
      }
      Repeater {
        model: 7
        Rectangle {
          required property int index
          property date day: root.weekDays[index] || new Date()
          property var dayEvents: root.allDayFor(day)
          width: (weekLayout.width - root.timeGutter) / 7
          height: parent.height
          color: "transparent"
          border.color: root.palette.border
          border.width: 1
          clip: true
          Column {
            anchors.fill: parent
            anchors.margins: Style.space(3)
            spacing: Style.space(2)
            Repeater {
              model: parent.parent.dayEvents.slice(0, 2)
              Rectangle {
                required property var modelData
                property date eventDay: CalendarModel.eventDay(modelData)
                width: parent.width
                height: Style.space(20)
                radius: Style.space(4)
                color: root.selectedUid === String(modelData.uid || "")
                  ? Qt.rgba(0.478, 0.635, 0.969, 0.34)
                  : Qt.rgba(0.478, 0.635, 0.969, 0.16)
                border.color: root.selectedUid === String(modelData.uid || "")
                  ? root.palette.accent : modelData.calendar_color || root.palette.border
                border.width: 1
                Text {
                  textFormat: Text.PlainText
                  anchors.fill: parent
                  anchors.leftMargin: Style.space(4)
                  anchors.rightMargin: Style.space(4)
                  text: String(modelData.title || "Untitled event")
                  verticalAlignment: Text.AlignVCenter
                  color: root.palette.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Math.max(9, Style.font.caption * root.textScale)
                  elide: Text.ElideRight
                }
                MouseArea {
                  anchors.fill: parent
                  onClicked: root.eventSelected(String(modelData.uid || ""), parent.eventDay)
                }
              }
            }
          }
        }
      }
    }

    Flickable {
      id: gridFlick
      width: parent.width
      height: Math.max(Style.space(120), parent.height - weekHeader.height
        - allDayLane.height - selectionStrip.height - weekLayout.spacing * 3)
      contentHeight: root.gridHeight + root.topPadding * 2
      clip: true
      boundsBehavior: Flickable.StopAtBounds

      Row {
        width: gridFlick.width
        height: gridFlick.contentHeight

        Item {
          width: root.timeGutter
          height: parent.height
          Repeater {
            model: root.endHour - root.startHour + 1
            Text {
              textFormat: Text.PlainText
              required property int index
              y: root.topPadding + index * root.hourHeight - height / 2
              width: parent.width - Style.space(8)
              text: String(root.startHour + index).padStart(2, "0") + ":00"
              horizontalAlignment: Text.AlignRight
              color: root.palette.muted
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption * root.textScale
            }
          }
        }

        Repeater {
          model: 7
          Rectangle {
            id: timedColumn
            required property int index
            property date day: root.weekDays[index] || new Date()
            property var timedEvents: root.timedFor(day)
            width: (weekLayout.width - root.timeGutter) / 7
            height: gridFlick.contentHeight
            color: CalendarModel.dayKey(day) === CalendarModel.dayKey(root.selectedDay)
              ? Qt.rgba(0.478, 0.635, 0.969, 0.05) : "transparent"
            border.color: root.palette.border
            border.width: 1

            Repeater {
              model: root.endHour - root.startHour + 1
              Rectangle {
                required property int index
                y: root.topPadding + index * root.hourHeight
                width: parent.width
                height: 1
                color: root.palette.border
                opacity: 0.72
              }
            }

            Repeater {
              model: timedColumn.timedEvents
              Rectangle {
                required property var modelData
                property date eventDay: CalendarModel.eventDay(modelData)
                property real available: timedColumn.width - Style.space(8)
                x: Style.space(4) + modelData.column * available / modelData.columns
                y: root.topPadding + CalendarModel.timePosition(modelData, root.hourHeight, root.startHour)
                width: Math.max(Style.space(18), available / modelData.columns - Style.space(3))
                height: Math.max(Style.space(24), CalendarModel.durationHeight(modelData, root.hourHeight))
                radius: Style.space(5)
                color: root.selectedUid === String(modelData.uid || "")
                  ? Qt.rgba(0.478, 0.635, 0.969, 0.34)
                  : Qt.rgba(0.478, 0.635, 0.969, 0.16)
                border.color: root.selectedUid === String(modelData.uid || "")
                  ? root.palette.accent : modelData.calendar_color || root.palette.border
                border.width: 1
                clip: true
                Behavior on color { enabled: root.motionDuration > 0; ColorAnimation { duration: root.motionDuration } }

                Column {
                  anchors.fill: parent
                  anchors.margins: Style.space(5)
                  spacing: 1
                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    text: String(modelData.title || "Untitled event")
                    color: root.palette.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption * root.textScale
                    font.bold: true
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                  }
                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    visible: parent.parent.height >= Style.space(44)
                    text: CalendarModel.formatTime(modelData).split(" to ")[0]
                    color: root.palette.muted
                    font.family: root.fontFamily
                    font.pixelSize: Math.max(9, Style.font.caption * root.textScale)
                    elide: Text.ElideRight
                  }
                }
                MouseArea {
                  anchors.fill: parent
                  onClicked: root.eventSelected(String(modelData.uid || ""), parent.eventDay)
                }
              }
            }

            Rectangle {
              objectName: "currentTimeLine"
              visible: root.isCurrentWeek()
                && CalendarModel.dayKey(timedColumn.day) === CalendarModel.dayKey(root.nowTime)
                && root.currentTimeY() >= root.topPadding
                && root.currentTimeY() <= root.gridHeight + root.topPadding
              x: 0
              y: root.currentTimeY()
              width: parent.width
              height: 2
              color: root.palette.urgent
              z: 10
            }
          }
        }
      }

      Rectangle {
        visible: gridFlick.contentHeight > gridFlick.height
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Style.space(3)
        color: Qt.rgba(1, 1, 1, 0.08)
        Rectangle {
          width: parent.width
          height: Math.max(Style.space(28), parent.height * gridFlick.height / gridFlick.contentHeight)
          y: (parent.height - height) * gridFlick.contentY / (gridFlick.contentHeight - gridFlick.height)
          color: root.palette.accent
        }
      }
    }

    Rectangle {
      id: selectionStrip
      objectName: "weekSelectionStrip"
      width: parent.width
      height: Style.space(30)
      radius: Style.space(7)
      color: root.palette.surface
      border.color: root.palette.border
      Row {
        objectName: "weekSelectionInfo"
        anchors.fill: parent
        anchors.margins: Style.space(4)
        spacing: Style.space(8)
        Text {
          textFormat: Text.PlainText
          width: parent.width * 0.2
          height: parent.height
          text: root.selectedEvent ? CalendarModel.formatTime(root.selectedEvent) : "No selection"
          color: root.palette.accent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          font.bold: true
          verticalAlignment: Text.AlignVCenter
          elide: Text.ElideRight
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width * (root.overlapPosition ? 0.34 : 0.5)
          height: parent.height
          text: root.selectedEvent ? String(root.selectedEvent.title || "Untitled event") : "Use j and k to select"
          color: root.palette.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall * root.textScale
          font.bold: true
          verticalAlignment: Text.AlignVCenter
          elide: Text.ElideRight
        }
        Text {
          textFormat: Text.PlainText
          visible: Boolean(root.overlapPosition)
          width: visible ? parent.width * 0.16 : 0
          height: parent.height
          text: root.overlapPosition ? "Overlap " + root.overlapPosition : ""
          color: root.palette.accent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          font.bold: true
          horizontalAlignment: Text.AlignHCenter
          verticalAlignment: Text.AlignVCenter
          elide: Text.ElideRight
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width * 0.25
          height: parent.height
          text: root.selectedEvent && root.selectedEvent.meeting_url ? "m Meeting   o Source" : "o Source"
          color: root.selectedEvent && root.selectedEvent.meeting_url ? root.palette.positive : root.palette.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          horizontalAlignment: Text.AlignRight
          verticalAlignment: Text.AlignVCenter
          elide: Text.ElideRight
        }
      }
    }
  }
}
