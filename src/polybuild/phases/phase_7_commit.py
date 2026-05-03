"""Phase 7 — Git commit + automatic ADR generation.

Strategy (acquis convergent rounds 1-4):
    - Tag pre-commit (rollback anchor): polybuild/run-{run_id}-pre
    - Commit message includes co-author = winning voice
    - Tag post-commit: polybuild/run-{run_id}-commit
    - ADR auto-generated only when ADR_TRIGGERS match

Rollback procedure (manual or via Phase 8 prod_smoke):
    git reset --hard polybuild/run-{run_id}-pre

Round 8 fix [P7-isolation] (ChatGPT P0, 90% confidence):
    Previous version did `git add -A` in project_root, which embedded ANY
    changes the developer had made in their editor during the 30-45 min
    background run. Catastrophic when running in tmux: the dev keeps
    coding, polybuild commits their work-in-progress, and a Phase 8
    rollback erases it.

    Now Phase 7 takes the explicit `winner_result.code_dir` (read-only
    artefact from Phase 2), copies the files into project_root with
    rsync-like semantics, and `git add` ONLY those paths. The dev's
    concurrent work in other parts of the repo is preserved.

Round 8 fix [P7-tag-force] (Grok P1):
    `git tag tag_post` was called without `-f` and without checking rc.
    On `--run-id` reuse, the tag already exists → silent failure → tag
    points to old SHA → future rollback targets stale commit.
    Now `tag -f` + rc check.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import structlog

from polybuild.models import BuilderResult, CommitInfo, PolybuildRun

logger = structlog.get_logger()


# ────────────────────────────────────────────────────────────────
# ADR TRIGGERS (acquis Round 3)
# ────────────────────────────────────────────────────────────────

ADR_TRIGGERS = {
    "schema_db_change",
    "new_dependency",
    "architecture_pattern_change",
    "breaking_api_change",
    "polylens_p0_resolved",
    "domain_gate_change",
    "privacy_gate_rule_change",
}


# ────────────────────────────────────────────────────────────────
# GIT HELPERS
# ────────────────────────────────────────────────────────────────


async def _git(*args: str, cwd: Path = Path()) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(), stderr.decode()


async def _list_changed_files(cwd: Path = Path()) -> list[Path]:
    """Return list of files changed (staged + unstaged)."""
    rc, stdout, _ = await _git("status", "--porcelain", cwd=cwd)
    if rc != 0:
        return []
    files: list[Path] = []
    for line in stdout.splitlines():
        # format: "XY path/to/file"
        if len(line) >= 4:
            files.append(Path(line[3:]))
    return files


# ────────────────────────────────────────────────────────────────
# ADR GENERATION
# ────────────────────────────────────────────────────────────────


async def _next_adr_id(project_root: Path) -> str:
    """Find next ADR ID (0001, 0002, ...)."""
    adr_dir = project_root / "docs" / "adr"
    if not adr_dir.exists():
        return "0001"
    existing = sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md"))
    if not existing:
        return "0001"
    last = existing[-1].name
    last_id = int(last.split("-", 1)[0])
    return f"{last_id + 1:04d}"


async def _generate_adr(
    project_root: Path,
    run: PolybuildRun,
    trigger: str,
) -> str | None:
    """Use Claude Opus 4.7 to generate ADR text."""
    prompt = f"""You are generating an Architecture Decision Record (ADR).

Trigger: {trigger}
Run summary:
{json.dumps(run.model_dump(mode='json'), indent=2, ensure_ascii=False)}

Output ONLY the ADR markdown (no prose around it), structured:
# ADR-XXXX: <Title>
## Status
Accepted / Proposed / Deprecated
## Context
<2-3 paragraphs>
## Decision
<what was decided>
## Consequences
<positive and negative>
## Alternatives considered
<list>
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "code",
            "--model", "opus-4.7",
            "--prompt", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        return stdout.decode().strip()
    except (TimeoutError, OSError) as e:
        logger.warning("adr_generation_failed", error=str(e))
        return None


def detect_adr_triggers(run: PolybuildRun, changed_files: list[Path]) -> list[str]:
    """Heuristic detection of which ADR triggers apply to this run."""
    triggers: list[str] = []

    file_names = {f.name for f in changed_files}
    if any(f.endswith((".sql", "schema.py", "models.py")) for f in file_names):
        triggers.append("schema_db_change")

    if "pyproject.toml" in file_names:
        triggers.append("new_dependency")

    if run.audit_findings_by_severity.get("P0", 0) > 0:
        triggers.append("polylens_p0_resolved")

    return triggers


# ────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────


