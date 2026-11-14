"""Availability checks for tests that need live services.

`make test` must pass on a fresh clone with no services running. Tests that need Redis, the ingested
thesis index or the embedding model skip with a reason instead of failing when those are missing.
Each check runs once per process. Never uses FT.INFO (it can deadlock Redis on this vector index).
"""

import functools

REDIS_REASON = "Redis not available (start it: make redis-up); live cache check skipped"
SEMANTIC_REASON = ("Redis or the embedding model not available (make redis-up; make download-models); "
                   "semantic (paraphrase) cache check skipped")
INDEX_REASON = ("thesis index or embedding model not available (needs Redis with the ingested chunks and "
                "make download-models); live retrieval check skipped")


@functools.lru_cache(maxsize=None)
def redis_available() -> bool:
    try:
        import redis
        from gateway.cache.redis_semantic_cache import DEFAULT_REDIS_URL
        redis.Redis.from_url(DEFAULT_REDIS_URL, socket_connect_timeout=2, socket_timeout=5).ping()
        return True
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def embedder_available() -> bool:
    """A real sentence-embedding model is loaded (not the hash fallback used when the model is missing)."""
    try:
        from pipeline.embeddings.embedder import LocalEmbedder
        e = LocalEmbedder()
        return e._model is not None or getattr(e, "_st_model", None) is not None
    except Exception:
        return False


@functools.lru_cache(maxsize=None)
def thesis_index_available() -> bool:
    if not redis_available():
        return False
    try:
        import redis
        from pipeline.retriever import RedisChunkRetriever
        r = RedisChunkRetriever()
        client = redis.Redis.from_url(r.redis_url, socket_connect_timeout=2, socket_timeout=10)
        names = {n.decode() if isinstance(n, bytes) else str(n) for n in client.execute_command("FT._LIST")}
        if r.index_name not in names:
            return False
        if not embedder_available():
            return False
        return bool(r.search("graphene synthesis", top_k=1))
    except Exception:
        return False
