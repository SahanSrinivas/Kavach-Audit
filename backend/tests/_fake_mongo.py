"""Minimal in-memory fake Mongo for route-level tests.

Implements only the operations the routers actually call. Each collection
is its own list-of-dicts. No indexing, no concurrency safety — sufficient
for unit-test deterministic assertions.
"""
from __future__ import annotations

from typing import Any


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def sort(self, key: str | list[tuple[str, int]], direction: int = 1) -> "_Cursor":
        """Mongo's sort accepts either (key, direction) or
        [(key, direction), ...]. Match the API so tests can rely on order."""
        if isinstance(key, list):
            for k, d in reversed(key):
                self._rows.sort(key=lambda r, _k=k: r.get(_k) or "", reverse=(d == -1))
        else:
            self._rows.sort(key=lambda r: r.get(key) or "", reverse=(direction == -1))
        return self

    async def to_list(self, n: int) -> list[dict[str, Any]]:
        return list(self._rows[:n])


class _DeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class _UpdateResult:
    def __init__(self, matched_count: int) -> None:
        self.matched_count = matched_count


class _Collection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self._unique_keys: list[tuple[str, ...]] = []

    def add_unique_index(self, *keys: str) -> None:
        self._unique_keys.append(keys)

    def _matches(self, doc: dict[str, Any], query: dict[str, Any]) -> bool:
        for k, v in query.items():
            if k.startswith("$"):
                continue
            doc_val = doc.get(k)
            if isinstance(v, dict) and "$gte" in v:
                if doc_val is None or doc_val < v["$gte"]:
                    return False
                continue
            if isinstance(v, dict) and "$gt" in v:
                if doc_val is None or doc_val <= v["$gt"]:
                    return False
                continue
            if doc_val != v:
                return False
        return True

    async def find_one(
        self, query: dict[str, Any], _projection: dict | None = None,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any] | None:
        rows = [d for d in self.docs if self._matches(d, query)]
        if sort:
            for key, direction in reversed(sort):
                rows.sort(key=lambda d: d.get(key) or "", reverse=(direction == -1))
        return dict(rows[0]) if rows else None

    def find(self, query: dict[str, Any] | None = None,
             _projection: dict | None = None) -> _Cursor:
        q = query or {}
        return _Cursor([dict(d) for d in self.docs if self._matches(d, q)])

    async def insert_one(self, doc: dict[str, Any]) -> None:
        for keys in self._unique_keys:
            for existing in self.docs:
                if all(existing.get(k) == doc.get(k) for k in keys):
                    raise Exception(f"E11000 duplicate key error: {keys}")
        self.docs.append(dict(doc))

    async def insert_many(self, docs: list[dict[str, Any]]) -> None:
        for d in docs:
            await self.insert_one(d)

    async def delete_one(self, query: dict[str, Any]) -> _DeleteResult:
        for i, d in enumerate(self.docs):
            if self._matches(d, query):
                self.docs.pop(i)
                return _DeleteResult(1)
        return _DeleteResult(0)

    async def delete_many(self, query: dict[str, Any]) -> _DeleteResult:
        before = len(self.docs)
        self.docs[:] = [d for d in self.docs if not self._matches(d, query)]
        return _DeleteResult(before - len(self.docs))

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> _UpdateResult:
        for d in self.docs:
            if self._matches(d, query):
                if "$set" in update:
                    d.update(update["$set"])
                return _UpdateResult(1)
        return _UpdateResult(0)

    async def count_documents(self, query: dict[str, Any]) -> int:
        return sum(1 for d in self.docs if self._matches(d, query))

    async def create_index(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class FakeDb:
    """Provides db.<collection>.<op> for any collection name on demand."""
    def __init__(self) -> None:
        self._cols: dict[str, _Collection] = {}
        self.beta_allowlist.add_unique_index("user_id", "feature")

    def __getattr__(self, name: str) -> _Collection:
        # Avoid infinite recursion for dunder + private attrs
        if name.startswith("_") or name == "command":
            raise AttributeError(name)
        if name not in self._cols:
            self._cols[name] = _Collection()
        return self._cols[name]

    async def command(self, _cmd: str) -> dict[str, int]:
        return {"ok": 1}
