#!/usr/bin/env python3
"""
Release Preflight Checks

Mild automation around preparing for an Exosphere release.
It is a series of tests that I would have written in a smaller bash
script if portability did not matter.

It will run a series of gates to essentially verify that the repo is in
a state suitable to publish a release, and if it is, it will print
a neat manual checklist of all the stuff the maintainer still has to do
by hand like a caveman banging rocks together.

It is especially useful for ensure the docs and changelog were not
forgotten, and avoiding small details that generate the "oh fuck"
moments 3 hours after a release while I'm on the couch.

Exits non-zero if any gate fails, so a CI job on a ``v*`` tag can
potentially, one day, reuse it for maximum safety -- but for now it's
basically just a local sanity check some guy runs before pushing a tag
and clicking buttons.

Also it's running within the exosphere uv env at all timnes, so we can
absolutely make use of Rich, and we shall.

This is actually INTENDED to be ran through 'poe' due to root path
shenanigans, as always, so don't run it directly, you will ruin
christmas.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from enum import Enum
from pathlib import Path

from packaging.version import InvalidVersion, Version
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_DIR = ROOT / "docs" / "source" / "changelog"

console = Console()


class GateOutcome(Enum):
    """
    Outcome of a gate.
    """

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


# A dirty human still has to do these at this point in time.
# They will be printed at the end of the preflight if it is ready.
MANUAL_STEPS = [
    "Do a final compat pass against the LATEST dependency versions - pipx/uv "
    "tool installs do not pin, so `uv lock --upgrade` then `poe test` now, not "
    "after release.",
    "Confirm the documentation covers any new features or options.",
    "Create a [red]SIGNED[/red] tag `git tag -s vX.Y.Z`.",
    "[red]Rerun the preflight[/red]",
    "Push the tag to origin",
    "Once CI is green on the tag, draft the GitHub release: paste "
    "changelog/<version>.md as the body and attach screenshots/video.",
    "Once satisfied, publish the GitHub Release.",
    "Check build actions for release",
    "Approve the PyPI publish in the GitHub environment (or wait out the "
    "'oh fuck' timer and confirm).",
    "Check the release on PyPI.",
    "Check the live documentation on Read the Docs.",
    "Do a test upgrade on a real system.",
    "Congratulations: You have a release!",
]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a command at the repo root, capturing output."""
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def project_version() -> str:
    """The version declared in pyproject.toml (authoritative source)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


## THE GATES ##


def gate_version_stable(version: Version) -> tuple[GateOutcome, str]:
    if version.is_devrelease or version.is_prerelease:
        return (
            GateOutcome.FAIL,
            f"'{version}' is a dev/pre-release - bump to a stable version",
        )
    return GateOutcome.PASS, str(version)


def gate_changelog_present(version: Version) -> tuple[GateOutcome, str]:
    base = version.base_version
    path = CHANGELOG_DIR / f"{base}.md"
    rel = path.relative_to(ROOT).as_posix()
    if path.exists():
        return GateOutcome.PASS, rel
    return GateOutcome.FAIL, f"missing '{rel}' - write the release notes first"


def gate_lockfile_current() -> tuple[GateOutcome, str]:
    proc = _run("uv", "lock", "--check")
    if proc.returncode == 0:
        return GateOutcome.PASS, "uv.lock matches pyproject.toml"
    return (
        GateOutcome.FAIL,
        "uv.lock is stale - run 'uv lock' and re-test against latest deps",
    )


def gate_worktree_clean() -> tuple[GateOutcome, str]:
    proc = _run("git", "status", "--porcelain")
    dirty = [line for line in proc.stdout.splitlines() if line.strip()]
    if not dirty:
        return GateOutcome.PASS, "no uncommitted changes"
    return (
        GateOutcome.FAIL,
        f"{len(dirty)} uncommitted change(s) - commit or stash first",
    )


def gate_on_main_branch() -> tuple[GateOutcome, str]:
    branch = _run("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch == "main":
        return GateOutcome.PASS, "on main"
    return GateOutcome.FAIL, f"on '{branch}' - merge the prep first"


def gate_tag_signed(version: Version) -> tuple[GateOutcome, str]:
    tag = f"v{version.base_version}"
    exists = (
        _run("git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}").returncode == 0
    )
    if not exists:
        # The tag not existing is not a failure, because the maintainer
        # is expected to create it AFTER doing all sorts of manual
        # checks and confirmations, and then re-run the preflight.
        return (
            GateOutcome.WARN,
            f"'{tag}' not created yet - create it signed: 'git tag -s {tag}'",
        )
    if _run("git", "tag", "-v", tag).returncode == 0:
        return GateOutcome.PASS, f"'{tag}' exists and its signature verifies"
    return (
        GateOutcome.FAIL,
        f"'{tag}' exists but is NOT signed - recreate it with 'git tag -s'",
    )


def main() -> int:
    raw_version = project_version()

    # Validate version string up front, so it doesn't break all the
    # gates at runtime because there's garbage in it.
    try:
        version = Version(raw_version)
    except InvalidVersion:
        console.rule("[dark_orange3]Exosphere release preflight[/dark_orange3]")
        console.print(
            "  [red]FAIL[/]  [bold]Version is stable:[/] "
            f"{raw_version!r} is not a valid version - check pyproject.toml"
        )
        console.print("\n[red]  1 gate(s) failed - not ready for release.[/]\n")
        console.print("All remaining gates skipped due to invalid version string.")
        return 1

    console.rule(
        f"[dark_orange3]Exosphere release preflight - 'v{version.base_version}'[/dark_orange3]"
    )

    gates = [
        ("Version is stable", gate_version_stable(version)),
        ("Changelog present", gate_changelog_present(version)),
        ("Lockfile current", gate_lockfile_current()),
        ("Working tree clean", gate_worktree_clean()),
        ("On main branch", gate_on_main_branch()),
        ("Release tag", gate_tag_signed(version)),
    ]

    marks = {
        GateOutcome.PASS: "[green]PASS[/]",
        GateOutcome.WARN: "[yellow]WARN[/]",
        GateOutcome.FAIL: "[red]FAIL[/]",
    }

    failed = warned = 0
    for name, (result, detail) in gates:
        console.print(f"  {marks[result]}  [bold]{name}:[/] {detail}")
        if result is GateOutcome.FAIL:
            failed += 1
        elif result is GateOutcome.WARN:
            warned += 1

    if failed:
        console.print(f"\n[red]  {failed} gate(s) failed - not ready for release.[/]\n")
        return 1

    if warned:
        console.print(
            f"\n[yellow]  No blockers, but {warned} item(s) still pending.[/]\n"
            "Remaining manual steps:\n"
        )
    else:
        console.print("\n[green]  All gates passed.[/] Remaining manual steps:\n")

    for index, step in enumerate(MANUAL_STEPS, start=1):
        console.print(f"  [bold]{index}.[/] {step}")
    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
