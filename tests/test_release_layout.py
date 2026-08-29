# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from omarchy_calendar import __version__


ROOT = Path(__file__).parents[1]


class ReleaseLayoutTests(unittest.TestCase):
    def test_static_site_has_no_executable_or_remote_resource_dependency(self):
        site = ROOT / "site"
        homepage = site / "index.html"
        privacy = site / "privacy" / "index.html"
        approved = ROOT / "screenshots" / "flight-deck-calendar-week.png"
        published = site / "assets" / "flight-deck-calendar-week.png"

        for path in (homepage, privacy, site / "styles.css", published):
            self.assertTrue(path.is_file(), path)
        self.assertEqual(published.read_bytes(), approved.read_bytes())
        self.assertEqual(
            {path.suffix for path in site.rglob("*") if path.is_file()},
            {".html", ".css", ".png"},
        )

        markup = homepage.read_text(encoding="utf-8") + privacy.read_text(encoding="utf-8")
        for forbidden in ("<script", "<form", "<iframe", "<object", "<embed"):
            self.assertNotIn(forbidden, markup.lower())
        self.assertNotIn("@import", (site / "styles.css").read_text(encoding="utf-8").lower())

    def test_release_check_rejects_tracked_test_source_without_spdx(self):
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release"
            shutil.copytree(
                ROOT,
                release_root,
                ignore=shutil.ignore_patterns(
                    ".git", ".private", ".superpowers", "__pycache__", "*.pyc"
                ),
            )
            for test_module in ("test_docs.py", "test_release_layout.py"):
                (release_root / "tests" / test_module).unlink()
            probe = release_root / "tests" / "spdx_probe.py"
            probe.write_text("VALUE = 1\n", encoding="utf-8")
            for command in (
                ["git", "init", "-q"],
                ["git", "config", "user.email", "release-check@example.com"],
                ["git", "config", "user.name", "Release Check"],
                ["git", "add", "."],
                ["git", "commit", "-qm", "baseline"],
            ):
                subprocess.run(command, cwd=release_root, check=True)

            result = subprocess.run(
                [str(release_root / "scripts" / "check"), "--release"],
                cwd=release_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL missing SPDX header: tests/spdx_probe.py", result.stderr)

    def test_release_check_rejects_a_force_listed_internal_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            release_root = Path(temporary) / "release"
            shutil.copytree(
                ROOT,
                release_root,
                ignore=shutil.ignore_patterns(
                    ".git", ".private", ".superpowers", "__pycache__", "*.pyc"
                ),
            )
            for test_module in ("test_docs.py", "test_release_layout.py"):
                (release_root / "tests" / test_module).unlink()
            for command in (
                ["git", "init", "-q"],
                ["git", "config", "user.email", "release-check@example.com"],
                ["git", "config", "user.name", "Release Check"],
                ["git", "add", "."],
                ["git", "commit", "-qm", "baseline"],
            ):
                subprocess.run(command, cwd=release_root, check=True)

            artifact = release_root / ".superpowers" / "force-listed.txt"
            artifact.parent.mkdir()
            artifact.write_text(
                "workspace = " + "/" + "home/release-user/private\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "add", "-f", str(artifact.relative_to(release_root))],
                cwd=release_root,
                check=True,
            )
            subprocess.run(["git", "commit", "-qm", "force-list artifact"], cwd=release_root, check=True)

            result = subprocess.run(
                [str(release_root / "scripts" / "check"), "--release"],
                cwd=release_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("FAIL private paths: .superpowers/force-listed.txt", result.stderr)

    def test_security_policy_has_the_private_github_advisory_submission_path(self):
        policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/joryeugene/omarchy-calendar/security/advisories/new",
            policy,
        )

    def test_official_plugin_root_has_no_legacy_install_or_timer_tree(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["id"], "io.github.joryeugene.omarchy-calendar")
        self.assertFalse((ROOT / "plugin").exists())
        self.assertFalse((ROOT / "systemd").exists())
        self.assertFalse((ROOT / "scripts" / "install").exists())
        self.assertFalse((ROOT / "scripts" / "rollback").exists())
        self.assertFalse((ROOT / "scripts" / "integrate.py").exists())

    def test_bundled_helper_runs_from_plugin_root_without_pythonpath(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            plugin.mkdir()
            shutil.copy2(ROOT / "calendarctl", plugin / "calendarctl")
            shutil.copytree(ROOT / "src", plugin / "src")
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment["XDG_STATE_HOME"] = str(root / "state")
            environment["XDG_CONFIG_HOME"] = str(root / "config")

            seed = subprocess.run(
                [str(plugin / "calendarctl"), "demo", "seed", "--date", "2026-08-25"],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(seed.returncode, 0, seed.stderr)
            self.assertEqual(json.loads(seed.stdout)["seeded"], 25)
            self.assertTrue((root / "state" / "omarchy-calendar" / "calendar.db").is_file())
            self.assertEqual(list(plugin.rglob("__pycache__")), [])
            self.assertEqual(list(plugin.rglob("*.pyc")), [])

    def test_release_metadata_and_one_command_check_exist(self):
        required = (
            "README.md",
            "LICENSE",
            "PRIVACY.md",
            "SECURITY.md",
            "TRADEMARKS.md",
            "pyproject.toml",
            "scripts/check",
            ".github/workflows/check.yml",
        )
        for path in required:
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertTrue(os.access(ROOT / "scripts" / "check", os.X_OK))
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('license = "GPL-3.0-or-later"', project)
        self.assertIn('name = "flight-deck-calendar"', project)
        self.assertNotIn('Environment :: X11 Applications :: Qt', project)

    def test_release_version_is_consistent_across_public_surfaces(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(manifest["version"], "1.0.0-rc.3")
        self.assertEqual(project["project"]["version"], "1.0.0rc3")
        self.assertEqual(__version__, "1.0.0rc3")
        self.assertIn("1.0.0 RC 3", (ROOT / "SettingsView.qml").read_text(encoding="utf-8"))

    def test_public_tree_excludes_private_reports_and_generated_files(self):
        for internal in (
            "GOAL.md",
            "TASKS.md",
            "docs/VERIFICATION.md",
            "docs/PUBLIC_LAUNCH.md",
        ):
            self.assertFalse((ROOT / internal).exists(), internal)
        self.assertFalse((ROOT / "docs" / "live-provider-report.md").exists())
        self.assertFalse((ROOT / "docs" / "local-demo-report.md").exists())
        tracked_generated = [
            path for path in subprocess.check_output(
                ["git", "ls-files"], cwd=ROOT, text=True
            ).splitlines()
            if path.endswith(".pyc") or "__pycache__/" in path
        ]
        self.assertEqual(tracked_generated, [])

    def test_release_sources_have_spdx_headers(self):
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT, text=True
        ).split("\0")
        sources = [
            ROOT / "calendarctl",
            *(ROOT / path for path in tracked if Path(path).suffix in {".py", ".js", ".mjs", ".qml"}),
        ]
        for path in sources:
            first_lines = "\n".join(path.read_text(encoding="utf-8").splitlines()[:4])
            self.assertIn("SPDX-License-Identifier: GPL-3.0-or-later", first_lines, path.name)

    def test_gitignore_blocks_local_data_secrets_and_generated_artifacts(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for pattern in (
            "/.private/", "/.superpowers/", "__pycache__/", "*.pyc", "*.db", "*.sqlite", ".env", ".env.*",
            "providers.json", "*.log", "*.swp", ".DS_Store",
        ):
            self.assertIn(pattern, ignored)


if __name__ == "__main__":
    unittest.main()
