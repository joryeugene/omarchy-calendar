// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "CalendarModel.js" as CalendarModel
import "SettingsModel.js" as SettingsModel

BarWidget {
  id: root
  moduleName: "io.github.joryeugene.omarchy-calendar"

  property date displayDate: clock.date
  readonly property var canonicalSettings: canonicalEntry()
  readonly property var normalizedSettings: SettingsModel.normalize(canonicalSettings)
  readonly property string configuredFormat: vertical
    ? normalizedSettings.verticalFormat : normalizedSettings.format
  readonly property string configuredAltFormat: vertical
    ? normalizedSettings.verticalFormatAlt : normalizedSettings.formatAlt
  readonly property var formatRing: CalendarModel.clockFormatRing(configuredFormat, configuredAltFormat)
  readonly property string displayText: Qt.formatDateTime(displayDate, configuredFormat)
  readonly property var verticalLines: displayText.split("\n")
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  readonly property var calendarService: bar && bar.shell ? bar.shell.serviceFor(root.moduleName) : null
  readonly property real openPanelIndicatorWidth: button.labelWidth
  readonly property real openPanelIndicatorHeight: Math.max(Style.space(10), Math.round(Style.bar.iconSlot * 0.55))

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function toggle() { if (panelLoader.item) panelLoader.item.toggle() }
  function refresh() {
    displayDate = new Date()
    if (panelLoader.item) panelLoader.item.refresh()
  }
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }

  function canonicalEntry() {
    var config = root.bar && root.bar.shell ? root.bar.shell.shellConfig : null
    var layout = config && config.bar ? config.bar.layout : null
    var sections = ["left", "center", "right"]
    for (var i = 0; layout && i < sections.length; i++) {
      var entries = layout[sections[i]] || []
      for (var j = 0; j < entries.length; j++)
        if (entries[j] && entries[j].id === root.moduleName) return entries[j]
    }
    return root.settings || ({})
  }

  function cycleFormat() {
    var next = CalendarModel.nextClockFormat(formatRing, configuredFormat)
    if (!next || next === configuredFormat) return
    var entry = { id: root.moduleName }
    for (var key in root.canonicalSettings)
      if (key !== "id") entry[key] = root.canonicalSettings[key]
    entry[vertical ? "verticalFormat" : "format"] = next
    root.settings = entry
    if (root.bar && root.bar.shell && root.bar.shell.updateEntryInline)
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.canonicalSettings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
    if ("calendarService" in target) target.calendarService = root.calendarService
    if (root.calendarService)
      root.calendarService.syncIntervalMinutes = root.normalizedSettings.syncIntervalMinutes
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()
  onCanonicalSettingsChanged: injectPanel()

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
    onDateChanged: root.displayDate = date
  }

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? "" : root.displayText
    labelVisible: !root.vertical
    hasVisualContent: root.vertical ? root.verticalLines.length > 0 : text !== ""
    fixedHeight: root.vertical ? root.verticalLines.length * Style.bar.iconSlot : -1
    horizontalMargin: 8.75
    verticalPadding: 8.75
    tooltipText: "Open calendar"

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton) root.cycleFormat()
      else if (mouseButton === Qt.MiddleButton && root.bar) root.bar.run("omarchy-menu-timezone")
      else root.toggle()
    }

    Column {
      visible: root.vertical
      anchors.fill: parent
      Repeater {
        model: root.verticalLines
        OpticalGlyph {
          required property string modelData
          width: button.width
          height: Style.bar.iconSlot
          text: modelData
          fontFamily: button.fontFamily
          fontSize: modelData.length > 3 ? button.fontSize * 0.9 : button.fontSize
          color: button.foreground
        }
      }
    }
  }
}
