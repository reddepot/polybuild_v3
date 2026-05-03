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
import contextlib
import errno
import json
import shutil
import sys
from pathlib import Path

import structlog

from polybuild.models import BuilderResult, CommitInfo, PolybuildRun


def _copy_cross_device_safe(src: Path, dst: Path) -> None:
    """Copy *src* to *dst*, surviving cross-device link errors.

    Round 10.2 fix [Qwen RX-003 P0]: ``shutil.copy2`` preserves metadata
    via ``os.link``-style fast paths and raises ``OSError(EXDEV)`` when
    the source and destination live on different volumes (common on
    Synology NAS bind mounts). We try ``copy2`` first to retain mtime
    where possible, then fall back to a portable byte stream.

    Round 10.4 fix [Kimi P1]: when the fallback path runs we lose
    ``copy2`` metadata, including the executable bit on shell scripts.
    Re-apply the source mode (permissions only) so a generated script
    keeps its ``+x`` after the cross-device copy.
    """
    try:
        shutil.copy2(src, dst)
    except OSError as e:
        if e.errno not in (errno.EXDEV, errno.ENOTSUP, errno.EPERM):
            raise
        # Cross-device fallback: portable byte-stream copy, no metadata.
        with src.open("rb") as fsrc, dst.open("wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
        with contextlib.suppress(OSError):
            dst.chmod(src.stat().st_mode & 0o777)

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


# Round 10.4 fix [Gemini RX-606-01 + chain]: every git call goes through
# this hardened wrapper so we never expose the orchestrator to:
#   * malicious hooks planted under ``.git/hooks/`` (``--no-verify`` on commit)
#   * a poisoned ``.gitconfig`` in the repo or the user's HOME (
#     ``GIT_CONFIG_NOSYSTEM=1`` + ``HOME=/dev/null``)
#   * an interactive prompt blocking the run (``GIT_TERMINAL_PROMPT=0``)
#   * SSH side-channels triggered by ``[core] sshCommand`` (``GIT_SSH_COMMAND``)
_GIT_ISOLATED_ENV: dict[str, str] = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/dev/null",
    "XDG_CONFIG_HOME": "/dev/null",
    "GIT_SSH_COMMAND": "/bin/false",
}


