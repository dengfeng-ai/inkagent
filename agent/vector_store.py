"""Vector store for semantic search over daily logs.

Uses sqlite-vec for vector storage and OpenAI for embeddings.
Degrades gracefully: if no embedding provider is available, vector search
is silently disabled and the system falls back to keyword search.
"""

import hashlib
import logging
import os
import sqlite3
import struct
from typing import Any

from agent.config import DAILY_DIR, DB_PATH, EMBEDDING_MODEL, VECTOR_SEARCH_TOP_K

logger = logging.getLogger(__name__)


def _serialize_f32(vector: list[float]) -> bytes:
    """Serialize a list of floats into raw bytes for sqlite-vec."""
    return struct.pack("%sf" % len(vector), *vector)


class VectorStore:
    """sqlite-vec backed vector store for daily logs."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        self._db: sqlite3.Connection | None = None
        self._embedder: Any = None  # lazy
        self._embed_dim: int | None = None
        self._embedder_resolved = False

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _get_db(self) -> sqlite3.Connection:
        if self._db is not None:
            return self._db
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        db = sqlite3.connect(self._db_path)
        try:
            import sqlite_vec  # noqa: F401

            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.enable_load_extension(False)
        except Exception as e:
            logger.warning("Failed to load sqlite-vec extension: %s", e)
            db.close()
            raise
        # Metadata table (always created).
        db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                content  TEXT NOT NULL,
                source   TEXT NOT NULL,
                hash     TEXT NOT NULL
            )
        """)
        # Meta table for tracking embedding dimension.
        db.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.commit()
        self._db = db
        # Read stored dimension.
        row = db.execute(
            "SELECT value FROM meta WHERE key = 'embed_dim'"
        ).fetchone()
        if row:
            self._embed_dim = int(row[0])
        return db

    def _ensure_vec_table(self, dim: int) -> None:
        """Create or recreate the vec_chunks virtual table if dimension changes."""
        db = self._get_db()
        if self._embed_dim == dim:
            return
        if self._embed_dim is not None:
            # Dimension changed — drop and recreate.
            logger.info(
                "Embedding dimension changed %d -> %d, rebuilding vector table",
                self._embed_dim, dim,
            )
            db.execute("DROP TABLE IF EXISTS vec_chunks")
            db.execute("DELETE FROM chunks")
        db.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding float[{dim}] distance_metric=cosine
            )
        """)
        db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('embed_dim', ?)",
            [str(dim)],
        )
        db.commit()
        self._embed_dim = dim

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def _resolve_embedder(self) -> None:
        """Try OpenAI embeddings. Sets self._embedder or leaves it None."""
        if self._embedder_resolved:
            return
        self._embedder_resolved = True

        if os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI

                client = OpenAI()
                self._embedder = client
                logger.info("Vector store using OpenAI embeddings (%s)", EMBEDDING_MODEL)
                return
            except Exception as e:
                logger.warning("OpenAI embedding init failed: %s", e)

        logger.info("No embedding provider available, vector search disabled")

    def _embed(self, text: str) -> list[float] | None:
        """Embed a single text string. Returns None if no provider available."""
        self._resolve_embedder()
        if self._embedder is None:
            return None
        try:
            resp = self._embedder.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None

    def _embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Embed a batch of texts using OpenAI's native batching."""
        self._resolve_embedder()
        if self._embedder is None:
            return [None] * len(texts)
        try:
            resp = self._embedder.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            result: list[list[float] | None] = [None] * len(texts)
            for item in resp.data:
                result[item.index] = item.embedding
            return result
        except Exception as e:
            logger.warning("Batch embedding failed: %s", e)
            return [None] * len(texts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if vector search is operational (has embedding provider + sqlite-vec)."""
        try:
            self._get_db()
        except Exception:
            return False
        self._resolve_embedder()
        return self._embedder is not None

    def index_daily_entry(self, date_str: str, content: str) -> None:
        """Index a single daily log entry into the vector store."""
        content = content.strip()
        if not content:
            return
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        chunk_id = f"daily:{date_str}:{content_hash}"
        source = f"daily/{date_str}.md"

        db = self._get_db()

        # Skip if already indexed with same hash.
        row = db.execute(
            "SELECT hash FROM chunks WHERE chunk_id = ?", [chunk_id]
        ).fetchone()
        if row and row[0] == content_hash:
            return

        vec = self._embed(content)
        if vec is None:
            return

        self._ensure_vec_table(len(vec))

        with db:
            db.execute(
                "INSERT OR REPLACE INTO chunks (chunk_id, content, source, hash) VALUES (?, ?, ?, ?)",
                [chunk_id, content, source, content_hash],
            )
            # Delete old vec row if exists, then insert new one.
            db.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", [chunk_id])
            db.execute(
                "INSERT INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
                [chunk_id, _serialize_f32(vec)],
            )

    def search(self, query: str, top_k: int = VECTOR_SEARCH_TOP_K) -> list[dict]:
        """Semantic search over indexed daily logs. Returns list of {content, source, distance}."""
        vec = self._embed(query)
        if vec is None:
            return []

        self._ensure_vec_table(len(vec))
        db = self._get_db()

        rows = db.execute(
            """
            SELECT v.chunk_id, v.distance, c.content, c.source
            FROM vec_chunks v
            JOIN chunks c ON c.chunk_id = v.chunk_id
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance
            """,
            [_serialize_f32(vec), top_k],
        ).fetchall()

        return [
            {"content": row[2], "source": row[3], "distance": row[1]}
            for row in rows
        ]

    def reindex_all(self) -> None:
        """Full reindex of all daily log files."""
        if not os.path.isdir(DAILY_DIR):
            return

        entries: list[tuple[str, str, str]] = []  # (chunk_id, content, source)
        for filename in sorted(os.listdir(DAILY_DIR)):
            if not filename.endswith(".md"):
                continue
            date_str = filename[:-3]  # strip .md
            path = os.path.join(DAILY_DIR, filename)
            try:
                with open(path, "r") as f:
                    raw = f.read()
            except OSError:
                continue
            # Parse individual log entries (lines starting with "- [").
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("<!--"):
                    continue
                content_hash = hashlib.md5(line.encode()).hexdigest()[:12]
                chunk_id = f"daily:{date_str}:{content_hash}"
                entries.append((chunk_id, line, f"daily/{date_str}.md"))

        if not entries:
            return

        # Batch embed all entries.
        texts = [e[1] for e in entries]
        embeddings = self._embed_batch(texts)

        # Filter out failed embeddings.
        valid = [
            (entry, emb)
            for entry, emb in zip(entries, embeddings)
            if emb is not None
        ]
        if not valid:
            return

        first_dim = len(valid[0][1])
        self._ensure_vec_table(first_dim)
        db = self._get_db()

        with db:
            for (chunk_id, content, source), vec in valid:
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                db.execute(
                    "INSERT OR REPLACE INTO chunks (chunk_id, content, source, hash) VALUES (?, ?, ?, ?)",
                    [chunk_id, content, source, content_hash],
                )
                db.execute("DELETE FROM vec_chunks WHERE chunk_id = ?", [chunk_id])
                db.execute(
                    "INSERT INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
                    [chunk_id, _serialize_f32(vec)],
                )

        logger.info("Reindexed %d daily log entries", len(valid))

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""
    global _instance
    if _instance is None:
        _instance = VectorStore()
        # Auto-reindex if DB is fresh but daily logs exist.
        try:
            db = _instance._get_db()
            count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            if count == 0 and _instance.is_available() and os.path.isdir(DAILY_DIR):
                has_logs = any(f.endswith(".md") for f in os.listdir(DAILY_DIR))
                if has_logs:
                    logger.info("Empty vector DB with existing daily logs, triggering reindex")
                    _instance.reindex_all()
        except Exception as e:
            logger.warning("Auto-reindex check failed: %s", e)
    return _instance
