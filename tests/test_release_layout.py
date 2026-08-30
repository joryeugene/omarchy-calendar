# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from omarchy_calendar import __version__, settings as settings_module


ROOT = Path(__file__).parents[1]
CSS_URL = re.compile(r"\burl\s*\(", re.IGNORECASE)
ACTIVE_TAGS = {"base", "script", "form", "iframe", "object", "embed"}
MEDIA_ATTRIBUTES = {
    "audio": ("src",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "track": ("src",),
    "video": ("poster", "src"),
}


class ElementParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.inline_css = []
        self._style_depth = 0

    def handle_starttag(self, tag, attributes):
        normalized = tag.lower()
        self.elements.append((normalized, {name.lower(): value or "" for name, value in attributes}))
        if normalized == "style":
            self._style_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == "style":
            self._style_depth = max(0, self._style_depth - 1)

    def handle_data(self, data):
        if self._style_depth:
            self.inline_css.append(data)


def _resource_targets(value):
    return [candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip()]


def _is_public_relative_url(value):
    parsed = urlsplit(value)
    return bool(parsed.path) and not parsed.scheme and not parsed.netloc and not parsed.path.startswith("/")


def _static_site_dependency_violations(site):
    homepage = site / "index.html"
    privacy = site / "privacy" / "index.html"
    terms = site / "terms" / "index.html"
    verification = site / "verification" / "index.html"
    published = site / "assets" / "flight-deck-calendar-week.png"
    headers = site / "_headers"
    violations = []

    expected_files = {
        Path(".well-known/microsoft-identity-association.json"),
        Path("_headers"),
        Path("assets/flight-deck-calendar-week.png"),
        Path("index.html"),
        Path("privacy/index.html"),
        Path("styles.css"),
        Path("terms/index.html"),
        Path("verification/index.html"),
    }
    for path in (homepage, privacy, terms, verification, site / "styles.css", published, headers):
        if not path.is_file():
            violations.append(f"missing artifact: {path.relative_to(site)}")
    if violations:
        return violations
    if published.read_bytes() != (ROOT / "screenshots" / "flight-deck-calendar-week.png").read_bytes():
        violations.append("published Week image differs from the approved asset")
    actual_files = {path.relative_to(site) for path in site.rglob("*") if path.is_file()}
    unexpected = sorted(actual_files - expected_files)
    if unexpected:
        violations.append(f"unexpected site files: {[str(path) for path in unexpected]}")

    header_text = headers.read_text(encoding="utf-8")
    for required in (
        "Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self';",
        "frame-ancestors 'none'",
        "Referrer-Policy: no-referrer",
        "X-Content-Type-Options: nosniff",
        "Permissions-Policy: camera=(), microphone=(), geolocation=()",
    ):
        if required not in header_text:
            violations.append(f"missing security header: {required}")

    for page in sorted(site.rglob("*.html")):
        parser = ElementParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for tag, attributes in parser.elements:
            if tag in ACTIVE_TAGS:
                violations.append(f"active <{tag}> element in {page.relative_to(site)}")
            for name, value in attributes.items():
                if name.startswith("on"):
                    violations.append(f"inline {name} handler in {page.relative_to(site)}")
                if name == "style" and CSS_URL.search(value):
                    violations.append(f"CSS url() resource in {page.relative_to(site)}")
                if value.strip().lower().startswith("javascript:"):
                    violations.append(f"javascript: URL in {page.relative_to(site)}")
            if tag == "link" and "stylesheet" in attributes.get("rel", "").lower().split():
                if not _is_public_relative_url(attributes.get("href", "")):
                    violations.append(f"remote stylesheet in {page.relative_to(site)}")
            for name in MEDIA_ATTRIBUTES.get(tag, ()):
                for target in _resource_targets(attributes.get(name, "")):
                    if not _is_public_relative_url(target):
                        violations.append(f"remote {tag} resource in {page.relative_to(site)}")
        inline_css = "".join(parser.inline_css)
        if "@import" in inline_css.lower():
            violations.append(f"CSS import in {page.relative_to(site)}")
        if CSS_URL.search(inline_css):
            violations.append(f"CSS url() resource in {page.relative_to(site)}")

    for stylesheet in site.rglob("*.css"):
        css = stylesheet.read_text(encoding="utf-8")
        if "@import" in css.lower():
            violations.append(f"CSS import in {stylesheet.relative_to(site)}")
        if CSS_URL.search(css):
            violations.append(f"CSS url() resource in {stylesheet.relative_to(site)}")
    return violations


class ReleaseLayoutTests(unittest.TestCase):
    def _run_release_scanner_with_google_credential(self, temporary, *, duplicate_path=None):
        release_root = Path(temporary) / "release"
        shutil.copytree(
            ROOT,
            release_root,
            ignore=shutil.ignore_patterns(
                ".git", ".private", ".superpowers", "__pycache__", "*.pyc"
            ),
        )
        for test_module in (release_root / "tests").glob("test_*.py"):
            test_module.unlink()
        (release_root / "tests" / "test_smoke.py").write_text(
            "# SPDX-License-Identifier: GPL-3.0-or-later\n"
            "import unittest\n\n"
            "class SmokeTest(unittest.TestCase):\n"
            "    def test_release_fixture(self):\n"
            "        self.assertTrue(True)\n",
            encoding="utf-8",
        )

        credential = "GOC" + "SPX-" + ("Ab1_" * 4)
        settings = release_root / "src" / "omarchy_calendar" / "settings.py"
        source = settings.read_text(encoding="utf-8")
        after = f'BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL = "{credential}"'
        source, replacements = re.subn(
            r'(?m)^BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL = ".*"$',
            after,
            source,
            count=1,
        )
        self.assertEqual(replacements, 1)
        settings.write_text(source, encoding="utf-8")
        if duplicate_path is not None:
            duplicate = release_root / duplicate_path
            duplicate.write_text(
                duplicate.read_text(encoding="utf-8")
                + f"\nUnexpected credential fixture: {credential}\n",
                encoding="utf-8",
            )

        for command in (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "release-check@example.com"],
            ["git", "config", "user.name", "Release Check"],
            ["git", "add", "."],
            ["git", "commit", "-qm", "scanner fixture"],
        ):
            subprocess.run(command, cwd=release_root, check=True)

        return subprocess.run(
            [str(release_root / "scripts" / "check"), "--release"],
            cwd=release_root,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_release_scanner_allows_only_the_canonical_bundled_google_credential_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            allowed = self._run_release_scanner_with_google_credential(temporary)

        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertIn("PASS zero secrets", allowed.stdout)

        with tempfile.TemporaryDirectory() as temporary:
            duplicated = self._run_release_scanner_with_google_credential(
                temporary, duplicate_path=Path("PRIVACY.md")
            )

        self.assertNotEqual(duplicated.returncode, 0, duplicated.stdout)
        self.assertIn("FAIL secret-shaped values: PRIVACY.md", duplicated.stderr)

    def test_static_site_allows_external_anchor_links_without_resource_dependencies(self):
        site = ROOT / "site"
        homepage = (site / "index.html").read_text(encoding="utf-8")

        self.assertIn('href="https://github.com/joryeugene/omarchy-calendar"', homepage)
        self.assertEqual(_static_site_dependency_violations(site), [])

    def test_static_site_associates_the_production_microsoft_application(self):
        association = json.loads(
            (ROOT / "site" / ".well-known" / "microsoft-identity-association.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(association, {
            "associatedApplications": [{
                "applicationId": settings_module.BUNDLED_PUBLIC_CLIENT_IDS["microsoft"],
            }],
        })

    def test_static_site_dependency_boundary_rejects_unsafe_mutations(self):
        mutations = (
            (
                "base URL",
                "index.html",
                "<head>",
                '<head>\n  <base href="https://example.com/">',
                "active <base> element",
            ),
            (
                "remote stylesheet",
                "index.html",
                'href="styles.css"',
                'href="https://example.com/site.css"',
                "remote stylesheet",
            ),
            (
                "remote media",
                "index.html",
                'src="assets/flight-deck-calendar-week.png"',
                'src="https://example.com/calendar.png"',
                "remote img resource",
            ),
            (
                "CSS URL",
                "styles.css",
                "/* SPDX-License-Identifier: GPL-3.0-or-later */",
                '/* SPDX-License-Identifier: GPL-3.0-or-later */\nbody { background: url("pixel.gif"); }',
                "CSS url() resource",
            ),
            (
                "inline handler",
                "index.html",
                "<body>",
                '<body onclick="alert(1)">',
                "inline onclick handler",
            ),
            (
                "inline CSS URL",
                "index.html",
                "<body>",
                '<body style="background: url(pixel.gif)">',
                "CSS url() resource",
            ),
            (
                "inline style block CSS URL",
                "index.html",
                "</head>",
                "<style>body { background: url(pixel.gif); }</style>\n</head>",
                "CSS url() resource",
            ),
            (
                "javascript URL",
                "index.html",
                'href="./" aria-label="Flight Deck Calendar home"',
                'href="javascript:void(0)" aria-label="Flight Deck Calendar home"',
                "javascript: URL",
            ),
        )
        for name, relative, before, after, expected in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                site = Path(temporary) / "site"
                shutil.copytree(ROOT / "site", site)
                target = site / relative
                source = target.read_text(encoding="utf-8")
                self.assertIn(before, source)
                target.write_text(source.replace(before, after, 1), encoding="utf-8")

                self.assertTrue(
                    any(expected in violation for violation in _static_site_dependency_violations(site)),
                    expected,
                )
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            shutil.copytree(ROOT / "site", site)
            (site / "extra.html").write_text("<script src=runner.js></script>\n", encoding="utf-8")

            self.assertTrue(
                any(
                    "active <script> element in extra.html" in violation
                    for violation in _static_site_dependency_violations(site)
                )
            )

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

        self.assertEqual(manifest["version"], "1.0.0-rc.4")
        self.assertEqual(project["project"]["version"], "1.0.0rc4")
        self.assertEqual(__version__, "1.0.0rc4")
        self.assertIn("1.0.0 RC 4", (ROOT / "SettingsView.qml").read_text(encoding="utf-8"))

    def test_candidate_release_requires_bundled_provider_registrations(self):
        candidate_setup_copy = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/INSTALL.md", "site/verification/index.html")
        )
        bundled = settings_module.BUNDLED_PUBLIC_CLIENT_IDS
        google_credential = settings_module.BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL

        self.assertRegex(
            bundled["google"],
            r"^[A-Za-z0-9._-]+\.apps\.googleusercontent\.com$",
        )
        self.assertRegex(
            bundled["microsoft"],
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        )
        self.assertTrue(google_credential.startswith("GOCSPX-"))
        self.assertIn("Connect in browser", candidate_setup_copy)
        self.assertIn("Advanced provider override", candidate_setup_copy)
        self.assertNotIn("Bring your own OAuth", candidate_setup_copy)
        self.assertNotIn("not one-click or seamless", candidate_setup_copy)

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
            "/.private/", "/.superpowers/", "/.wrangler/", "__pycache__/", "*.pyc", "*.db", "*.sqlite", ".env", ".env.*",
            "providers.json", "*.log", "*.swp", ".DS_Store",
        ):
            self.assertIn(pattern, ignored)


if __name__ == "__main__":
    unittest.main()
