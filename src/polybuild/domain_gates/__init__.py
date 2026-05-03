"""Domain-specific gates for Phase 6 (round 4 finalisé).

Each gate validates a specific domain concern (MCP, SQLite, Qdrant, FTS5, RAG).
Activated per profile via routing.yaml `domain_gates` mapping.

Convergence round 4 (5/6, DeepSeek nuance vers warn pour SQLite optionnel):
    - All gates strictly BLOCK Phase 7 commit on failure.
    - Optional warnings reserved for P2/P3 documentation findings.
    - MCP gate: spawn server in stdio/JSON-RPC mode, send initialize + tools/list,
      validate tool schemas via Pydantic, terminate cleanly.
    - SQLite gate: PRAGMA integrity_check + WAL mode + schema diff.
    - Qdrant gate: get_collection + dimension match + sample query.
    - FTS5 gate: 3 golden queries with expected hits.
    - RAG gate: chunk hash stability + Qdrant count + golden retrieval check.
"""

from polybuild.domain_gates.validate_fts5 import validate_fts5_golden
from polybuild.domain_gates.validate_mcp import validate_mcp_server
from polybuild.domain_gates.validate_qdrant import validate_qdrant_collection
from polybuild.domain_gates.validate_rag import validate_rag_smoke
from polybuild.domain_gates.validate_sqlite import validate_sqlite_db

__all__ = [
    "validate_fts5_golden",
    "validate_mcp_server",
    "validate_qdrant_collection",
    "validate_rag_smoke",
    "validate_sqlite_db",
]