async def phase_7_commit(
    run: PolybuildRun,
    project_root: Path = Path(),
    skip_adr: bool = False,
    winner_result: BuilderResult | None = None,
) -> CommitInfo:
    """Commit changes, create rollback tags, generate ADR if applicable.

    Args:
        run: PolybuildRun metadata.
        project_root: Repo root where the commit will land.
        skip_adr: If True, skip ADR generation (used for tests).
        winner_result: BuilderResult from the winning voice. Required for
                       round-8 isolation: the function copies files from
                       winner_result.code_dir into project_root rather than
                       using `git add -A`. None is accepted for backward
                       compatibility but logs a warning.

    Round 8 fix [P7-isolation]: explicit per-file copy + add prevents
    embedding the developer's concurrent work-in-progress.
    """
    logger.info("phase_7_start", run_id=run.run_id)

    tag_pre = f"polybuild/run-{run.run_id}-pre"
    tag_post = f"polybuild/run-{run.run_id}-commit"

    # 1. Pre-commit tag (rollback anchor) — points to current HEAD.
    # Round 8: `-f` is intentional here so a re-run with the same run_id
    # re-anchors the rollback target rather than failing silently.
    rc, _, stderr = await _git("tag", "-f", tag_pre, cwd=project_root)
    if rc != 0:
        logger.warning("phase_7_pre_tag_failed", stderr=stderr)

    # 2. Round 8 [P7-isolation]: copy + stage ONLY winner artefacts,
    # NOT `git add -A` (which would embed the dev's concurrent edits).
    staged_paths: list[Path] = []
    if winner_result is not None and winner_result.code_dir.exists():
        # winner_result.code_dir is the per-voice worktree under
        # .polybuild/runs/{run_id}/worktrees/{voice_id}/. We mirror it
        # into project_root and add only those paths.
        src_root = winner_result.code_dir
        for src_path in src_root.rglob("*"):
            if not src_path.is_file():
                continue
            # Skip git internals and caches in the worktree
            rel = src_path.relative_to(src_root)
            rel_str = str(rel)
            if (
                rel_str.startswith(".git/")
                or "__pycache__" in rel.parts
                or rel_str.endswith(".pyc")
            ):
                continue
            target = project_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, target)
            staged_paths.append(target)

        # Also include the tests dir if it's separate from code_dir
        if (
            winner_result.tests_dir.exists()
            and winner_result.tests_dir != winner_result.code_dir
            and winner_result.tests_dir.is_relative_to(
                winner_result.code_dir.parent
            )
        ):
            tests_root = winner_result.tests_dir
            for src_path in tests_root.rglob("*"):
                if not src_path.is_file():
                    continue
                rel = src_path.relative_to(tests_root)
                if "__pycache__" in rel.parts or str(rel).endswith(".pyc"):
                    continue
                target = project_root / "tests" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, target)
                staged_paths.append(target)

        # Stage exactly the paths we copied — no `-A`.
        if staged_paths:
            for p in staged_paths:
                rel_to_root = p.relative_to(project_root)
                rc, _, stderr = await _git(
                    "add", "--", str(rel_to_root), cwd=project_root
                )
                if rc != 0:
                    logger.warning(
                        "phase_7_add_failed", path=str(rel_to_root), stderr=stderr
                    )
        else:
            logger.warning("phase_7_no_winner_files_to_stage")
    else:
        # Backward-compat fallback: only used if caller didn't pass winner_result.
        # Logs a warning because this path embeds dev work-in-progress.
        logger.warning(
            "phase_7_isolation_disabled_using_add_minus_A",
            hint=(
                "Round 8 [P7-isolation]: pass winner_result to scope the commit "
                "to LLM-generated artefacts only. `git add -A` may embed the "
                "developer's concurrent uncommitted work."
            ),
        )
        rc, _, stderr = await _git("add", "-A", cwd=project_root)
        if rc != 0:
            raise RuntimeError(f"git add failed: {stderr}")

    # 3. List changed files for ADR detection
    changed = await _list_changed_files(project_root)

    # 4. Build commit message
    summary = run.profile_id.replace("_", " ").title()
    winner = run.winner_voice_id or "polybuild"
    commit_msg = f"""polybuild: {summary} [run-{run.run_id}]

Profile: {run.profile_id}
Winner voice: {winner}
Findings resolved: P0={run.audit_findings_by_severity.get('P0', 0)} P1={run.audit_findings_by_severity.get('P1', 0)}

Co-authored-by: {winner} <polybuild@reddie.local>
Polybuild-run: {run.run_id}
Polybuild-spec-hash: {run.spec_hash[:12]}
"""

    rc, stdout, stderr = await _git("commit", "-m", commit_msg, cwd=project_root)
    if rc != 0:
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            logger.warning("phase_7_no_changes")
            return CommitInfo(
                sha="",
                message=commit_msg,
                tag_pre=tag_pre,
                tag_post=tag_post,
                files_changed=[],
            )
        raise RuntimeError(f"git commit failed: {stderr}")

    # 5. Get commit SHA
    _, sha_out, _ = await _git("rev-parse", "HEAD", cwd=project_root)
    commit_sha = sha_out.strip()

    # 6. Post-commit tag.
    # Round 8 fix [P7-tag-force] (Grok P1): use `-f` and check rc. Previous
    # version silently failed on --run-id reuse, leaving the tag pointing to
    # the OLD commit → future rollback would target stale code.
    rc, _, stderr = await _git("tag", "-f", tag_post, cwd=project_root)
    if rc != 0:
        raise RuntimeError(f"post-commit tag failed: {stderr}")

    # 7. ADR if applicable
    adr_id: str | None = None
    if not skip_adr:
        triggers = detect_adr_triggers(run, changed)
        if triggers:
            adr_text = await _generate_adr(project_root, run, ", ".join(triggers))
            if adr_text:
                adr_id = await _next_adr_id(project_root)
                adr_dir = project_root / "docs" / "adr"
                adr_dir.mkdir(parents=True, exist_ok=True)
                adr_path = adr_dir / f"{adr_id}-polybuild-run-{run.run_id}.md"
                adr_path.write_text(adr_text)
                # Amend commit to include ADR
                await _git("add", str(adr_path), cwd=project_root)
                await _git("commit", "--amend", "--no-edit", cwd=project_root)
                _, sha_out, _ = await _git("rev-parse", "HEAD", cwd=project_root)
                commit_sha = sha_out.strip()
                # Re-tag post (move tag to amended commit)
                await _git("tag", "-f", tag_post, cwd=project_root)

    logger.info(
        "phase_7_done",
        run_id=run.run_id,
        sha=commit_sha[:12],
        adr_id=adr_id,
        files=len(changed),
    )

    return CommitInfo(
        sha=commit_sha,
        message=commit_msg,
        tag_pre=tag_pre,
        tag_post=tag_post,
        files_changed=changed,
        adr_id=adr_id,
    )
