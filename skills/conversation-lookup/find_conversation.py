"""Find Codex conversation JSONL files by short ID prefix.

Usage:
    python find_conversation.py <id-prefix>                  # lookup only
    python find_conversation.py <id-prefix> --summarize      # lookup + extract + Devstral summary
    python find_conversation.py <id-prefix> --extract        # lookup + extract transcript (no LLM)
    python find_conversation.py --search "query"             # BM25 search (default)
    python find_conversation.py --search "query" --mode semantic    # vector similarity search
    python find_conversation.py --search "query" --mode hybrid     # BM25 + vector combined
    python find_conversation.py --search "query" -n 20       # top 20 results
    python find_conversation.py --search "query" --project LiteSuite  # filter by project
    python find_conversation.py --index                      # build/update the FTS5 index
    python find_conversation.py --index --force              # force full rebuild
    python find_conversation.py --index-embeddings           # build/update vector embeddings
    python find_conversation.py --index-embeddings --force   # force full embedding rebuild
    python find_conversation.py --stats                      # show index statistics
"""
import sys
import os
import json
import re
import sqlite3
import struct
import time
import urllib.request

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

LM_STUDIO_URL = "http://169.254.83.107:1234/v1"
SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "convo_index.db"
PROJECTS_DIR = Path.home() / ".codex" / "projects"

# Embedding config — all-MiniLM-L6-v2 (384 dims)
# Stored in LiteSuite's model directory so end users auto-download on first use
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 64
EMBEDDING_MAX_CHARS = 2048  # ~512 tokens
# Chunk conversations into groups of N messages for embedding (not per-message)
EMBEDDING_CHUNK_SIZE = 8
# LiteSuite model cache — sentence-transformers will auto-download here
LITESUITE_MODEL_DIR = Path.home() / ".litesuite" / "llm" / "models"

# Skip noisy dirs (litegauntlet temp sessions, etc.)
SKIP_PATTERNS = ["litegauntlet", "AppData-Local-Temp"]

def _time_cutoff(hours=None, date=None):
    """Convert --hours or --date to ISO cutoff string(s).
    Returns (after, before) tuple. Either or both can be None."""
    if hours:
        return ((datetime.now() - timedelta(hours=hours)).isoformat(), None)
    if date:
        # "2026-04-12" -> search that full day
        return (f"{date}T00:00:00", f"{date}T23:59:59")
    return (None, None)


def find_conversations(prefix: str) -> list[dict]:
    prefix = prefix.lower().strip()
    projects_dir = PROJECTS_DIR if PROJECTS_DIR.exists() else (Path.home() / ".claude" / "projects")
    if not projects_dir.exists():
        return []

    results = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for f in project_dir.glob(f"{prefix}*.jsonl"):
            stat = f.stat()
            results.append({
                "path": str(f),
                "project": project_dir.name,
                "uuid": f.stem,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })

    results.sort(key=lambda r: r["modified"], reverse=True)
    return results


def format_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def extract_transcript(jsonl_path: str) -> dict:
    entries = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    type_counts = Counter(e.get("type", "unknown") for e in entries)
    tool_names = []
    for e in entries:
        if e.get("type") == "assistant":
            content = e.get("message", {}).get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_names.append(block.get("name", "unknown"))
    tool_counts = Counter(tool_names)

    parts = []
    for e in entries:
        msg_type = e.get("type", "")
        if msg_type == "user":
            content = e.get("message", {}).get("content", "")
            if isinstance(content, str) and len(content.strip()) > 10:
                parts.append(f"[USER]: {content[:800]}")
        elif msg_type == "assistant":
            content = e.get("message", {}).get("content", "")
            if isinstance(content, str) and len(content.strip()) > 10:
                parts.append(f"[ASSISTANT]: {content[:1500]}")
            elif isinstance(content, list):
                texts, tools = [], []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and len(block.get("text", "")) > 10:
                        texts.append(block["text"][:1000])
                    elif block.get("type") == "tool_use":
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        if name == "WebSearch":
                            tools.append(f'WebSearch: {inp.get("query", "")}')
                        elif name in ("Read", "Write", "Edit"):
                            fp = inp.get("file_path", "")
                            tools.append(f"{name}: ...{fp[-60:]}" if len(fp) > 60 else f"{name}: {fp}")
                        elif name == "Grep":
                            tools.append(f'Grep: {inp.get("pattern", "")}')
                        elif name == "Glob":
                            tools.append(f'Glob: {inp.get("pattern", "")}')
                        elif name == "Agent":
                            tools.append(f'Agent({inp.get("subagent_type", "general")}): {inp.get("description", "")}')
                        elif name == "Bash":
                            tools.append(f'Bash: {inp.get("command", "")[:80]}')
                        elif name == "Skill":
                            tools.append(f'Skill: {inp.get("skill", "")}')
                        elif name in ("AskUserQuestion", "request_user_input"):
                            tools.append(f'AskUser: {inp.get("question", "")[:80]}')
                        else:
                            tools.append(name)
                if texts:
                    parts.append(f'[ASSISTANT]: {" ".join(texts)[:1500]}')
                if tools:
                    parts.append(f'[TOOLS]: {" | ".join(tools)}')

    return {
        "entries": len(entries),
        "type_counts": dict(type_counts),
        "tool_counts": dict(tool_counts),
        "total_tool_calls": len(tool_names),
        "transcript_parts": len(parts),
        "transcript_chars": len("\n\n".join(parts)),
        "transcript": "\n\n".join(parts),
    }


