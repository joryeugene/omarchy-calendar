// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  property var shell: null
  property var manifest: null
  readonly property string helperPath: manifest && manifest.__sourceDir
    ? String(manifest.__sourceDir) + "/calendarctl" : ""
  property bool syncing: false
  property int revision: 0
  property string lastError: ""
  property int syncIntervalMinutes: 5

  function requestSync() {
    if (syncing || helperPath === "") return false
    syncing = true
    lastError = ""
    syncProcess.command = [root.helperPath, "sync"]
    syncProcess.running = true
    return true
  }

  Timer {
    interval: root.syncIntervalMinutes * 60000
    repeat: true
    running: root.helperPath !== ""
    triggeredOnStart: true
    onTriggered: root.requestSync()
  }

  IpcHandler {
    target: "io.github.joryeugene.omarchy-calendar"
    function refresh(): string { return root.requestSync() ? "ok" : "busy" }
  }

  Process {
    id: syncProcess
    running: false
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { id: syncError; waitForEnd: true }
    onExited: function(exitCode) {
      root.syncing = false
      root.lastError = exitCode === 0 ? "" : String(syncError.text || "Calendar refresh failed").trim()
      root.revision += 1
    }
  }
}
