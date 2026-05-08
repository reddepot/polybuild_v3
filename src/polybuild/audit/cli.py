"""CLI surface for the audit subsystem (M2C.1).

Exposes ``polybuild audit {drain,status,digest,dry-run,configure}``.
The parent CLI registers this Typer app via ``app.add_typer(audit_app,
name="audit")``.

Verbs:

  * ``drain``   — consume the queue, run ``audit_commit`` on each entry,
                  route findings via ``notify_findings``.
  * ``status``  — backlog counts by severity, plus queue length.
  * ``digest``  — multi-line markdown summary (P0/P1/P2/P3 grouped).
  * ``dry-run`` — same as ``drain`` but ``persist=False`` and a stub
                  voice caller; no LLM call, no backlog write.
  * ``configure rotation`` — show / reset the W+CN voice rotation.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table

from polybuild.audit.backlog import read_backlog
from polybuild.audit.cost_log import summarize_costs
from polybuild.audit.notifier import build_digest, notify_findings
from polybuild.audit.queue import drain_queue, mark_entry_processed, read_queue
from polybuild.audit.rotation import (
    CHINESE_VOICES,
    WESTERN_VOICES,
    pick_voice_pair,
    reset_rotation,
)
from polybuild.audit.runner import audit_commit

audit_app = typer.Typer(
    help="POLYLENS async audit — drain, status, digest, dry-run, configure.",
    no_args_is_help=True,
)
console = Console()


# ────────────────────────────────────────────────────────────────
# ENQUEUE
# ────────────────────────────────────────────────────────────────


@audit_app.command("enqueue")
def cmd_enqueue(
    sha: Annotated[
        str,
        typer.Option("--sha", help="Commit SHA to enqueue."),
    ],
    repo: Annotated[
        str,
        typer.Option("--repo", help="Absolute repo path."),
    ] = ".",
    branch: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name (informational)."),
    ] = None,
) -> None:
    """Append a single commit to the audit queue.

    Used by the post-commit git hook (``scripts/install_audit_hook.sh``)
    immediately after a commit lands. Safe to call repeatedly with the
    same SHA — drain dedups via the backlog 7-day window, so a duplicate
    enqueue at most wastes one audit cycle.
    """
    from pathlib import Path

    from polybuild.audit.queue import AuditQueueEntry, append_queue_entry

    entry = AuditQueueEntry(
        commit_sha=sha,
        repo_path=Path(repo).resolve(),
        branch=branch,
    )
    append_queue_entry(entry)
    console.print(
        f"[green]enqueued[/green] {sha[:12]} ({entry.repo_path})"
    )


# ────────────────────────────────────────────────────────────────
# DRAIN
# ────────────────────────────────────────────────────────────────


@audit_app.command("drain")
def cmd_drain() -> None:
    """Consume the queue, run audits, route findings.

    No-op when the queue is empty (zero exit code so the post-commit
    hook can call ``polybuild audit drain --async &`` without spamming
    a "nothing to do" line on every commit).
    """
    asyncio.run(_drain_async(persist=True))


async def _drain_async(*, persist: bool) -> None:
    from polybuild.audit.backlog import Severity

    entries = list(drain_queue())
    if not entries:
        console.print("[dim]audit queue empty[/dim]")
        return

    total_findings = 0
    counts_total: dict[Severity, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    for entry in entries:
        console.print(
            f"[cyan]auditing[/cyan] {entry.commit_sha[:12]} "
            f"@ {entry.repo_path}"
        )
        findings = await audit_commit(entry)
        total_findings += len(findings)
        if findings:
            counts = notify_findings(findings, persist=persist)
            for sev, count in counts.items():
                counts_total[sev] = counts_total.get(sev, 0) + count
        # POLYLENS-FIX-3 P1: only mark this entry processed AFTER the
        # full audit + notification pipeline completed without raising.
        # If we crashed above, the entry stays in the queue and the
        # next ``polybuild audit drain`` will replay it.
        mark_entry_processed(entry)

    table = Table(title=f"Drain summary ({len(entries)} commit(s))")
    table.add_column("Severity", style="cyan")
    table.add_column("Count", justify="right")
    for sev_key, count in counts_total.items():
        table.add_row(sev_key, str(count))
    table.add_row("[bold]Total[/bold]", f"[bold]{total_findings}[/bold]")
    console.print(table)


# ────────────────────────────────────────────────────────────────
# STATUS
# ────────────────────────────────────────────────────────────────


@audit_app.command("status")
def cmd_status() -> None:
    """Show queue length + backlog counts by severity."""
    queue_len = len(read_queue())
    backlog = read_backlog()

    by_sev = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for f in backlog:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1

    table = Table(title="POLYLENS audit status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("queue_pending", str(queue_len))
    table.add_row("backlog_total", str(len(backlog)))
    for sev, count in by_sev.items():
        table.add_row(f"backlog_{sev}", str(count))
    console.print(table)


# ────────────────────────────────────────────────────────────────
# DIGEST
# ────────────────────────────────────────────────────────────────


@audit_app.command("digest")
def cmd_digest(
    since: Annotated[
        str,
        typer.Option("--since", help="yesterday | week | month"),
    ] = "yesterday",
) -> None:
    """Print a markdown-ish digest of the backlog from ``--since``."""
    if since not in ("yesterday", "week", "month"):
        raise typer.BadParameter(
            f"invalid --since={since!r}. Use 'yesterday', 'week' or 'month'."
        )
    window: Literal["yesterday", "week", "month"] = since  # type: ignore[assignment]
    text = build_digest(since=window)
    console.print(text)


# ────────────────────────────────────────────────────────────────
# CACHE
# ────────────────────────────────────────────────────────────────


@audit_app.command("cache")
def cmd_cache(
    action: Annotated[
        str,
        typer.Argument(help="stats | clear"),
    ] = "stats",
) -> None:
    """Inspect or clear the persistent LLM response cache (FEAT-3).

    ``stats``  → row count, distinct voices, size on disk.
    ``clear``  → wipe every entry (vacuum).
    """
    from polybuild.audit.cache import cache_clear, cache_stats

    if action == "stats":
        stats = cache_stats()
        table = Table(title="LLM response cache")
        table.add_column("Field", style="cyan")
        table.add_column("Value", justify="right")
        for k, v in stats.items():
            table.add_row(k, str(v))
        console.print(table)
    elif action == "clear":
        n = cache_clear()
        console.print(f"[yellow]cache cleared[/yellow]: {n} entries removed")
    else:
        raise typer.BadParameter(
            f"unknown action {action!r}. Use 'stats' or 'clear'."
        )


# ────────────────────────────────────────────────────────────────
# COST
# ────────────────────────────────────────────────────────────────


@audit_app.command("cost")
def cmd_cost(
    since: Annotated[
        str,
        typer.Option("--since", help="yesterday | week | month | all"),
    ] = "week",
) -> None:
    """Print a per-voice cost summary for the chosen window.

    Western voices (codex / gemini / kimi via local CLI) ride on the
    user's existing subscription and have $0 marginal cost — they do
    not appear in this log. The summary covers OpenRouter (Chinese)
    voices only.
    """
    if since not in ("yesterday", "week", "month", "all"):
        raise typer.BadParameter(
            f"invalid --since={since!r}. Use 'yesterday', 'week', "
            "'month' or 'all'."
        )
    window: Literal["yesterday", "week", "month", "all"] = since  # type: ignore[assignment]
    text = summarize_costs(window=window)
    console.print(text)


# ────────────────────────────────────────────────────────────────
# DRY RUN
# ────────────────────────────────────────────────────────────────


@audit_app.command("dry-run")
def cmd_dry_run() -> None:
    """Same as ``drain`` but ``persist=False`` and a stub voice caller.

    Useful for checking the queue plumbing end-to-end without firing
    real LLM calls or polluting the backlog. Each queued commit is
    consumed (so the queue empties — re-enqueue manually if you want
    to test the real drain afterwards) and the routing is exercised
    against canned findings.
    """
    asyncio.run(_dry_run_async())


async def _dry_run_async() -> None:
    entries = list(drain_queue())
    if not entries:
        console.print("[dim]audit queue empty[/dim]")
        return

    async def _stub_caller(voice_id: str, _prompt: str) -> str:
        # Empty output → zero findings per voice. Lets us validate
        # rotation + queue handling without making any external call.
        del voice_id
        return ""

    for entry in entries:
        console.print(
            f"[yellow]dry-run audit[/yellow] {entry.commit_sha[:12]}"
        )
        findings = await audit_commit(entry, voice_caller=_stub_caller)
        notify_findings(findings, persist=False)


# ────────────────────────────────────────────────────────────────
# CONFIGURE
# ────────────────────────────────────────────────────────────────


configure_app = typer.Typer(help="Configure audit subsystem.", no_args_is_help=True)
audit_app.add_typer(configure_app, name="configure")


@configure_app.command("rotation")
def cmd_configure_rotation(
    reset: Annotated[
        bool,
        typer.Option("--reset", help="Reset rotation to head of each pool."),
    ] = False,
) -> None:
    """Show or reset the Western+Chinese voice rotation pool."""
    if reset:
        reset_rotation()
        console.print("[green]Rotation reset to head of each pool.[/green]")
    pair = pick_voice_pair()
    table = Table(title="Voice rotation")
    table.add_column("Pool", style="cyan")
    table.add_column("Voices")
    table.add_column("Next pick")
    table.add_row("Western", ", ".join(WESTERN_VOICES), pair.western)
    table.add_row("Chinese", ", ".join(CHINESE_VOICES), pair.chinese)
    console.print(table)
    console.print(
        "[dim]Note: ``next pick`` advances the rotation by one. "
        "Re-run to see the following pair.[/dim]"
    )


__all__ = ["audit_app"]