def summarize_with_llm(transcript: str, project: str) -> str:
    try:
        resp = json.loads(urllib.request.urlopen(
            urllib.request.Request(f"{LM_STUDIO_URL}/models"), timeout=5
        ).read())
        models = [m["id"] for m in resp.get("data", [])]
    except Exception:
        return "[ERROR] LM Studio not reachable."

    model = None
    for m in models:
        if "devstral" in m.lower():
            model = m
            break
    if not model:
        for m in models:
            if "qwen" in m.lower():
                model = m
                break
    if not model:
        model = models[0] if models else None
    if not model:
        return "[ERROR] No models loaded in LM Studio."

    max_chars = 120000 if "devstral" in model.lower() else 12000
    t = transcript.encode("ascii", "replace").decode("ascii")
    if len(t) > max_chars:
        t = t[:max_chars] + "\n\n[TRUNCATED]"

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": (
                "You are a precision summarizer analyzing a Codex conversation transcript. "
                "Extract ALL key findings, decisions, technical discoveries, and actionable outcomes. "
                "Structure: 1) Mission/Goal, 2) Key Findings (bulleted), 3) Systems/Projects Analyzed, "
                "4) Decisions Made, 5) Artifacts Created, 6) Open Items / Next Steps. "
                "Be thorough but concise. Do not use any tools. Do not fabricate."
            )},
            {"role": "user", "content": f"Summarize this Codex conversation from project '{project}'.\n\n{t}"},
        ],
        "max_tokens": 2500,
        "temperature": 0.1,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{LM_STUDIO_URL}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return f"[Model: {model}]\n\n{resp['choices'][0]['message']['content']}"
    except Exception as e:
        return f"[ERROR] LLM request failed: {e}"


# ── FTS5 Search Index ───────────────────────────────────────────────────────

def get_db(create=False):
    """Get database connection, optionally creating schema."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    if create:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                project TEXT NOT NULL,
                message_uuid TEXT,
                timestamp TEXT,
                msg_type TEXT,
                file_path TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content_rowid='id',
                tokenize='porter unicode61'
            );
            CREATE TABLE IF NOT EXISTS index_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS indexed_files (
                file_path TEXT PRIMARY KEY,
                mtime REAL,
                msg_count INTEGER
            );
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                project TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                timestamp_start TEXT,
                timestamp_end TEXT,
                embedding BLOB NOT NULL,
                UNIQUE(conversation_id, chunk_index)
            );
            CREATE TABLE IF NOT EXISTS embedded_files (
                file_path TEXT PRIMARY KEY,
                mtime REAL,
                chunk_count INTEGER
            );
        """)
        conn.commit()
    return conn


def _ensure_embedding_tables(conn):
    """Add embedding tables if they don't exist (for DBs created before this upgrade)."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "embeddings" not in tables:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                project TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                timestamp_start TEXT,
                timestamp_end TEXT,
                embedding BLOB NOT NULL,
                UNIQUE(conversation_id, chunk_index)
            );
            CREATE TABLE IF NOT EXISTS embedded_files (
                file_path TEXT PRIMARY KEY,
                mtime REAL,
                chunk_count INTEGER
            );
        """)
        conn.commit()