async def _git(*args: str, cwd: Path = Path()) -> tuple[int, str, str]:
    """Run a git command in an isolated environment.

    Round 10.4: merges ``_GIT_ISOLATED_ENV`` on top of the caller's env so
    polybuild's git operations cannot be redirected by an attacker-planted
    .gitconfig, hooks, or env-borne SSH command.
    """
    import os as _os

    env = {**_os.environ, **_GIT_ISOLATED_ENV}
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
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
            # Round 10.4 fix [Kimi P1]: ignore untracked files (``?? path``)
            # so detect_adr_triggers doesn't fire on a developer's stray
            # ``models.py`` in /tmp.
            if line[:2].strip() == "??":
                continue
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
    # Round 10.2 fix [Kimi RX-005]: SIGINT propagation (start_new_session)
    # + explicit proc.kill() on timeout so a hung ``claude code`` doesn't
    # leave an orphan that survives the run.
    proc: asyncio.subprocess.Process | None = None
    try:
        # Round 10.8 prod-launch fix: claude CLI v2 surface (cf phase_0_spec).
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt,
            "--model", "claude-opus-4-7",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=(sys.platform != "win32"),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
        return stdout.decode().strip()
    except TimeoutError as e:
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()
        logger.warning("adr_generation_timeout", error=str(e))
        return None
    except OSError as e:
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

    # Round 10.4 fix [Kimi P1]: refuse to operate on a non-git directory.
    rc, _, _ = await _git("rev-parse", "--git-dir", cwd=project_root)
    if rc != 0:
        raise RuntimeError(
            f"phase_7_project_root_not_a_git_repo: {project_root}"
        )

    # Round 10.4 fix [ChatGPT P7-401 P0 — index pré-stagé du dev]:
    # ``git commit`` includes the entire index, not just the paths Phase 7
    # added. If the developer had pre-staged work-in-progress, our commit
    # would silently bundle it. Refuse to start when the index is dirty
    # so the developer cannot lose their staged WIP under a polybuild tag.
    rc, _, _ = await _git("diff", "--cached", "--quiet", cwd=project_root)
    if rc != 0:
        raise RuntimeError(
            "phase_7_index_not_clean: refusing to commit pre-staged "
            "developer changes. Stash or unstage them before re-running."
        )

    # Round 10.4 fix [ChatGPT P7-401 + Kimi convergent]: the legacy
    # ``git add -A`` fallback for missing winner_result is a foot-gun
    # that re-introduces the round-8 P0 (embedding dev WIP). Refuse.
    if winner_result is None:
        raise RuntimeError(
            "phase_7_commit requires winner_result (round 8 [P7-isolation]). "
            "The legacy `git add -A` fallback was disabled in round 10.4 "
            "after ChatGPT + Kimi flagged it as a P0 isolation hole."
        )

    tag_pre = f"polybuild/run-{run.run_id}-pre"
    tag_post = f"polybuild/run-{run.run_id}-commit"

    # 1. Pre-commit tag (rollback anchor) — points to current HEAD.
    # Round 10.4 fix [Kimi P0 + ChatGPT P7-405]: previously a failed pre-tag
    # was warn-only, but without an anchor Phase 8 cannot roll back. Also
    # check that the existing tag (if any) does not already point at a
    # different SHA — that would indicate a run_id collision and silently
    # losing the previous run's rollback target.
    rc_existing, existing_sha, _ = await _git(
        "rev-parse", tag_pre, cwd=project_root
    )
    if rc_existing == 0:
        rc_head, head_sha, _ = await _git(
            "rev-parse", "HEAD", cwd=project_root
        )
        if rc_head == 0 and existing_sha.strip() != head_sha.strip():
            raise RuntimeError(
                f"phase_7_pre_tag_collision: {tag_pre} already points at "
                f"{existing_sha.strip()[:12]} (HEAD={head_sha.strip()[:12]}). "
                f"Run-id collision suspected — refusing to overwrite."
            )

    rc, _, stderr = await _git("tag", "-f", tag_pre, cwd=project_root)
    if rc != 0:
        raise RuntimeError(f"phase_7_pre_tag_failed: {stderr}")

    # 2. Round 8 [P7-isolation]: copy + stage ONLY winner artefacts,
    # NOT `git add -A` (which would embed the dev's concurrent edits).
    staged_paths: list[Path] = []
    if winner_result is not None and winner_result.code_dir.exists():
        # winner_result.code_dir is the per-voice worktree under
        # .polybuild/runs/{run_id}/worktrees/{voice_id}/. We mirror it
        # into project_root and add only those paths.
        # Round 10.3 fix [ChatGPT RX-301-04 P0 — validated artefact ≠
        # committed artefact]: ``winner_result.code_dir`` is set to either
        # ``worktree`` or ``worktree/src`` depending on the adapter. When
        # it points at ``worktree/src`` (e.g. claude_code._parse_output
        # set code_dir = worktree / "src"), ``relative_to(code_dir)``
        # strips the ``src/`` prefix and Phase 7 commits files at the
        # project root rather than under ``src/`` — exactly where Phase 6
        # validated them. Recover the prefix when we detect this layout.
        src_root = winner_result.code_dir
        prefix_to_restore = ""
        if src_root.name in {"src", "lib"}:
            prefix_to_restore = src_root.name
        for src_path in src_root.rglob("*"):
            # Round 10.3 fix [Kimi RX-304 P0 — symlink data exfiltration]:
            # ``Path.is_file()`` follows symlinks, so a malicious builder
            # that drops a symlink ``src/data -> /etc/passwd`` (or
            # ``~/.ssh/id_rsa``) would have its TARGET content copied
            # into project_root and committed. Skip symlinks entirely
            # at the staging gate — they have no legitimate purpose in
            # an LLM-generated worktree.
            #
            # Round 10.7 fix [Grok E-01 + Kimi C-06, 3/5 conv P0]: reordered
            # so the ``is_symlink()`` check fires BEFORE ``is_file()``. The
            # previous order was functionally safe (symlinks-to-files passed
            # is_file() then got caught by is_symlink()) but the inverted
            # ordering communicates intent more clearly and removes a
            # superfluous stat() syscall on the resolved target.
            if src_path.is_symlink():
                logger.warning(
                    "phase_7_symlink_skipped_in_worktree",
                    path=str(src_path),
                    target=str(src_path.readlink()),
                )
                continue
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
            target = (
                project_root / prefix_to_restore / rel
                if prefix_to_restore
                else project_root / rel
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_cross_device_safe(src_path, target)
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
                # Round 10.3 fix [Kimi RX-304 P0]: same symlink defence
                # applies on the tests/ side path.
                # Round 10.7 fix [Grok E-02, 3/5 conv P0]: same reorder
                # as the code_dir loop above — is_symlink() must fire
                # before is_file() to make intent unambiguous and to
                # avoid the resolved-target stat() syscall.
                if src_path.is_symlink():
                    logger.warning(
                        "phase_7_symlink_skipped_in_tests",
                        path=str(src_path),
                        target=str(src_path.readlink()),
                    )
                    continue
                if not src_path.is_file():
                    continue
                rel = src_path.relative_to(tests_root)
                if "__pycache__" in rel.parts or str(rel).endswith(".pyc"):
                    continue
                target = project_root / "tests" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_cross_device_safe(src_path, target)
                staged_paths.append(target)

        # Stage exactly the paths we copied — no `-A`.
        if staged_paths:
            # Round 10.4 fix [ChatGPT P7-404 + Qwen P1-02]: a partial
            # ``git add`` would produce a partial commit silently. Batch
            # in chunks of 50 paths and raise on any non-zero rc — better
            # to fail loud than ship half a fix.
            for chunk_start in range(0, len(staged_paths), 50):
                chunk = staged_paths[chunk_start : chunk_start + 50]
                rel_paths = [str(p.relative_to(project_root)) for p in chunk]
                rc, _, stderr = await _git(
                    "add", "--", *rel_paths, cwd=project_root
                )
                if rc != 0:
                    raise RuntimeError(
                        f"phase_7_add_batch_failed: {stderr} "
                        f"(paths={rel_paths[:5]}...)"
                    )

            # Round 10.8 POLYLENS [Gemini GEMINI-01 P0 CRITICAL]: the
            # Round 10.4 ChatGPT P7-403 patch ("lost deletions") assumed
            # the LLM emits the *entire* scope (all of ``src/``, all of
            # ``tests/``). In reality, our adapter contract is
            # ``files: {<path>: <content>}`` — the model writes ONLY the
            # specific module the brief asks for, not the whole repo.
            # Therefore ``tracked_paths - staged_rel`` ≈ the entire repo,
            # and the ``git rm`` call MASSIVELY DELETED legitimate files
            # on every incremental Phase 7 commit. This is data-loss
            # CRITICAL — the patch is removed entirely.
            #
            # If a future use-case wants explicit deletion semantics, the
            # adapter contract should be extended with an explicit
            # ``deleted_files: [<path>, ...]`` field in the JSON payload,
            # so we delete ONLY what the LLM marked as removed — never
            # by exclusion from the staged set.
        else:
            logger.warning("phase_7_no_winner_files_to_stage")

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

    # Round 10.4 fix [Gemini RX-606-02 P1]: a commit message produced by
    # an LLM that starts with ``-`` would be parsed as a CLI flag by some
    # git versions. Pad with a space.
    if commit_msg.startswith("-"):
        commit_msg = " " + commit_msg

    # Round 10.4 fix [Gemini RX-606-01 P0]: --no-verify so a malicious
    # builder cannot plant a ``.git/hooks/pre-commit`` script that runs
    # arbitrary code as the orchestrator. Git hooks have no place in an
    # automated polybuild run.
    rc, stdout, stderr = await _git(
        "commit", "--no-verify", "-m", commit_msg, cwd=project_root
    )
    if rc != 0:
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            # Round 10.4 fix [ChatGPT P7-407]: ``sha=""`` is not a commit.
            # Refuse to mark a run as committed when no commit happened.
            raise RuntimeError(
                "phase_7_no_changes: refusing committed status without "
                "a real commit SHA. Verify Phase 5 actually patched the "
                "winner code and that staging produced new content."
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
                # Round 10.4 fix [ChatGPT P7-406 + Kimi P0 + Qwen P1-03]
                # (3-conv): each ADR-amend git call must check rc.
                # A pre-commit hook rejecting the ADR would otherwise leave
                # ``tag_post`` pointing at the *non*-amended commit, while
                # ``commit_sha`` (read after the no-op amend) would be the
                # old SHA — silent divergence between the run record and
                # the tag.
                rc, _, stderr = await _git(
                    "add", "--", str(adr_path), cwd=project_root
                )
                if rc != 0:
                    raise RuntimeError(f"phase_7_adr_add_failed: {stderr}")
                rc, _, stderr = await _git(
                    "commit", "--amend", "--no-edit", "--no-verify",
                    cwd=project_root,
                )
                if rc != 0:
                    raise RuntimeError(f"phase_7_adr_amend_failed: {stderr}")
                _, sha_out, _ = await _git("rev-parse", "HEAD", cwd=project_root)
                commit_sha = sha_out.strip()
                # Re-tag post (move tag to amended commit)
                rc, _, stderr = await _git(
                    "tag", "-f", tag_post, cwd=project_root
                )
                if rc != 0:
                    raise RuntimeError(
                        f"phase_7_adr_post_tag_failed: {stderr}"
                    )

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
