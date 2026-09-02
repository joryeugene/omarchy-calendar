// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import qs.Commons
import "CalendarModel.js" as CalendarModel

Rectangle {
  id: root
  objectName: "settingsSurface"

  property var draft: ({})
  property var providers: []
  property var calendars: []
  property var palette: ({})
  property string fontFamily: Style.font.family
  property real textScale: 1
  property int sectionIndex: 0
  property int controlIndex: 0
  property bool pendingReset: false
  property string pendingDisconnect: ""
  property bool busy: false
  property string errorText: ""

  signal updateRequested(string key, var value)
  signal applyRequested()
  signal cancelRequested()
  signal setupRequested(string provider)
  signal disconnectRequested(string provider)
  signal resetRequested()

  readonly property var sections: ["Calendars", "Appearance", "Preferences", "About and Privacy"]
  readonly property var appearanceControls: [
    { key: "theme", label: "Theme", options: [
      { label: "Kinetic Tokyo Night", value: "kinetic-tokyo-night" },
      { label: "Follow Omarchy", value: "omarchy" },
      { label: "High Contrast", value: "high-contrast" }
    ]},
    { key: "density", label: "Density", description: "Compact shows more. Roomy is easier to scan.", options: [{ label: "Compact", value: "compact" }, { label: "Roomy", value: "roomy" }] },
    { key: "textScale", label: "Text scale", options: [{ label: "90%", value: 0.9 }, { label: "100%", value: 1 }, { label: "110%", value: 1.1 }, { label: "125%", value: 1.25 }] },
    { key: "animations", label: "Animations", description: "Short color transitions only.", options: [{ label: "On", value: true }, { label: "Off", value: false }] }
  ]
  readonly property var preferenceControls: [
    { key: "defaultView", label: "Default view", options: [{ label: "Today", value: "today" }, { label: "Week", value: "week" }] },
    { key: "weekStartHour", label: "Week starts", options: hourOptions(0, 22) },
    { key: "weekEndHour", label: "Week ends", options: hourOptions(2, 24) },
    { key: "timeFormat", label: "Time format", options: [{ label: "System", value: "system" }, { label: "12 hour", value: "12h" }, { label: "24 hour", value: "24h" }] },
    { key: "syncIntervalMinutes", label: "Sync interval", options: [{ label: "5 minutes", value: 5 }, { label: "15 minutes", value: 15 }, { label: "30 minutes", value: 30 }] }
  ]

  function hourOptions(first, last) {
    var result = []
    for (var hour = first; hour <= last; hour++)
      result.push({ label: String(hour).padStart(2, "0") + ":00", value: hour })
    return result
  }
  function activeControls() {
    if (sectionIndex === 1) return appearanceControls
    if (sectionIndex === 2) return preferenceControls
    return []
  }
  function providerAt(index) {
    return index >= 0 && index < providers.length ? providers[index] : null
  }
  function providerCount() { return providers.length }
  function calendarGroups() {
    var groups = []
    for (var i = 0; i < calendars.length; i++) {
      var calendar = calendars[i]
      var group = null
      for (var j = 0; j < groups.length; j++)
        if (groups[j].provider === calendar.provider) { group = groups[j]; break }
      if (!group) {
        group = { provider: calendar.provider, label: CalendarModel.providerLabel(calendar.provider), calendars: [] }
        groups.push(group)
      }
      group.calendars.push(calendar)
    }
    return groups
  }
  function bulkControlCount() { return calendarGroups().length * 2 }
  function calendarBaseIndex() { return providerCount() + bulkControlCount() }
  function resetControlIndex() { return calendarBaseIndex() + calendars.length }
  function groupControlIndex(provider, visible) {
    var groups = calendarGroups()
    for (var i = 0; i < groups.length; i++)
      if (groups[i].provider === provider)
        return providerCount() + i * 2 + (visible ? 0 : 1)
    return -1
  }
  function calendarControlIndex(key) {
    for (var i = 0; i < calendars.length; i++)
      if (String(calendars[i].key) === String(key)) return calendarBaseIndex() + i
    return -1
  }
  function isCalendarHidden(key) {
    return (draft.hiddenCalendars || []).indexOf(String(key)) !== -1
  }
  function toggleCalendar(key) {
    var target = String(key)
    var hidden = (draft.hiddenCalendars || []).slice()
    var index = hidden.indexOf(target)
    if (index === -1) hidden.push(target)
    else hidden.splice(index, 1)
    updateRequested("hiddenCalendars", hidden)
  }
  function setProviderVisible(provider, visible) {
    var hidden = (draft.hiddenCalendars || []).slice()
    for (var i = 0; i < calendars.length; i++) {
      if (calendars[i].provider !== provider) continue
      var key = String(calendars[i].key)
      var index = hidden.indexOf(key)
      if (visible && index !== -1) hidden.splice(index, 1)
      else if (!visible && index === -1) hidden.push(key)
    }
    updateRequested("hiddenCalendars", hidden)
  }
  function controlCount() {
    if (sectionIndex === 0) return resetControlIndex() + 1
    if (sectionIndex === 3) return 2
    return activeControls().length
  }
  function moveSection(amount) {
    sectionIndex = (sectionIndex + amount + sections.length) % sections.length
    controlIndex = 0
  }
  function moveControl(amount) {
    var count = Math.max(1, controlCount())
    controlIndex = (controlIndex + amount + count) % count
  }
  function revealSettingsItem(item) {
    if (!item || sectionIndex !== 0) return
    var point = item.mapToItem(calendarScroll.contentItem, 0, 0)
    calendarScroll.contentY = CalendarModel.revealOffset(
      calendarScroll.contentY, calendarScroll.height, point.y, item.height,
      calendarScroll.contentHeight, Style.space(10))
  }
  function selectedOption(control) {
    var value = draft[control.key]
    for (var i = 0; i < control.options.length; i++)
      if (control.options[i].value === value) return i
    return 0
  }
  function cycleControl(index, amount) {
    var controls = activeControls()
    if (index < 0 || index >= controls.length) return
    var control = controls[index]
    var current = selectedOption(control)
    var next = (current + amount + control.options.length) % control.options.length
    updateRequested(control.key, control.options[next].value)
  }
  function activateCurrent() {
    if (sectionIndex === 1 || sectionIndex === 2) {
      cycleControl(controlIndex, 1)
      return
    }
    if (sectionIndex === 0) {
      var provider = controlIndex < providerCount() ? providerAt(controlIndex) : null
      if (provider) {
        if (provider.connected) disconnectRequested(provider.provider)
        else setupRequested(provider.provider)
      } else if (controlIndex < calendarBaseIndex()) {
        var bulkOffset = controlIndex - providerCount()
        var group = calendarGroups()[Math.floor(bulkOffset / 2)]
        var show = bulkOffset % 2 === 0
        setProviderVisible(group.provider, show)
      } else if (controlIndex < resetControlIndex()) {
        toggleCalendar(calendars[controlIndex - calendarBaseIndex()].key)
      } else if (controlIndex === resetControlIndex()) resetRequested()
      return
    }
    if (sectionIndex === 3 && controlIndex === 1) resetRequested()
  }

  color: root.palette.background
  radius: Style.space(10)
  border.color: root.palette.border
  border.width: 1

  Row {
    anchors.fill: parent

    Rectangle {
      width: Style.space(224)
      height: parent.height
      color: root.palette.surface
      radius: root.radius

      Column {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Style.space(14)
        spacing: Style.space(8)

        Text {

          textFormat: Text.PlainText
          text: "SETTINGS"
          color: root.palette.accent
          font.family: root.fontFamily
          font.pixelSize: Style.font.title * root.textScale
          font.bold: true
          font.letterSpacing: 1
        }

        Item { width: 1; height: Style.space(5) }

        Repeater {
          model: root.sections
          Rectangle {
            required property string modelData
            required property int index
            width: parent.width
            height: Style.space(44)
            radius: Style.space(7)
            color: root.sectionIndex === index ? Qt.rgba(0.478, 0.635, 0.969, 0.18) : "transparent"
            border.color: root.sectionIndex === index ? root.palette.accent : "transparent"
            border.width: 1
            Text {
              textFormat: Text.PlainText
              anchors.left: parent.left
              anchors.leftMargin: Style.space(12)
              anchors.verticalCenter: parent.verticalCenter
              text: modelData
              color: root.sectionIndex === index ? root.palette.foreground : root.palette.muted
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall * root.textScale
              font.bold: root.sectionIndex === index
            }
            MouseArea { anchors.fill: parent; onClicked: { root.sectionIndex = index; root.controlIndex = 0 } }
          }
        }

      }

      Text {

        textFormat: Text.PlainText
        objectName: "settingsKeyboardHint"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Style.space(14)
        text: "h / l sections\nj / k controls\nEnter or Space change"
        color: root.palette.muted
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption * root.textScale
        lineHeight: 1.4
      }
    }

    Item {
      width: parent.width - Style.space(224)
      height: parent.height

      Column {
        anchors.fill: parent
        anchors.margins: Style.space(18)
        spacing: Style.space(12)

        Row {
          width: parent.width
          height: Style.space(36)
          Text {
            textFormat: Text.PlainText
            width: parent.width - Style.space(160)
            text: root.sections[root.sectionIndex]
            color: root.palette.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.title * root.textScale
            font.bold: true
          }
          Text {
            textFormat: Text.PlainText
            width: Style.space(160)
            text: root.busy ? "WORKING" : "Live preview"
            color: root.busy ? root.palette.accent : root.palette.muted
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption * root.textScale
            horizontalAlignment: Text.AlignRight
          }
        }

        Item {
          width: parent.width
          height: parent.height - Style.space(168)

          Flickable {
            id: calendarScroll
            visible: root.sectionIndex === 0
            anchors.fill: parent
            contentHeight: calendarContent.implicitHeight + Style.space(8)
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
              id: calendarContent
              width: parent.width
              spacing: Style.space(10)

            Text {

              textFormat: Text.PlainText
              width: parent.width
              text: "Authenticate in your browser when connecting. Tokens stay in the system keyring and events stay in the local cache."
              color: root.palette.muted
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall * root.textScale
              wrapMode: Text.Wrap
            }

            Repeater {
              model: root.providers
              Rectangle {
                id: providerCard
                required property var modelData
                required property int index
                property bool current: root.controlIndex === index
                width: parent.width
                height: Style.space(104)
                radius: Style.space(8)
                color: root.palette.surface
                border.color: current ? root.palette.accent : root.palette.border
                border.width: current ? 2 : 1
                onCurrentChanged: if (current) Qt.callLater(function() { root.revealSettingsItem(providerCard) })

                Column {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(14)
                  anchors.verticalCenter: parent.verticalCenter
                  width: parent.width - Style.space(190)
                  spacing: Style.space(5)
                  Text { textFormat: Text.PlainText; text: String(modelData.label || modelData.provider); color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.body * root.textScale; font.bold: true }
                  Text { textFormat: Text.PlainText; text: modelData.connected ? "Connected and read-only" : modelData.client_configured ? "Ready to connect" : "Local developer registration needed"; color: modelData.connected ? root.palette.positive : root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale }
                  Text { textFormat: Text.PlainText; width: parent.width; text: modelData.connected ? CalendarModel.updateStatus([modelData], new Date()) : "No live sync yet"; color: modelData.stale ? root.palette.urgent : root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; elide: Text.ElideRight }
                }

                Rectangle {
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(14)
                  anchors.verticalCenter: parent.verticalCenter
                  width: Style.space(146)
                  height: Style.space(38)
                  radius: Style.space(6)
                  color: modelData.connected && root.pendingDisconnect === modelData.provider
                    ? root.palette.urgent : modelData.connected ? "transparent" : root.palette.accent
                  border.color: modelData.connected ? root.palette.urgent : root.palette.accent
                  border.width: 1
                  Text {
                    textFormat: Text.PlainText
                    anchors.centerIn: parent
                    text: modelData.connected
                      ? root.pendingDisconnect === modelData.provider ? "Confirm disconnect" : "Disconnect"
                      : "Connect"
                    color: modelData.connected && root.pendingDisconnect !== modelData.provider
                      ? root.palette.urgent : root.palette.background
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption * root.textScale
                    font.bold: true
                  }
                  MouseArea { anchors.fill: parent; onClicked: modelData.connected ? root.disconnectRequested(modelData.provider) : root.setupRequested(modelData.provider) }
                }
              }
            }

            Column {
              id: calendarVisibilityList
              objectName: "calendarVisibilityList"
              width: parent.width
              spacing: Style.space(8)

              Text {

                textFormat: Text.PlainText
                text: "VISIBLE CALENDARS"
                color: root.palette.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption * root.textScale
                font.bold: true
                font.letterSpacing: 0.8
              }
              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Hidden calendars stay synchronized and can be shown again instantly. Only opaque local selectors are saved in appearance settings."
                color: root.palette.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption * root.textScale
                wrapMode: Text.Wrap
              }
              Text {
                textFormat: Text.PlainText
                visible: root.calendars.length === 0
                width: parent.width
                text: "Calendars appear here after their first event is cached."
                color: root.palette.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall * root.textScale
              }

              Repeater {
                model: root.calendarGroups()
                Column {
                  id: providerCalendarGroup
                  required property var modelData
                  width: calendarVisibilityList.width
                  spacing: Style.space(5)

                  Row {
                    width: parent.width
                    height: Style.space(30)
                    spacing: Style.space(8)
                    Text {
                      textFormat: Text.PlainText
                      width: parent.width - Style.space(172)
                      anchors.verticalCenter: parent.verticalCenter
                      text: String(providerCalendarGroup.modelData.label)
                      color: root.palette.foreground
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.bodySmall * root.textScale
                      font.bold: true
                    }
                    Rectangle {
                      id: showAllButton
                      property bool current: root.controlIndex === root.groupControlIndex(providerCalendarGroup.modelData.provider, true)
                      width: Style.space(76)
                      height: Style.space(28)
                      radius: Style.space(5)
                      color: current ? Qt.rgba(0.478, 0.635, 0.969, 0.18) : "transparent"
                      border.color: current ? root.palette.accent : root.palette.border
                      border.width: current ? 2 : 1
                      onCurrentChanged: if (current) Qt.callLater(function() { root.revealSettingsItem(showAllButton) })
                      Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "Show all"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale }
                      MouseArea { anchors.fill: parent; onClicked: { root.controlIndex = root.groupControlIndex(providerCalendarGroup.modelData.provider, true); root.setProviderVisible(providerCalendarGroup.modelData.provider, true) } }
                    }
                    Rectangle {
                      id: hideAllButton
                      property bool current: root.controlIndex === root.groupControlIndex(providerCalendarGroup.modelData.provider, false)
                      width: Style.space(76)
                      height: Style.space(28)
                      radius: Style.space(5)
                      color: current ? Qt.rgba(0.478, 0.635, 0.969, 0.18) : "transparent"
                      border.color: current ? root.palette.accent : root.palette.border
                      border.width: current ? 2 : 1
                      onCurrentChanged: if (current) Qt.callLater(function() { root.revealSettingsItem(hideAllButton) })
                      Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: "Hide all"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale }
                      MouseArea { anchors.fill: parent; onClicked: { root.controlIndex = root.groupControlIndex(providerCalendarGroup.modelData.provider, false); root.setProviderVisible(providerCalendarGroup.modelData.provider, false) } }
                    }
                  }

                  Repeater {
                    model: providerCalendarGroup.modelData.calendars
                    Rectangle {
                      id: calendarRow
                      required property var modelData
                      property bool current: root.controlIndex === root.calendarControlIndex(modelData.key)
                      width: providerCalendarGroup.width
                      height: Style.space(40)
                      radius: Style.space(6)
                      color: root.isCalendarHidden(modelData.key) ? "transparent" : root.palette.surface
                      border.color: current ? root.palette.accent : root.palette.border
                      border.width: current ? 2 : 1
                      onCurrentChanged: if (current) Qt.callLater(function() { root.revealSettingsItem(calendarRow) })

                      Rectangle {
                        anchors.left: parent.left
                        anchors.leftMargin: Style.space(10)
                        anchors.verticalCenter: parent.verticalCenter
                        width: Style.space(8)
                        height: Style.space(22)
                        radius: Style.space(3)
                        color: String(modelData.color || root.palette.accent)
                      }
                      Text {
                        textFormat: Text.PlainText
                        anchors.left: parent.left
                        anchors.leftMargin: Style.space(28)
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - Style.space(170)
                        text: String(modelData.name || "Unnamed calendar")
                        color: root.palette.foreground
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.bodySmall * root.textScale
                        font.bold: true
                        elide: Text.ElideRight
                      }
                      Text {
                        textFormat: Text.PlainText
                        anchors.right: visibilityToggle.left
                        anchors.rightMargin: Style.space(12)
                        anchors.verticalCenter: parent.verticalCenter
                        text: String(modelData.event_count || 0) + " cached"
                        color: root.palette.muted
                        font.family: root.fontFamily
                        font.pixelSize: Style.font.caption * root.textScale
                      }
                      Rectangle {
                        id: visibilityToggle
                        anchors.right: parent.right
                        anchors.rightMargin: Style.space(8)
                        anchors.verticalCenter: parent.verticalCenter
                        width: Style.space(66)
                        height: Style.space(26)
                        radius: Style.space(13)
                        color: root.isCalendarHidden(modelData.key) ? "transparent" : Qt.rgba(0.478, 0.635, 0.969, 0.18)
                        border.color: root.isCalendarHidden(modelData.key) ? root.palette.muted : root.palette.accent
                        border.width: 1
                        Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: root.isCalendarHidden(modelData.key) ? "Hidden" : "Shown"; color: root.isCalendarHidden(modelData.key) ? root.palette.muted : root.palette.accent; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
                      }
                      MouseArea { anchors.fill: parent; onClicked: root.toggleCalendar(modelData.key) }
                    }
                  }
                }
              }
            }

            Rectangle {
              id: resetCard
              property bool current: root.controlIndex === root.resetControlIndex()
              width: parent.width
              height: Style.space(64)
              radius: Style.space(8)
              color: "transparent"
              border.color: current ? root.palette.urgent : root.palette.border
              border.width: current ? 2 : 1
              onCurrentChanged: if (current) Qt.callLater(function() { root.revealSettingsItem(resetCard) })
              Text {
                textFormat: Text.PlainText
                anchors.left: parent.left
                anchors.leftMargin: Style.space(14)
                anchors.verticalCenter: parent.verticalCenter
                text: root.pendingReset ? "This removes tokens, provider overrides, and cached events." : "Reset all local calendar data"
                color: root.pendingReset ? root.palette.urgent : root.palette.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall * root.textScale
              }
              Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(132)
                height: Style.space(34)
                radius: Style.space(6)
                color: root.pendingReset ? root.palette.urgent : "transparent"
                border.color: root.palette.urgent
                border.width: 1
                Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: root.pendingReset ? "Confirm reset" : "Reset local data"; color: root.pendingReset ? root.palette.background : root.palette.urgent; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
                MouseArea { anchors.fill: parent; onClicked: root.resetRequested() }
              }
            }
            }
          }

          Column {
            visible: root.sectionIndex === 1 || root.sectionIndex === 2
            anchors.fill: parent
            spacing: Style.space(10)

            Repeater {
              model: root.activeControls()
              Rectangle {
                required property var modelData
                required property int index
                width: parent.width
                height: Style.space(70)
                radius: Style.space(8)
                color: root.palette.surface
                border.color: root.controlIndex === index ? root.palette.accent : root.palette.border
                border.width: root.controlIndex === index ? 2 : 1

                Column {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(14)
                  anchors.verticalCenter: parent.verticalCenter
                  width: parent.width - Style.space(330)
                  spacing: Style.space(2)
                  Text { textFormat: Text.PlainText; width: parent.width; text: String(modelData.label); color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall * root.textScale; font.bold: true; elide: Text.ElideRight }
                  Text { textFormat: Text.PlainText; width: parent.width; visible: Boolean(modelData.description); text: String(modelData.description || ""); color: root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; elide: Text.ElideRight }
                }
                Row {
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(12)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(8)
                  Text {
                    textFormat: Text.PlainText
                    width: Style.space(58)
                    height: parent.height
                    text: "Previous"
                    color: root.palette.muted
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption * root.textScale
                    verticalAlignment: Text.AlignVCenter
                    horizontalAlignment: Text.AlignRight
                    MouseArea { anchors.fill: parent; onClicked: root.cycleControl(index, -1) }
                  }
                  Rectangle {
                    width: Style.space(180)
                    height: Style.space(38)
                    radius: Style.space(6)
                    color: Qt.rgba(0.478, 0.635, 0.969, 0.12)
                    border.color: root.palette.accent
                    border.width: 1
                    Text { textFormat: Text.PlainText; anchors.centerIn: parent; text: String(modelData.options[root.selectedOption(modelData)].label); color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; font.bold: true }
                    MouseArea { anchors.fill: parent; onClicked: root.cycleControl(index, 1) }
                  }
                  Text {
                    textFormat: Text.PlainText
                    width: Style.space(34)
                    height: parent.height
                    text: "Next"
                    color: root.palette.muted
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption * root.textScale
                    verticalAlignment: Text.AlignVCenter
                    MouseArea { anchors.fill: parent; onClicked: root.cycleControl(index, 1) }
                  }
                }
              }
            }

            Rectangle {
              objectName: "densityPreview"
              width: parent.width
              height: Style.space(root.draft.density === "roomy" ? 96 : 72)
              visible: root.sectionIndex === 1
              radius: Style.space(8)
              color: "transparent"
              border.color: root.palette.border
              border.width: 1
              Text {
                textFormat: Text.PlainText
                anchors.left: parent.left
                anchors.leftMargin: Style.space(14)
                anchors.verticalCenter: parent.verticalCenter
                text: root.draft.density === "roomy" ? "Roomy preview" : "Compact preview"
                color: root.palette.muted
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption * root.textScale
                font.bold: true
              }
              Column {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(14)
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width * 0.52
                spacing: Style.space(root.draft.density === "roomy" ? 8 : 4)
                Repeater {
                  model: 2
                  Rectangle {
                    width: parent.width
                    height: Style.space(root.draft.density === "roomy" ? 30 : 22)
                    radius: Style.space(4)
                    color: Qt.rgba(0.478, 0.635, 0.969, 0.12)
                    border.color: root.palette.border
                    border.width: 1
                    Text { textFormat: Text.PlainText; anchors.left: parent.left; anchors.leftMargin: Style.space(8); anchors.verticalCenter: parent.verticalCenter; text: index === 0 ? "09:30  Design review" : "11:00  Focus block"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Math.max(9, Style.font.caption * root.textScale); elide: Text.ElideRight; width: parent.width - Style.space(16) }
                  }
                }
              }
            }

            Text {

              textFormat: Text.PlainText
              width: parent.width
              visible: root.sectionIndex === 2
              text: "Clock formats remain available as inline config keys: format, formatAlt, verticalFormat, and verticalFormatAlt."
              color: root.palette.muted
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption * root.textScale
              wrapMode: Text.Wrap
            }
          }

          Column {
            visible: root.sectionIndex === 3
            anchors.fill: parent
            spacing: Style.space(12)

            Rectangle {
              width: parent.width
              height: Style.space(190)
              radius: Style.space(8)
              color: root.palette.surface
              border.color: root.controlIndex === 0 ? root.palette.accent : root.palette.border
              border.width: root.controlIndex === 0 ? 2 : 1
              Column {
                anchors.fill: parent
                anchors.margins: Style.space(14)
                spacing: Style.space(8)
                Text { textFormat: Text.PlainText; text: "Flight Deck Calendar  1.0.0"; color: root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.body * root.textScale; font.bold: true }
                Text { textFormat: Text.PlainText; width: parent.width; text: "Flight Deck Calendar puts Google Calendar and Outlook in one read-only Omarchy panel. It has no hosted backend, telemetry, analytics, or AI."; color: root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall * root.textScale; wrapMode: Text.Wrap }
                Text { textFormat: Text.PlainText; width: parent.width; text: "Scopes\nGoogle: identity, calendar lists, and events read-only\nMicrosoft: identity, profile, and Calendars.Read\n\nStorage\nOAuth tokens: Secret Service keyring\nCalendar data: local SQLite cache"; color: root.palette.muted; font.family: root.fontFamily; font.pixelSize: Style.font.caption * root.textScale; lineHeight: 1.35; wrapMode: Text.Wrap }
              }
            }

            Rectangle {
              width: parent.width
              height: Style.space(66)
              radius: Style.space(8)
              color: root.pendingReset ? Qt.rgba(0.969, 0.463, 0.557, 0.16) : "transparent"
              border.color: root.controlIndex === 1 ? root.palette.urgent : root.palette.border
              border.width: root.controlIndex === 1 ? 2 : 1
              Text { textFormat: Text.PlainText; anchors.left: parent.left; anchors.leftMargin: Style.space(14); anchors.verticalCenter: parent.verticalCenter; text: root.pendingReset ? "Confirm reset to erase all calendar data" : "Reset local data"; color: root.pendingReset ? root.palette.urgent : root.palette.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.bodySmall * root.textScale; font.bold: true }
              Rectangle {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
                width: Style.space(132)
                height: Style.space(34)
                radius: Style.space(6)
                color: root.pendingReset ? root.palette.urgent : "transparent"
                border.color: root.palette.urgent
                border.width: 1
                Text {
                  textFormat: Text.PlainText
                  anchors.centerIn: parent
                  text: root.pendingReset ? "Confirm reset" : "Reset local data"
                  color: root.pendingReset ? root.palette.background : root.palette.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption * root.textScale
                  font.bold: true
                }
                MouseArea { anchors.fill: parent; onClicked: root.resetRequested() }
              }
            }
          }
        }

        Text {

          textFormat: Text.PlainText
          width: parent.width
          height: Style.space(18)
          text: root.errorText
          color: root.palette.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption * root.textScale
          elide: Text.ElideRight
        }

        Row {
          width: parent.width
          height: Style.space(42)
          spacing: Style.space(8)
          Item { width: parent.width - Style.space(264); height: 1 }
          Rectangle {
            width: Style.space(124)
            height: parent.height
            radius: Style.space(6)
            color: "transparent"
            border.color: root.palette.border
            border.width: 1
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "Cancel"
              color: root.palette.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption * root.textScale
              font.bold: true
            }
            MouseArea { anchors.fill: parent; onClicked: root.cancelRequested() }
          }
          Rectangle {
            width: Style.space(124)
            height: parent.height
            radius: Style.space(6)
            color: root.palette.accent
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "Apply"
              color: root.palette.background
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption * root.textScale
              font.bold: true
            }
            MouseArea { anchors.fill: parent; onClicked: root.applyRequested() }
          }
        }
      }
    }
  }
}
