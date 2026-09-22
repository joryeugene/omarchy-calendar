// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  property var shell: null
  property var manifest: null
  // The host hands third-party plugins a sanitized manifest with no
  // __sourceDir, so resolve the bundled helper from this component's own
  // location instead of trusting the injected manifest.
  readonly property string helperPath: {
    var url = String(Qt.resolvedUrl("calendarctl"));
    if (url.indexOf("file://") === 0)
      url = decodeURIComponent(url.slice(7));
    return url;
  }
  property bool syncing: false
  property bool syncQueued: false
  property int revision: 0
  property string lastError: ""
  property int syncIntervalMinutes: 5

  function requestSync() {
    if (helperPath === "") return false
    if (syncing) {
      syncQueued = true
      return true
    }
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
      if (root.syncQueued) {
        root.syncQueued = false
        root.requestSync()
      }
    }
  }
}
