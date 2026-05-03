"""POLYBUILD v3 — Multi-LLM orchestrated code generation pipeline.

Architecture overview (all phases active as of round 6):
    1. Phase -1: Privacy gate (Presidio + EDS-NLP + heuristic L3)
    2. Phase 0:  Spec generation (Opus 4.7)
    3. Phase 0b: Spec attack (orthogonal challenger)
    4. Phase 1:  Voice selection (matrix + optional 50 LOC probe)
    5. Phase 2:  Parallel generation (3 voices)
    6. Phase 3:  Deterministic scoring
    7. Phase 3b: AST grounding check
    8. Phase 4:  Orthogonal POLYLENS audit
    9. Phase 5:  Critic-Fixer-Verifier triade
    10. Phase 6: General + domain validation gates
    11. Phase 7: Commit + auto-ADR
    12. Phase 8: Production smoke (rollback-on-regression)
"""

from polybuild._version import __version__

__all__ = ["__version__"]