def extract_text_from_content(content):
    """Extract searchable text from message content (string or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_result":
                result = block.get("content", "")
                if isinstance(result, str):
                    parts.append(result[:2000])
                elif isinstance(result, list):
                    for sub in result:
                        if isinstance(sub, dict) and sub.get("type") == "text":
                            parts.append(sub.get("text", "")[:2000])
            elif btype == "tool_use":
                name = block.get("name", "")
                inp = block.get("input", {})
                if name:
                    parts.append(f"[tool:{name}]")
                if isinstance(inp, dict):
                    for v in inp.values():
                        if isinstance(v, str) and len(v) < 1000:
                            parts.append(v)
        return "\n".join(parts)
    return str(content)[:2000]


def parse_jsonl_messages(file_path):
    """Yield (metadata, text) from a JSONL conversation file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") not in ("user", "assistant"):
                    continue
                if obj.get("isMeta"):
                    continue
                message = obj.get("message", {})
                text = extract_text_from_content(message.get("content", ""))
                if not text or len(text.strip()) < 10:
                    continue
                yield {
                    "uuid": obj.get("uuid", ""),
                    "timestamp": obj.get("timestamp", ""),
                    "type": obj.get("type"),
                    "text": text,
                }
    except Exception as e:
        print(f"  Warning: {file_path}: {e}", file=sys.stderr)


def cmd_index(force=False):
    """Build or incrementally update the FTS5 search index."""
    conn = get_db(create=True)
    if force:
        print("Force rebuild — clearing index...")
        conn.executescript(
            "DELETE FROM messages; DELETE FROM messages_fts; "
            "DELETE FROM indexed_files; DELETE FROM index_meta;")
        conn.commit()

    indexed = dict(conn.execute("SELECT file_path, mtime FROM indexed_files"))

    all_files = [f for f in PROJECTS_DIR.rglob("*.jsonl")
                 if not any(s in str(f) for s in SKIP_PATTERNS)]
    print(f"Found {len(all_files)} conversation files")

    to_index = [f for f in all_files
                if str(f) not in indexed or indexed[str(f)] < f.stat().st_mtime]
    if not to_index:
        print("Index is up to date.")
        _print_stats(conn)
        conn.close()
        return

    print(f"Indexing {len(to_index)} new/modified files...")
    total_msgs = 0
    t0 = time.time()

    for i, jsonl_path in enumerate(to_index):
        fp = str(jsonl_path)
        rel = jsonl_path.relative_to(PROJECTS_DIR)
        project = rel.parts[0] if rel.parts else "unknown"
        conv_id = jsonl_path.stem

        # Remove old entries if re-indexing
        if fp in indexed:
            old_ids = [r[0] for r in conn.execute(
                "SELECT id FROM messages WHERE file_path = ?", (fp,))]
            if old_ids:
                ph = ",".join("?" * len(old_ids))
                conn.execute(f"DELETE FROM messages_fts WHERE rowid IN ({ph})", old_ids)
                conn.execute(f"DELETE FROM messages WHERE id IN ({ph})", old_ids)

        msg_count = 0
        for msg in parse_jsonl_messages(jsonl_path):
            conn.execute(
                "INSERT INTO messages (conversation_id, project, message_uuid, "
                "timestamp, msg_type, file_path) VALUES (?,?,?,?,?,?)",
                (conv_id, project, msg["uuid"], msg["timestamp"], msg["type"], fp))
            rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO messages_fts (rowid, content) VALUES (?,?)",
                         (rowid, msg["text"]))
            msg_count += 1

        conn.execute(
            "INSERT OR REPLACE INTO indexed_files (file_path, mtime, msg_count) "
            "VALUES (?,?,?)", (fp, jsonl_path.stat().st_mtime, msg_count))
        total_msgs += msg_count

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  [{i+1}/{len(to_index)}] {total_msgs:,} messages...")

    conn.commit()
    conn.execute("INSERT OR REPLACE INTO index_meta (key, value) VALUES ('last_indexed', ?)",
                 (datetime.now().isoformat(),))
    conn.commit()
    print(f"\nDone: {total_msgs:,} messages from {len(to_index)} files in {time.time()-t0:.1f}s")
    _print_stats(conn)
    conn.close()


