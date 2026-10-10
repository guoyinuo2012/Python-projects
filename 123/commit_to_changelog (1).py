#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8.1,<9"]
# ///
"""
# Commit-to-Changelog

A local Python CLI that turns Git history into categorized changelogs and public
release note drafts. Runs offline after installation, with no API key or GitHub
account. Uses Click and Git subprocesses; never stages, commits, stashes, resets,
or pushes your repository.

## Quick start

Requires Python 3.10+ and Git on PATH. Everything is in this file: CLI,
README, and the 12-test integration suite. Install the Click dependency once:

```sh
python -m pip install "click>=8.1,<9"
python commit_to_changelog.py readme
python commit_to_changelog.py build --repo /path/to/your/repository --stdout
python commit_to_changelog.py build --repo /path/to/your/repository
python commit_to_changelog.py watch --repo /path/to/your/repository
python commit_to_changelog.py self-test
```

The README can also be read directly at the top of this file. The `readme`
command works even before Click is installed. Optional Markdown export:

```sh
python commit_to_changelog.py readme > README.md
```

From inside your target repository, omit `--repo`. Default outputs are
`CHANGELOG.md` and `RELEASE_NOTES.md` in the repository root. Preview with
`--stdout` writes nothing. Bare repositories are unsupported because outputs
need a working tree. Empty repositories produce a clean error until a commit exists.

## Draft a release range

```sh
python commit_to_changelog.py build --since v1.2.0 --label 1.3.0
python commit_to_changelog.py watch --since v1.2.0 --label 1.3.0 --interval 2
python commit_to_changelog.py build --changelog drafts/CHANGELOG.md --release-notes drafts/RELEASE.md
```

`--since` excludes the specified ancestor commit or tag; omitted means all
history reachable from HEAD. HEAD is resolved once per generation, so every draft
uses one snapshot. Invalid refs and non-ancestor bases fail rather than widening
the release range silently. The displayed date is HEAD's commit date, making
unchanged runs byte-identical. Version labels are supplied by you; this tool
suggests a bump but does not create tags or change package versions.

## How categorization works

| Commit evidence | Category |
| --- | --- |
| `feat:` / `feat(scope):` | Features |
| `fix:` / `revert:` | Fixes |
| `perf:` | Performance |
| `docs:` | Documentation |
| `chore:`, `refactor:`, `test:`, `build:`, `ci:`, `style:` | Maintenance |
| `!` after type/scope or `BREAKING CHANGE:` / `BREAKING-CHANGE:` footer | Breaking Changes |
| Plain-language keywords | Inferred category, marked for review |
| Unknown types or unclear messages | Other Changes, marked for review |

Breaking changes take priority. Suggested bumps are major for breaking changes,
minor for features, patch for any other nonempty range, and none for an empty range.
Actual compatibility and pre-1.0 version policy require human judgment.

Messages like `wip`, `fix`, or `update` include up to three changed paths and an
instruction to inspect the commit. The tool never invents product behavior from
a vague message. Markdown-sensitive characters are escaped. Commit bodies are
inspected for breaking-change footers but otherwise omitted from public drafts.

Deduplication uses category, scope, and case/punctuation-normalized text. Repeated
entries become one bullet with all contributing commit hashes. Distinct scopes
stay separate. Similar paraphrases are not automatically merged. Merge commits
are excluded; their reachable non-merge commits are included. Reverts are listed
as fixes; they do not automatically cancel earlier entries.

Public drafts omit Maintenance and retain source hashes and review flags.
Review them before publishing: commit subjects may contain internal details.
This implementation is a deterministic agent, not an LLM summarizer; it makes
no network calls or claims to infer behavior from diffs.

## Safe regeneration

The CLI maintains one checksum-protected block per output:

```md
<!-- git-notes:start sha256=... -->
Generated content
<!-- git-notes:end -->
```

Handwritten text outside the block survives reruns. Existing files without a
block get one appended. If you edit inside a generated block, regeneration stops;
move your edits outside the markers before running again. Malformed or multiple
blocks also stop generation. Both output contents are validated before writing.
Each file is replaced atomically, but the two-file update is not a transaction
if an OS/filesystem failure occurs midway.

Dirty repositories are supported: only committed history is read. Output files
can themselves make the working tree dirty. The watcher polls HEAD rather than
installing a Git hook, so existing hooks are untouched. It regenerates on commits,
checkouts, resets, and rebases, including removing unreachable history from the
draft. Changes to uncommitted files alone do not trigger generation.

Ctrl+C stops the watcher. Git failures, conflicts in generated text, and invalid
ranges stop it with an error; correct the issue and restart. A worktree-local
exclusive lock prevents overlapping writes. If the process is killed forcibly,
remove the stale `git-notes.lock` under the path reported by
`git rev-parse --absolute-git-dir`, after ensuring no run is active.
Output paths must stay inside the working tree and outside Git metadata;
symlink output files are refused.

Each run refreshes one release draft, not an accumulating archive. To preserve a
finished release, copy its generated text into a historical section outside the
markers or use new output paths for the next release.

## Verification

```sh
python commit_to_changelog.py self-test
```

The integration suite creates disposable repositories and covers dirty states,
duplicates, release ranges, breaking changes, history rewrites, merges, Unicode,
output conflicts, path safety, empty repositories, and live watcher updates.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from contextlib import contextmanager

import sys

if __name__ == "__main__" and sys.argv[1:] == ["readme"]:
    print(__doc__, end="")
    raise SystemExit(0)

try:
    import click
except ModuleNotFoundError:
    raise SystemExit('Install the dependency: python -m pip install "click>=8.1,<9"')

CATEGORIES = ("Breaking Changes", "Features", "Fixes", "Performance", "Documentation",
              "Maintenance", "Other Changes")
TYPES = {"feat": "Features", "fix": "Fixes", "perf": "Performance",
         "docs": "Documentation", "refactor": "Maintenance", "test": "Maintenance",
         "build": "Maintenance", "ci": "Maintenance", "chore": "Maintenance",
         "style": "Maintenance", "revert": "Fixes"}
CONVENTIONAL = re.compile(r"^(\w+)(?:\(([^\n)]+)\))?(!)?:\s*(.+)$")
BLOCK = re.compile(r"<!-- git-notes:start sha256=([a-f0-9]{64}) -->\n(.*?)<!-- git-notes:end -->", re.S)


class NotesError(Exception):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NotesError(f"Cannot run Git: {exc}") from exc
    if check and result.returncode:
        raise NotesError(result.stderr.strip() or "Git command failed")
    return result.stdout if result.returncode == 0 else ""


def revision(repo: Path, ref: str) -> str:
    # Resolve separately: refs never become options or arbitrary revision expressions in log.
    return git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()


@dataclass
class Entry:
    category: str
    text: str
    scope: str = ""
    review: bool = False
    hashes: list[str] = field(default_factory=list)


def classify(message: str, files: list[str], sha: str) -> Entry:
    lines = message.strip().splitlines()
    subject = lines[0].strip() if lines else "Empty commit message"
    match = CONVENTIONAL.match(subject)
    scope = ""
    review = False
    breaking = re.search(r"^BREAKING[ -]CHANGE:\s*(.*)$", message, re.M)
    if match:
        kind, scope, bang, text = match.groups()
        category = TYPES.get(kind.lower(), "Other Changes")
        review = kind.lower() not in TYPES
        if bang:
            category = "Breaking Changes"
    else:
        text = subject
        rules = ((r"\b(fix(?:es|ed)?|bug|crash|resolve[ds]?|repair)\b", "Fixes"),
                 (r"\b(add(?:s|ed)?|implement(?:s|ed)?|introduce[ds]?|feature)\b", "Features"),
                 (r"\b(performance|optimi[sz]e[ds]?|speed|faster)\b", "Performance"),
                 (r"\b(docs?|documentation|readme)\b", "Documentation"),
                 (r"\b(refactor|dependencies|deps|chore|tests?|ci|cleanup)\b", "Maintenance"))
        category = next((label for pattern, label in rules if re.search(pattern, subject, re.I)), "Other Changes")
        review = True  # Inferred classification always warrants editorial review.
    if breaking:
        category = "Breaking Changes"
        if breaking.group(1).strip():
            text += " — " + breaking.group(1).strip()
    if re.fullmatch(r"(?:wip|oops|stuff|changes?|updates?|fix(?:es|ed)?|misc|work|done)[.! ]*", text, re.I):
        paths = ", ".join(files[:3]) or "no changed paths"
        text += f" — inspect commit ({paths})"
        review = True
    text = " ".join(text.split())
    return Entry(category, text, scope or "", review, [sha])


def collect(repo: Path, head: str, since: str | None) -> list[Entry]:
    selection = f"{since}..{head}" if since else head
    # NUL fields preserve multiline bodies and avoid delimiter assumptions about prose.
    raw = git(repo, "log", "--reverse", "--no-merges", "--format=%H%x00%B%x00", selection, "--")
    fields = raw.split("\0")
    entries: dict[tuple[str, str, str], Entry] = {}
    for index in range(0, len(fields) - 1, 2):
        sha, message = fields[index].strip(), fields[index + 1]
        files = git(repo, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", sha, "--").split("\0")
        entry = classify(message, [x for x in files if x], sha)
        normalized = re.sub(r"[\W_]+", " ", entry.text.casefold()).strip()
        key = (entry.category, entry.scope.casefold(), normalized)
        if key in entries:
            entries[key].hashes.append(sha)
            entries[key].review |= entry.review
        else:
            entries[key] = entry
    return list(entries.values())


def escape(text: str) -> str:
    # Commit text is untrusted Markdown; never let it inject headings, HTML or links.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|~-])", r"\\\1", text)


def render(entries: list[Entry], label: str, head: str, date: str, public: bool) -> str:
    level = "major" if any(e.category == "Breaking Changes" for e in entries) else (
        "minor" if any(e.category == "Features" for e in entries) else "patch")
    lines = [f"## {escape(label)} · {date}", ""]
    if public:
        lines += ["Draft for editorial review.", ""]
    lines += [f"Suggested version bump: **{level if entries else 'none'}** (commit-message evidence only).",
              f"Source: `{head}` · {sum(len(e.hashes) for e in entries)} commits · {len(entries)} entries.", ""]
    if not entries:
        lines += ["No commits in this range.", ""]
    for category in CATEGORIES:
        selected = [e for e in entries if e.category == category]
        if not selected or (public and category == "Maintenance"):
            continue
        lines += [f"### {category}", ""]
        for entry in selected:
            scope = f"**{escape(entry.scope)}:** " if entry.scope else ""
            references = ", ".join(f"`{sha[:12]}`" for sha in entry.hashes)
            review = " **[Review required]**" if entry.review else ""
            lines.append(f"- {scope}{escape(entry.text)} ({references}){review}")
        lines.append("")
    if public and entries and all(e.category == "Maintenance" for e in entries):
        lines += ["This range contains internal maintenance changes only.", ""]
    return "\n".join(lines) + "\n"


def managed(existing: str, body: str, title: str) -> str:
    matches = list(BLOCK.finditer(existing))
    if len(matches) > 1 or existing.count("<!-- git-notes:start") != len(matches) or existing.count("<!-- git-notes:end -->") != len(matches):
        raise NotesError("Malformed or multiple generated sections; repair the markers first")
    if matches and hashlib.sha256(matches[0].group(2).encode()).hexdigest() != matches[0].group(1):
        raise NotesError("Generated section was edited. Move edits outside its markers before regenerating")
    digest = hashlib.sha256(body.encode()).hexdigest()
    block = f"<!-- git-notes:start sha256={digest} -->\n{body}<!-- git-notes:end -->"
    if matches:
        match = matches[0]
        return existing[:match.start()] + block + existing[match.end():]
    return (existing.rstrip() + "\n\n" if existing else f"# {title}\n\n") + block + "\n"


def atomic_write(path: Path, content: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def lock(repo: Path):
    location = Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "git-notes.lock"
    try:
        descriptor = os.open(location, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise NotesError(f"Another run holds {location}. If it crashed, remove the stale lock manually") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        location.unlink(missing_ok=True)


def generate(repo: Path, since: str | None, label: str, changelog: Path,
             release_notes: Path, stdout: bool) -> str:
    root = Path(git(repo, "rev-parse", "--show-toplevel").strip())
    # Verify HEAD exists before acquiring the write lock (empty repositories get a useful error).
    head = revision(root, "HEAD")
    base = revision(root, since) if since else None
    if base:
        git(root, "merge-base", "--is-ancestor", base, head)
    entries = collect(root, head, base)
    date = git(root, "show", "-s", "--format=%cs", head).strip()
    content = render(entries, label, head, date, False)
    if stdout:
        click.echo(content, nl=False)
        return head
    outputs = [(root / changelog, content, "Changelog"),
               (root / release_notes, render(entries, label, head, date, True), "Release notes")]
    git_dir = Path(git(root, "rev-parse", "--absolute-git-dir").strip()).resolve()
    for path, _, _ in outputs:
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()) or resolved.is_relative_to(git_dir) or ".git" in resolved.relative_to(root.resolve()).parts:
            raise NotesError("Output paths must stay within the working tree, outside Git metadata")
    if outputs[0][0].resolve() == outputs[1][0].resolve():
        raise NotesError("Changelog and release notes must use different paths")
    if git(root, "status", "--porcelain"):
        click.echo("Working tree is dirty; reading committed history only.", err=True)
    with lock(root):
        prepared = []
        for path, body, title in outputs:
            if path.is_symlink():
                raise NotesError(f"Refusing symlink output: {path}")
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            prepared.append((path, managed(existing, body, title)))
        for path, text in prepared:
            atomic_write(path, text)
    click.echo(f"Drafted {len(entries)} entries → {outputs[0][0]} and {outputs[1][0]}")
    return head


@click.group()
@click.version_option("0.1.0")
def cli():
    """Turn local Git commits into categorized Markdown release drafts."""


def common_options(function):
    for decorator in reversed([
        click.option("--repo", type=click.Path(path_type=Path, exists=True, file_okay=False), default=".", show_default=True),
        click.option("--since", help="Exclusive ancestor commit/tag; omitted means all reachable history."),
        click.option("--label", default="Unreleased", show_default=True),
        click.option("--changelog", type=click.Path(path_type=Path), default="CHANGELOG.md", show_default=True),
        click.option("--release-notes", type=click.Path(path_type=Path), default="RELEASE_NOTES.md", show_default=True),
    ]):
        function = decorator(function)
    return function


@cli.command()
@common_options
@click.option("--stdout", is_flag=True, help="Preview changelog without writing files.")
def build(**kwargs):
    """Generate or refresh one protected release draft."""
    try:
        generate(**kwargs)
    except (NotesError, OSError, UnicodeError) as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command()
@common_options
@click.option("--interval", type=click.FloatRange(min=0.2), default=2.0, show_default=True)
def watch(interval, **kwargs):
    """Poll HEAD and refresh drafts after commits, checkout, reset or rebase."""
    try:
        last_head = generate(**kwargs, stdout=False)
        click.echo("Watching HEAD. Press Ctrl+C to stop.")
        while True:
            time.sleep(interval)
            if revision(kwargs["repo"], "HEAD") != last_head:
                last_head = generate(**kwargs, stdout=False)
    except KeyboardInterrupt:
        click.echo("\nWatcher stopped.")
    except (NotesError, OSError, UnicodeError) as exc:
        raise click.ClickException(str(exc)) from exc



# Bundled integration tests
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import time
import signal
import unittest

from click.testing import CliRunner


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.runner = CliRunner()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def commit(self, message):
        self.git("commit", "--allow-empty", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def run_cli(self, *args):
        return self.runner.invoke(cli, ["build", "--repo", str(self.repo), *args])

    def test_dirty_state_and_idempotent_dedup(self):
        self.commit("feat(ui): Add dashboard")
        self.commit("feat(ui): add dashboard!")
        self.commit("fix: prevent crash")
        (self.repo / "personal.txt").write_text("leave this alone")
        before = self.git("status", "--porcelain")
        result = self.run_cli()
        self.assertEqual(result.exit_code, 0, result.output)
        output = self.repo / "CHANGELOG.md"
        first = output.read_bytes()
        self.assertEqual(first.count(b"**ui:**"), 1)
        self.assertIn(b"3 commits", first)
        self.assertIn("dirty", result.output)
        self.assertEqual((self.repo / "personal.txt").read_text(), "leave this alone")
        self.assertIn(before, self.git("status", "--porcelain"))
        second = self.run_cli()
        self.assertEqual(second.exit_code, 0, second.output)
        self.assertEqual(first, output.read_bytes())

    def test_range_breaking_and_public_maintenance_filter(self):
        self.commit("feat: old feature")
        self.git("tag", "v1")
        self.commit("refactor!: replace API\n\nBREAKING CHANGE: use the new endpoint")
        self.commit("chore: bump dependencies")
        result = self.run_cli("--since", "v1", "--label", "2.0.0")
        self.assertEqual(result.exit_code, 0, result.output)
        output = (self.repo / "CHANGELOG.md").read_text()
        self.assertIn("Breaking Changes", output)
        self.assertIn("**major**", output)
        self.assertNotIn("old feature", output)
        self.assertNotIn("bump dependencies", (self.repo / "RELEASE_NOTES.md").read_text())

    def test_handwritten_content_and_generated_edit_conflict(self):
        self.commit("fix: stop crashing")
        output = self.repo / "CHANGELOG.md"
        output.write_text("# My historical releases\n\nKeep me.\n")
        self.assertEqual(self.run_cli().exit_code, 0)
        self.assertIn("Keep me.", output.read_text())
        output.write_text(output.read_text().replace("stop crashing", "edited by hand"))
        before = output.read_bytes()
        self.assertNotEqual(self.run_cli().exit_code, 0)
        self.assertEqual(before, output.read_bytes())

    def test_preview_and_invalid_refs(self):
        self.commit("wip")
        result = self.run_cli("--stdout")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Review required", result.output)
        self.assertFalse((self.repo / "CHANGELOG.md").exists())
        self.assertNotEqual(self.run_cli("--since", "--all").exit_code, 0)

    def test_rewrite_removes_old_entries(self):
        first = self.commit("feat: original")
        self.commit("feat: removed later")
        self.run_cli()
        self.git("reset", "--hard", first)
        self.assertEqual(self.run_cli().exit_code, 0)
        self.assertNotIn("removed later", (self.repo / "CHANGELOG.md").read_text())

    def test_empty_repository(self):
        result = self.run_cli()
        self.assertNotEqual(result.exit_code, 0)
        self.assertFalse((self.repo / "CHANGELOG.md").exists())

    def test_lock_and_path_safety(self):
        self.commit("fix: a bug")
        with lock(self.repo):
            self.assertNotEqual(self.run_cli().exit_code, 0)
        self.assertNotEqual(self.run_cli("--changelog", ".git/config").exit_code, 0)
        self.assertNotEqual(self.run_cli("--release-notes", "CHANGELOG.md").exit_code, 0)
        self.assertNotEqual(self.run_cli("--changelog", "../escape.md").exit_code, 0)
        target = self.repo / "original.md"
        target.write_text("untouched")
        (self.repo / "linked.md").symlink_to(target)
        self.assertNotEqual(self.run_cli("--changelog", "linked.md").exit_code, 0)
        self.assertEqual(target.read_text(), "untouched")

    def test_multiline_unicode_and_merge(self):
        self.commit("feat: 初めての機能\n\nBody with multiline prose")
        self.git("checkout", "-qb", "side")
        self.commit("fix: side bug")
        self.git("checkout", "-q", "-")
        self.commit("docs: main guide")
        self.git("merge", "--no-ff", "-qm", "merge side", "side")
        result = self.run_cli("--stdout")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("初めての機能", result.output)
        self.assertIn("side bug", result.output)
        self.assertNotIn("merge side", result.output)

    def test_live_watcher_updates_on_commit(self):
        self.commit("feat: first feature")
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                    "watch", "--repo", str(self.repo), "--interval", "0.2"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        output = self.repo / "CHANGELOG.md"
        deadline = time.monotonic() + 8
        while not output.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(output.exists())
        self.commit("fix: watcher picks this up")
        while "watcher picks this up" not in output.read_text() and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn("watcher picks this up", output.read_text())
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertFalse((self.repo / ".git" / "git-notes.lock").exists())


class ParserTests(unittest.TestCase):
    def test_vague_commit_and_scope(self):
        entry = classify("fix", ["src/main.py"], "abc")
        self.assertTrue(entry.review)
        self.assertIn("src/main.py", entry.text)
        self.assertEqual(classify("feat(auth): login", [], "abc").scope, "auth")

    def test_broken_markers(self):
        with self.assertRaises(NotesError):
            managed("<!-- git-notes:start corrupted -->", "text", "Title")

    def test_markdown_injection(self):
        text = render([classify("feat: <script> [click](evil)", [], "abc")], "v1", "abc", "2026-01-01", False)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("\\[click\\]", text)



@cli.command()
def readme():
    """Display the complete embedded README."""
    click.echo(__doc__, nl=False)


@cli.command(name="self-test")
def self_test():
    """Run the bundled tests in disposable repositories."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for case in (ParserTests, RepositoryTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise click.ClickException("Self-tests failed")


if __name__ == "__main__":
    cli()
