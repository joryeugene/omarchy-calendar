# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


@unittest.skipUnless(shutil.which("quickshell"), "quickshell is not installed")
class ServiceSyncQueueTests(unittest.TestCase):
    def test_requests_while_syncing_coalesce_into_one_follow_up_process(self):
        with tempfile.TemporaryDirectory() as directory:
            test_dir = Path(directory)
            (test_dir / "Service.qml").symlink_to(ROOT / "Service.qml")
            helper = test_dir / "calendarctl"
            helper.write_text(
                textwrap.dedent(
                    f"""\
                    #!/usr/bin/env python3
                    import fcntl
                    import os
                    import time
                    from pathlib import Path

                    log = Path({str(test_dir / 'runs.log')!r})
                    with Path({str(test_dir / 'sync.lock')!r}).open("w") as lock:
                        try:
                            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            with log.open("a") as output:
                                output.write("OVERLAP\\n")
                            raise SystemExit(2)
                        with log.open("a") as output:
                            output.write(f"START {{os.getpid()}}\\n")
                        time.sleep(0.2)
                        with log.open("a") as output:
                            output.write(f"END {{os.getpid()}}\\n")
                    """
                ),
                encoding="utf-8",
            )
            helper.chmod(0o755)
            (test_dir / "shell.qml").write_text(
                textwrap.dedent(
                    f"""\
                    import QtQuick
                    import Quickshell

                    ShellRoot {{
                      property bool queued: false

                      Service {{
                        id: service
                        syncIntervalMinutes: 60
                      }}

                      Timer {{
                        interval: 10
                        repeat: true
                        running: true
                        onTriggered: {{
                          if (!parent.queued && service.syncing) {{
                            parent.queued = true
                            var first = service.requestSync()
                            var second = service.requestSync()
                            var third = service.requestSync()
                            console.info("QUEUE_ACCEPTED " + (first && second && third))
                          }}
                        }}
                      }}

                      Timer {{
                        interval: 1000
                        running: true
                        onTriggered: Qt.quit()
                      }}
                    }}
                    """
                ),
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["NO_COLOR"] = "1"
            result = subprocess.run(
                ["quickshell", "--no-color", "--path", str(test_dir / "shell.qml")],
                cwd=test_dir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("QUEUE_ACCEPTED true", result.stdout + result.stderr)
            lines = (test_dir / "runs.log").read_text(encoding="utf-8").splitlines()
            self.assertNotIn("OVERLAP", lines)
            self.assertEqual(sum(line.startswith("START ") for line in lines), 2, lines)
            self.assertEqual(sum(line.startswith("END ") for line in lines), 2, lines)


if __name__ == "__main__":
    unittest.main()