def cmd_search(query, top_n=10, project_filter=None, msg_type=None, hours=None, date=None):
    """BM25 search across all indexed conversations."""
    if not DB_PATH.exists():
        print("No index found. Run with --index first.")
        sys.exit(1)

    conn = get_db()
    t_after, t_before = _time_cutoff(hours, date)

    # Build FTS5 query
    clean = re.sub(r'[^\w\s]', ' ', query).strip()
    terms = clean.split()
    fts_and = " AND ".join(f'"{t}"' for t in terms) if len(terms) > 1 else f'"{clean}"'
    fts_or = " OR ".join(f'"{t}"' for t in terms) if len(terms) > 1 else fts_and

    sql = """
        SELECT m.id, m.conversation_id, m.project, m.timestamp, m.msg_type,
               m.file_path,
               snippet(messages_fts, 0, '>>>', '<<<', '...', 64) as snippet,
               bm25(messages_fts) as rank
        FROM messages_fts
        JOIN messages m ON m.id = messages_fts.rowid
        WHERE messages_fts MATCH ?
    """
    params = [fts_and]
    if t_after:
        sql += " AND m.timestamp >= ?"
        params.append(t_after)
    if t_before:
        sql += " AND m.timestamp <= ?"
        params.append(t_before)
    if project_filter:
        sql += " AND m.project LIKE ?"
        params.append(f"%{project_filter}%")
    if msg_type:
        sql += " AND m.msg_type = ?"
        params.append(msg_type)
    sql += " ORDER BY rank LIMIT ?"
    params.append(top_n * 3)

    try:
        results = conn.execute(sql, params).fetchall()
    except Exception:
        params[0] = fts_or
        try:
            results = conn.execute(sql, params).fetchall()
        except Exception as e:
            print(f"Search error: {e}")
            conn.close()
            sys.exit(1)

    if not results:
        print(f"No results for: {query}")
        conn.close()
        return

    # Best hit per conversation
    seen = {}
    deduped = []
    for r in results:
        if r[1] not in seen:
            seen[r[1]] = True
            deduped.append(r)
        if len(deduped) >= top_n:
            break

    print(f"Found {len(results)} matches across {len(seen)} conversations")
    print(f"Top {len(deduped)} (best per conversation):\n")

    for i, (_, conv_id, project, timestamp, mtype, file_path, snippet, rank) in enumerate(deduped):
        ts = ""
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts = timestamp[:16]
        snip = snippet.replace("\\n", " ").strip()[:300]
        proj = project.replace("C--", "").replace("E--", "").replace("-", "/")
        print(f"{'─'*70}")
        print(f"#{i+1}  [{mtype}]  {ts}  score={abs(rank):.2f}")
        print(f"    Project: {proj}")
        print(f"    ConvID:  {conv_id[:8]}...  ({conv_id})")
        print(f"    Snippet: {snip}")

    print(f"{'─'*70}")
    conn.close()


# ── Embedding helpers ──────────────────────────────────────────────────────

def _vec_to_blob(vec):
    """Pack float list to compact binary blob."""
    return struct.pack(f"{len(vec)}f", *vec)


