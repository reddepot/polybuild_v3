"""POLYBUILD v3 CLI.

Commands:
    polybuild run --brief <file> --profile <name>     Run the full pipeline
    polybuild status <run_id>                         Show status of a run
    polybuild logs <run_id>                           Show logs (last 200 lines)
    polybuild abort <run_id>                          Abort a running run
    polybuild test-cli                                Smoke test all CLI adapters
    polybuild stats --profile <name> --last <N>       Show learning stats
    polybuild init                                    Bootstrap a new project
    polybuild resume --checkpoint <run_id>            Resume from checkpoint
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from polybuild import __version__
from polybuild.audit.cli import audit_app
from polybuild.orchestrator import (
    ConsensusPipeline,
    PipelineStrategy,
    SoloPipeline,
    run_polybuild,
)

app = typer.Typer(help="POLYBUILD v3 — Multi-LLM orchestrated code generation")
app.add_typer(audit_app, name="audit")
console = Console()


@app.callback()
def callback() -> None:
    """POLYBUILD v3 CLI."""


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"POLYBUILD v{__version__}")


def _build_consensus_strategy(scorer_name: str) -> PipelineStrategy:
    """Build a ``ConsensusPipeline`` with the requested scorer (M2A.4).

    Raises ``typer.BadParameter`` for unknown scorer names so the user
    sees a clean CLI error rather than a stack trace. The DEVCODE
    scorer is loaded lazily so callers that stick with the naive path
    never pay the import cost.
    """
    if scorer_name == "naive":
        return ConsensusPipeline()
    if scorer_name == "devcode":
        # POLYLENS-FIX-7 P2: ``DevcodeScorer.__init__`` itself imports
        # ``devcode.reputation`` to build the default in-memory store, so
        # an ImportError can also escape at instantiation time. Wrap both
        # the module import AND the constructor call in the same
        # BadParameter-producing try/except so the CLI never leaks a
        # raw traceback when the optional extra is missing.
        try:
            from polybuild.scoring.devcode_scorer import DevcodeScorer

            scorer = DevcodeScorer()
        except ImportError as e:
            raise typer.BadParameter(
                "--scorer=devcode requires the optional [devcode] extra. "
                "Install it with ``pip install -e \".[devcode]\"`` (devcode "
                "lives at ~/Developer/projects/devcode by default — see "
                "pyproject.toml)."
            ) from e
        return ConsensusPipeline(scorer=scorer)
    if scorer_name == "devcode-shadow":
        # FEAT-2: shadow scorer always returns NaiveScorer's winner (no
        # behavior change) and logs DEVCODE divergence to
        # ``~/.polybuild/audit/scorer_shadow.jsonl`` for calibration.
        try:
            from polybuild.scoring.shadow_scorer import ShadowScorer
        except ImportError as e:
            raise typer.BadParameter(
                "--scorer=devcode-shadow requires the optional [devcode] "
                "extra. Install it with ``pip install -e \".[devcode]\"``."
            ) from e
        return ConsensusPipeline(scorer=ShadowScorer())
    raise typer.BadParameter(
        f"unknown --scorer={scorer_name!r}. "
        "Use 'naive', 'devcode' or 'devcode-shadow'."
    )


@app.command()
def run(
    brief: Path = typer.Option(
        ...,
        "--brief",
        "-b",
        "--spec",  # Round 5 fix [M] (Audit 4 P0): SKILL.md uses --spec
        help="Brief file (.md or .yaml). --spec is an alias.",
    ),
    profile: str = typer.Option(
        "module_standard_known",
        "--profile",
        "-p",
        help="Routing profile id",
    ),
    project_root: Path = typer.Option(Path(), "--project-root", "-r"),
    skip_commit: bool = typer.Option(False, "--no-commit", help="Dry run (no Git commit)"),
    skip_smoke: bool = typer.Option(
        False, "--no-smoke", help="Skip Phase 8 production smoke"
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Override the auto-generated run id (used by /polybuild)"
    ),
    solo: bool = typer.Option(
        False,
        "--solo",
        help=(
            "Use the single-voice short-circuit pipeline (skip Phase 2/3/5 "
            "consensus). Faster, cheaper, no parallel generation."
        ),
    ),
    scorer: str = typer.Option(
        "naive",
        "--scorer",
        help=(
            "Phase 3 scoring strategy for the consensus pipeline. "
            "``naive`` (default) keeps the historical gate-based scorer + "
            "eligibility-filter winner selection. ``devcode`` enables "
            "DEVCODE-Vote v1 arbitration (Schulze pondere bayesien Glicko-2). "
            "``devcode-shadow`` runs both in parallel — naive picks the "
            "live winner, DEVCODE divergences logged to "
            "~/.polybuild/audit/scorer_shadow.jsonl for calibration. "
            "Requires the optional ``[devcode]`` extra for the latter two. "
            "Ignored when --solo is set (solo skips Phase 3)."
        ),
    ),
) -> None:
    """Run the full POLYBUILD pipeline.

    `--spec` and `--brief` are interchangeable.
    """
    if not brief.exists():
        console.print(f"[red]Brief file not found: {brief}[/red]")
        raise typer.Exit(1)

    brief_text = brief.read_text()

    # Pick the pipeline strategy. ``run_polybuild`` defaults to
    # ConsensusPipeline when ``strategy=None``; we make the choice
    # explicit here so the CLI can echo it in the run banner.
    if solo:
        if scorer != "naive":
            console.print(
                f"[yellow]warning: --scorer={scorer} ignored "
                "(solo mode skips Phase 3 scoring)[/yellow]"
            )
        strategy: PipelineStrategy = SoloPipeline()
    else:
        strategy = _build_consensus_strategy(scorer)

    console.print(f"[cyan]POLYBUILD v{__version__}[/cyan]")
    console.print(f"  Profile: {profile}")
    console.print(f"  Brief: {brief}")
    console.print(f"  Project: {project_root.absolute()}")
    console.print(f"  Strategy: {strategy.name}")
    if not solo:
        console.print(f"  Scorer: {scorer}")
    console.print(f"  Skip commit: {skip_commit}")
    console.print(f"  Skip smoke: {skip_smoke}")
    console.print()

    project_ctx: dict[str, Any] = {}
    if run_id is not None:
        project_ctx["run_id_override"] = run_id

    result = asyncio.run(
        run_polybuild(
            brief=brief_text,
            profile_id=profile,
            project_root=project_root,
            skip_commit=skip_commit,
            skip_smoke=skip_smoke,
            project_ctx=project_ctx or None,
            strategy=strategy,
        )
    )

    # Pretty print result
    table = Table(title=f"Run {result.run_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Status", result.final_status)
    table.add_row("Winner", result.winner_voice_id or "—")
    table.add_row("Duration", f"{result.duration_total_sec:.1f}s")
    table.add_row("Commit SHA", (result.commit_sha or "—")[:12])
    console.print(table)

    if result.final_status != "committed":
        raise typer.Exit(1)


@app.command()
def status(run_id: str) -> None:
    """Show the status of a run by id."""
    run_dir = Path(".polybuild") / "runs" / run_id
    if not run_dir.exists():
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    final = run_dir / "polybuild_run.json"
    if final.exists():
        data = json.loads(final.read_text())
        table = Table(title=f"Run {run_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        for key in ("final_status", "profile_id", "winner_voice_id",
                    "duration_total_sec", "commit_sha", "spec_hash"):
            table.add_row(key, str(data.get(key, "—")))
        console.print(table)
    else:
        # Look at checkpoints
        cp_dir = Path(".polybuild") / "checkpoints"
        ckpts = sorted(cp_dir.glob(f"{run_id}_*.json"))
        if ckpts:
            console.print(f"[yellow]Run in progress, last checkpoint: {ckpts[-1].name}[/yellow]")
        else:
            console.print(f"[yellow]No checkpoints found for {run_id}[/yellow]")


@app.command(name="test-cli")
def test_cli() -> None:
    """Smoke test all CLI adapters and report which are available."""
    from polybuild.adapters import (
        ClaudeCodeAdapter,
        CodexCLIAdapter,
        GeminiCLIAdapter,
        KimiCLIAdapter,
        MistralEUAdapter,
        OllamaLocalAdapter,
        OpenRouterAdapter,
    )

    adapters = [
        ClaudeCodeAdapter("opus-4.7"),
        ClaudeCodeAdapter("sonnet-4.6"),
        CodexCLIAdapter("gpt-5.5"),
        GeminiCLIAdapter("gemini-3.1-pro-preview"),
        KimiCLIAdapter("k2.6"),
        OpenRouterAdapter("deepseek/deepseek-v4-pro", "deepseek"),
        OpenRouterAdapter("x-ai/grok-4.20", "xai"),
        MistralEUAdapter("devstral-2"),
        OllamaLocalAdapter("qwen2.5-coder:14b-int4"),
    ]

    table = Table(title="CLI Adapters Status")
    table.add_column("Adapter", style="cyan")
    table.add_column("Available")
    table.add_column("Smoke Test")

    async def _check_all() -> list[tuple[str, bool, bool]]:
        results = []
        for a in adapters:
            avail = await a.is_available()
            smoke = await a.smoke_test() if avail else False
            results.append((a.name, avail, smoke))
        return results

    results = asyncio.run(_check_all())
    for name, avail, smoke in results:
        avail_str = "[green]✓[/green]" if avail else "[red]✗[/red]"
        smoke_str = "[green]✓[/green]" if smoke else "[red]✗[/red]"
        table.add_row(name, avail_str, smoke_str)
    console.print(table)


@app.command()
def stats(
    profile: str | None = typer.Option(None, "--profile", "-p"),
    last_n: int = typer.Option(20, "--last", "-n"),
) -> None:
    """Show learning stats per voice (TODO Phase E)."""
    console.print("[yellow]TODO: implement stats aggregation (Phase E)[/yellow]")


@app.command()
def init() -> None:
    """Bootstrap a new project (TODO Phase F)."""
    console.print("[yellow]TODO: implement polybuild init (Phase F)[/yellow]")


@app.command()
def resume(checkpoint: str = typer.Option(..., "--checkpoint", "-c")) -> None:
    """Resume from a checkpoint (TODO Phase G)."""
    console.print(f"[yellow]TODO: resume from {checkpoint} (Phase G)[/yellow]")


if __name__ == "__main__":
    app()