def _blob_to_vec(blob):
    """Unpack binary blob to float list."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _load_embedder():
    """Load sentence-transformers model (singleton, lazy).

    Uses LiteSuite's model directory (~/.litesuite/llm/models/) as cache.
    Auto-downloads on first use for end users — no separate setup needed.
    """
    from sentence_transformers import SentenceTransformer
    if not hasattr(_load_embedder, "_model"):
        cache_dir = str(LITESUITE_MODEL_DIR)
        LITESUITE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Loading embedding model: {EMBEDDING_MODEL} (cache: {cache_dir})...")
        _load_embedder._model = SentenceTransformer(
            EMBEDDING_MODEL, cache_folder=cache_dir
        )
        print(f"  Loaded ({_load_embedder._model.get_sentence_embedding_dimension()} dims)")
    return _load_embedder._model


def _chunk_conversation(file_path):
    """Read a conversation and chunk messages into groups for embedding."""
    messages = []
    for msg in parse_jsonl_messages(file_path):
        messages.append(msg)

    if not messages:
        return []

    chunks = []
    for i in range(0, len(messages), EMBEDDING_CHUNK_SIZE):
        group = messages[i:i + EMBEDDING_CHUNK_SIZE]
        text_parts = []
        for m in group:
            prefix = "USER" if m["type"] == "user" else "ASSISTANT"
            text_parts.append(f"[{prefix}]: {m['text'][:EMBEDDING_MAX_CHARS]}")
        chunk_text = "\n".join(text_parts)
        # Truncate final chunk text to model max
        if len(chunk_text) > EMBEDDING_MAX_CHARS:
            chunk_text = chunk_text[:EMBEDDING_MAX_CHARS]
        chunks.append({
            "index": i // EMBEDDING_CHUNK_SIZE,
            "text": chunk_text,
            "ts_start": group[0].get("timestamp", ""),
            "ts_end": group[-1].get("timestamp", ""),
        })
    return chunks


def cmd_index_embeddings(force=False):
    """Build or incrementally update vector embeddings for conversations."""
    conn = get_db(create=True)
    _ensure_embedding_tables(conn)

    if force:
        print("Force rebuild — clearing embeddings...")
        conn.executescript("DELETE FROM embeddings; DELETE FROM embedded_files;")
        conn.commit()

    embedded = dict(conn.execute("SELECT file_path, mtime FROM embedded_files").fetchall())

    all_files = [f for f in PROJECTS_DIR.rglob("*.jsonl")
                 if not any(s in str(f) for s in SKIP_PATTERNS)]
    print(f"Found {len(all_files)} conversation files")

    to_embed = [f for f in all_files
                if str(f) not in embedded or embedded[str(f)] < f.stat().st_mtime]
    if not to_embed:
        print("Embeddings are up to date.")
        _print_embedding_stats(conn)
        conn.close()
        return

    print(f"Embedding {len(to_embed)} new/modified files...")
    model = _load_embedder()
    total_chunks = 0
    t0 = time.time()

    batch_texts = []
    batch_meta = []

    for i, jsonl_path in enumerate(to_embed):
        fp = str(jsonl_path)
        rel = jsonl_path.relative_to(PROJECTS_DIR)
        project = rel.parts[0] if rel.parts else "unknown"
        conv_id = jsonl_path.stem

        # Remove old embeddings if re-indexing
        if fp in embedded:
            conn.execute("DELETE FROM embeddings WHERE conversation_id = ?", (conv_id,))

        chunks = _chunk_conversation(jsonl_path)
        for chunk in chunks:
            batch_texts.append(chunk["text"])
            batch_meta.append({
                "conv_id": conv_id,
                "project": project,
                "chunk_index": chunk["index"],
                "chunk_text": chunk["text"],
                "ts_start": chunk["ts_start"],
                "ts_end": chunk["ts_end"],
            })

        # Flush batch when large enough
        if len(batch_texts) >= EMBEDDING_BATCH_SIZE:
            embeddings = model.encode(batch_texts, convert_to_numpy=True, batch_size=EMBEDDING_BATCH_SIZE)
            for emb, meta in zip(embeddings, batch_meta):
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings "
                    "(conversation_id, project, chunk_index, chunk_text, "
                    "timestamp_start, timestamp_end, embedding) VALUES (?,?,?,?,?,?,?)",
                    (meta["conv_id"], meta["project"], meta["chunk_index"],
                     meta["chunk_text"], meta["ts_start"], meta["ts_end"],
                     _vec_to_blob(emb.tolist())))
            total_chunks += len(batch_texts)
            batch_texts.clear()
            batch_meta.clear()

        conn.execute(
            "INSERT OR REPLACE INTO embedded_files (file_path, mtime, chunk_count) "
            "VALUES (?,?,?)", (fp, jsonl_path.stat().st_mtime, len(chunks)))

        if (i + 1) % 100 == 0:
            conn.commit()
            elapsed = time.time() - t0
            rate = total_chunks / elapsed if elapsed > 0 else 0
            print(f"  [{i+1}/{len(to_embed)}] {total_chunks:,} chunks ({rate:.0f} chunks/s)...")

    # Flush remaining
    if batch_texts:
        embeddings = model.encode(batch_texts, convert_to_numpy=True, batch_size=EMBEDDING_BATCH_SIZE)
        for emb, meta in zip(embeddings, batch_meta):
            conn.execute(
                "INSERT OR REPLACE INTO embeddings "
                "(conversation_id, project, chunk_index, chunk_text, "
                "timestamp_start, timestamp_end, embedding) VALUES (?,?,?,?,?,?,?)",
                (meta["conv_id"], meta["project"], meta["chunk_index"],
                 meta["chunk_text"], meta["ts_start"], meta["ts_end"],
                 _vec_to_blob(emb.tolist())))
        total_chunks += len(batch_texts)

    conn.commit()
    conn.execute("INSERT OR REPLACE INTO index_meta (key, value) VALUES ('last_embedded', ?)",
                 (datetime.now().isoformat(),))
    conn.commit()
    elapsed = time.time() - t0
    print(f"\nDone: {total_chunks:,} chunks from {len(to_embed)} files in {elapsed:.1f}s "
          f"({total_chunks/elapsed:.0f} chunks/s)")
    _print_embedding_stats(conn)
    conn.close()


def cmd_search_semantic(query, top_n=10, project_filter=None, hours=None, date=None):
    """Pure vector similarity search."""
    if not DB_PATH.exists():
        print("No index found. Run with --index-embeddings first.")
        sys.exit(1)

    conn = get_db()
    _ensure_embedding_tables(conn)

    emb_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    if emb_count == 0:
        print("No embeddings found. Run with --index-embeddings first.")
        conn.close()
        sys.exit(1)

    import numpy as np
    t_after, t_before = _time_cutoff(hours, date)
    model = _load_embedder()
    query_vec = model.encode(query, convert_to_numpy=True)
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

    # Load all embeddings (brute-force cosine — fast enough for ~100K chunks)
    sql = "SELECT id, conversation_id, project, chunk_index, chunk_text, timestamp_start, embedding FROM embeddings"
    clauses = []
    params = []
    if project_filter:
        clauses.append("project LIKE ?")
        params.append(f"%{project_filter}%")
    if t_after:
        clauses.append("timestamp_start >= ?")
        params.append(t_after)
    if t_before:
        clauses.append("timestamp_start <= ?")
        params.append(t_before)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No embeddings match the filter.")
        conn.close()
        return

    # Batch cosine similarity
    ids, conv_ids, projects, chunk_idxs, texts, timestamps, vecs = [], [], [], [], [], [], []
    for row in rows:
        ids.append(row[0])
        conv_ids.append(row[1])
        projects.append(row[2])
        chunk_idxs.append(row[3])
        texts.append(row[4])
        timestamps.append(row[5])
        vecs.append(_blob_to_vec(row[6]))

    mat = np.array(vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-8
    mat_norm = mat / norms
    scores = np.dot(mat_norm, query_norm)

    # Sort by score descending
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    # Best per conversation
    seen = {}
    results = []
    for idx in ranked:
        cid = conv_ids[idx]
        if cid not in seen:
            seen[cid] = True
            results.append((cid, projects[idx], timestamps[idx], texts[idx], float(scores[idx])))
        if len(results) >= top_n:
            break

    _print_search_results(results, query, "semantic")
    conn.close()


def cmd_search_hybrid(query, top_n=10, project_filter=None, msg_type=None, bm25_weight=0.3, hours=None, date=None):
    """Hybrid BM25 + vector search with configurable weight blend."""
    if not DB_PATH.exists():
        print("No index found. Run with --index and --index-embeddings first.")
        sys.exit(1)

    conn = get_db()
    _ensure_embedding_tables(conn)

    import numpy as np
    t_after, t_before = _time_cutoff(hours, date)

    # ── BM25 pass ──
    clean = re.sub(r'[^\w\s]', ' ', query).strip()
    terms = clean.split()
    fts_query = " OR ".join(f'"{t}"' for t in terms) if terms else f'"{clean}"'

    bm25_sql = """
        SELECT m.conversation_id, m.project, m.timestamp,
               snippet(messages_fts, 0, '>>>', '<<<', '...', 64) as snippet,
               bm25(messages_fts) as rank
        FROM messages_fts
        JOIN messages m ON m.id = messages_fts.rowid
        WHERE messages_fts MATCH ?
    """
    bm25_params = [fts_query]
    if t_after:
        bm25_sql += " AND m.timestamp >= ?"
        bm25_params.append(t_after)
    if t_before:
        bm25_sql += " AND m.timestamp <= ?"
        bm25_params.append(t_before)
    if project_filter:
        bm25_sql += " AND m.project LIKE ?"
        bm25_params.append(f"%{project_filter}%")
    if msg_type:
        bm25_sql += " AND m.msg_type = ?"
        bm25_params.append(msg_type)
    bm25_sql += " ORDER BY rank LIMIT 200"

    try:
        bm25_rows = conn.execute(bm25_sql, bm25_params).fetchall()
    except Exception:
        bm25_rows = []

    # Aggregate BM25: best score per conversation (bm25 returns negative, lower=better)
    bm25_scores = {}
    bm25_snippets = {}
    for cid, proj, ts, snippet, rank in bm25_rows:
        score = abs(rank)
        if cid not in bm25_scores or score > bm25_scores[cid]:
            bm25_scores[cid] = score
            bm25_snippets[cid] = (proj, ts, snippet)

    # ── Vector pass ──
    emb_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    vec_scores = {}
    if emb_count > 0:
        model = _load_embedder()
        query_vec = model.encode(query, convert_to_numpy=True)
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

        emb_sql = "SELECT conversation_id, project, timestamp_start, chunk_text, embedding FROM embeddings"
        emb_clauses = []
        emb_params = []
        if project_filter:
            emb_clauses.append("project LIKE ?")
            emb_params.append(f"%{project_filter}%")
        if t_after:
            emb_clauses.append("timestamp_start >= ?")
            emb_params.append(t_after)
        if t_before:
            emb_clauses.append("timestamp_start <= ?")
            emb_params.append(t_before)
        if emb_clauses:
            emb_sql += " WHERE " + " AND ".join(emb_clauses)

        emb_rows = conn.execute(emb_sql, emb_params).fetchall()
        for cid, proj, ts, text, emb_blob in emb_rows:
            vec = np.array(_blob_to_vec(emb_blob), dtype=np.float32)
            vec_norm = vec / (np.linalg.norm(vec) + 1e-8)
            sim = float(np.dot(query_norm, vec_norm))
            if cid not in vec_scores or sim > vec_scores[cid]:
                vec_scores[cid] = sim
                if cid not in bm25_snippets:
                    bm25_snippets[cid] = (proj, ts, text[:300])

    # ── Merge scores ──
    all_cids = set(bm25_scores.keys()) | set(vec_scores.keys())
    if not all_cids:
        print(f"No results for: {query}")
        conn.close()
        return

    # Normalize each score set to [0, 1]
    bm25_max = max(bm25_scores.values()) if bm25_scores else 1.0
    vec_max = max(vec_scores.values()) if vec_scores else 1.0

    merged = []
    for cid in all_cids:
        b = bm25_scores.get(cid, 0) / bm25_max if bm25_max > 0 else 0
        v = vec_scores.get(cid, 0) / vec_max if vec_max > 0 else 0
        combined = (bm25_weight * b) + ((1 - bm25_weight) * v)
        proj, ts, snippet = bm25_snippets.get(cid, ("unknown", "", ""))
        merged.append((cid, proj, ts, snippet, combined))

    merged.sort(key=lambda x: x[4], reverse=True)
    _print_search_results(merged[:top_n], query, "hybrid")
    conn.close()


def _print_search_results(results, query, mode):
    """Print formatted search results."""
    print(f"Found {len(results)} conversations ({mode} search)\n")
    for i, (conv_id, project, timestamp, snippet, score) in enumerate(results):
        ts = ""
        if timestamp:
            try:
                ts = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts = str(timestamp)[:16]
        snip = str(snippet).replace("\\n", " ").replace("\n", " ").strip()[:300]
        proj = project.replace("C--", "").replace("E--", "").replace("-", "/")
        print(f"{'─'*70}")
        print(f"#{i+1}  {ts}  score={score:.4f}  [{mode}]")
        print(f"    Project: {proj}")
        print(f"    ConvID:  {conv_id[:8]}...  ({conv_id})")
        print(f"    Snippet: {snip}")
    print(f"{'─'*70}")


def _print_embedding_stats(conn):
    """Print embedding index statistics."""
    total = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    files = conn.execute("SELECT COUNT(*) FROM embedded_files").fetchone()[0]
    convos = conn.execute("SELECT COUNT(DISTINCT conversation_id) FROM embeddings").fetchone()[0]
    last = conn.execute("SELECT value FROM index_meta WHERE key='last_embedded'").fetchone()
    print(f"\n--- Embedding Stats ---")
    print(f"Chunks: {total:,}  |  Files: {files:,}  |  Conversations: {convos:,}")
    print(f"Model: {EMBEDDING_MODEL} ({EMBEDDING_DIM} dims)")
    if last:
        print(f"Last embedded: {last[0][:19]}")


def _print_stats(conn):
    total_msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
    total_proj = conn.execute("SELECT COUNT(DISTINCT project) FROM messages").fetchone()[0]
    last = conn.execute("SELECT value FROM index_meta WHERE key='last_indexed'").fetchone()
    print(f"\n--- FTS5 Index Stats ---")
    print(f"Messages: {total_msgs:,}  |  Files: {total_files:,}  |  Projects: {total_proj}")
    if last:
        print(f"Last indexed: {last[0][:19]}")
    if DB_PATH.exists():
        print(f"DB size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"\nTop projects:")
    for proj, cnt in conn.execute(
            "SELECT project, COUNT(*) c FROM messages GROUP BY project ORDER BY c DESC LIMIT 10"):
        print(f"  {cnt:>6,}  {proj.replace('C--','').replace('E--','').replace('-','/')}")

    # Show embedding stats if table exists
    _ensure_embedding_tables(conn)
    emb_count = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    if emb_count > 0:
        _print_embedding_stats(conn)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: find_conversation.py <id-prefix> [--summarize | --extract]")
        print("       find_conversation.py --search \"query\" [-n N] [--project NAME] [--mode bm25|semantic|hybrid]")
        print("       find_conversation.py --index [--force]")
        print("       find_conversation.py --index-embeddings [--force]")
        print("       find_conversation.py --stats")
        sys.exit(1)

    # ── Search mode ─────────────────────────────────────────────────────
    if "--search" in args:
        idx = args.index("--search")
        if idx + 1 >= len(args):
            print("Error: --search requires a query string")
            sys.exit(1)
        query = args[idx + 1]
        top_n = 10
        if "-n" in args:
            ni = args.index("-n")
            top_n = int(args[ni + 1]) if ni + 1 < len(args) else 10
        project = None
        if "--project" in args:
            pi = args.index("--project")
            project = args[pi + 1] if pi + 1 < len(args) else None
        msg_type = None
        if "--type" in args:
            ti = args.index("--type")
            msg_type = args[ti + 1] if ti + 1 < len(args) else None
        mode = "bm25"
        if "--mode" in args:
            mi = args.index("--mode")
            mode = args[mi + 1] if mi + 1 < len(args) else "bm25"
        hours = None
        if "--hours" in args:
            hi = args.index("--hours")
            hours = int(args[hi + 1]) if hi + 1 < len(args) else None
        date = None
        if "--date" in args:
            di = args.index("--date")
            date = args[di + 1] if di + 1 < len(args) else None

        if mode == "semantic":
            cmd_search_semantic(query, top_n, project, hours=hours, date=date)
        elif mode == "hybrid":
            cmd_search_hybrid(query, top_n, project, msg_type, hours=hours, date=date)
        else:
            cmd_search(query, top_n, project, msg_type, hours=hours, date=date)
        return

    # ── Index embeddings mode ──────────────────────────────────────────
    if "--index-embeddings" in args:
        cmd_index_embeddings(force="--force" in args)
        return

    # ── Index mode ──────────────────────────────────────────────────────
    if "--index" in args:
        cmd_index(force="--force" in args)
        return

    # ── Stats mode ──────────────────────────────────────────────────────
    if "--stats" in args:
        if not DB_PATH.exists():
            print("No index. Run --index first.")
            return
        conn = get_db()
        _print_stats(conn)
        conn.close()
        return

    # ── Original lookup mode ────────────────────────────────────────────
    prefix = args[0]
    do_summarize = "--summarize" in args
    do_extract = "--extract" in args

    results = find_conversations(prefix)
    if not results:
        print(f"No conversations found matching '{prefix}'")
        sys.exit(0)

    print(f"Found {len(results)} match(es):\n")
    for r in results:
        print(f"  UUID:     {r['uuid']}")
        print(f"  Path:     {r['path']}")
        print(f"  Project:  {r['project']}")
        print(f"  Size:     {format_size(r['size_bytes'])}")
        print(f"  Modified: {r['modified']}")
        print()

    if not (do_summarize or do_extract):
        return

    match = results[0]
    print("Extracting transcript...")
    data = extract_transcript(match["path"])
    print(f"  JSONL entries: {data['entries']}")
    print(f"  Tool calls:    {data['total_tool_calls']}")
    print(f"  Transcript:    {data['transcript_parts']} parts, {data['transcript_chars']} chars")
    top_tools = sorted(data["tool_counts"].items(), key=lambda x: -x[1])[:8]
    if top_tools:
        print(f"  Top tools:     {', '.join(f'{n}({c})' for n,c in top_tools)}")

    if do_extract:
        print(f"\n{'='*60}\n")
        print(data["transcript"])
        return

    if do_summarize:
        print("\nSummarizing via LM Studio...")
        summary = summarize_with_llm(data["transcript"], match["project"])
        print(f"\n{'='*60}")
        print("SUMMARY:")
        print(f"{'='*60}\n")
        print(summary)


if __name__ == "__main__":
    main()
