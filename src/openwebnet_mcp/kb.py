"""Machine KB consumer: loads the OpenWebNet Encyclopedia's deterministic knowledge artifacts.

The Machine KB (``knowledge/`` in the OpenWebNet-Encyclopedia repository) is a static
projection of the Encyclopedia: retrieval chunks, atomic claims and seven reference
registries, all keyed by stable ``ownkb:`` IDs. This module follows the consumer guide
(``knowledge/CONSUMING.md``): read the manifest first, check version compatibility,
verify SHA-256 hashes, then index chunks and claims and key everything by stable ID.

Qualifications (epistemic status, applicability, cautions, open questions, provenance)
are carried through untouched; ranking is lexical and is never evidence strength.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openwebnet_mcp._paths import get_kb_dir

logger = logging.getLogger("openwebnet_mcp.kb")

SUPPORTED_SCHEMA = (0, 1)  # (major, minor) of manifest.schema_compatibility_version

# Statuses that are preserved history or open knowledge, not established guidance.
NON_ESTABLISHED = {
    "unresolved": "an open question, not an established fact",
    "hypothesis": "an untested explanation, not an established fact",
    "rejected": "preserved history, not current guidance",
    "superseded": "preserved history, not current guidance",
    "contradicted": "contradicted by other records",
    "inferred": "a reasoned interpretation, not a published specification",
}

# Known 0.1.0 defect (Encyclopedia#37): claim statements can embed a Python dict repr of
# the markdown parser's table cells. The retrieval chunk for the same section is intact.
_LEAK_MARKERS = ("{'text': '", '{"text": "', '{"text":"')

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BM25_K1 = 1.4
_BM25_B = 0.75


class KBError(Exception):
    """Raised when the Machine KB cannot be loaded or is not supported."""


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def clean_statement(statement: str) -> tuple[str, bool]:
    """Return ``(statement, degraded)``, cutting off a leaked parser representation."""
    hits = [i for i in (statement.find(m) for m in _LEAK_MARKERS) if i != -1]
    if not hits:
        return statement, False
    idx = min(hits)
    return statement[:idx].rstrip(" :;|") + " […]", True


class MachineKB:
    """In-memory index over the Machine KB artifacts."""

    def __init__(self, kb_dir: Path | None = None, *, strict: bool | None = None) -> None:
        self._explicit_dir = kb_dir
        self.strict = strict if strict is not None else os.environ.get("OPENWEBNET_KB_STRICT") == "1"
        self._reset()

    def _reset(self) -> None:
        self.kb_dir: Path | None = None
        self.manifest: dict[str, Any] = {}
        self.hash_mismatches: list[str] = []
        self.hashes_verified = False
        self.loaded = False
        self.load_error: str | None = None
        self.chunks: dict[str, dict[str, Any]] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.registry: dict[str, dict[str, Any]] = {}
        self.aliases: dict[str, dict[str, Any]] = {}  # alias id -> id-registry alias entry
        self.lifecycle: dict[str, dict[str, Any]] = {}  # id -> id-registry entry (deprecated/retired only)
        self._chunk_by_section: dict[str, str] = {}
        self._docs: list[tuple[str, str]] = []  # (kind, id)
        self._tf: list[Counter[str]] = []
        self._doc_len: list[int] = []
        self._df: Counter[str] = Counter()
        self._avg_len = 0.0

    # ── loading ──────────────────────────────────────────────────────
    def load(self) -> bool:
        """Load and index the KB. Returns False (with ``load_error`` set) when unavailable.

        The new index is built off to the side and swapped in only when complete, so a concurrent
        search never observes a half-built or empty KB.
        """
        fresh = MachineKB(self._explicit_dir, strict=self.strict)
        ok = fresh._load()
        self.__dict__.update(fresh.__dict__)
        return ok

    def _load(self) -> bool:
        kb_dir = self._explicit_dir or get_kb_dir()
        if kb_dir is None:
            self.load_error = (
                "Machine KB not found. Set OPENWEBNET_KB_PATH to a 'knowledge' directory, place an "
                "OpenWebNet-Encyclopedia checkout next to this repository, or run "
                "'python -m openwebnet_mcp.kb_fetch'."
            )
            return False
        try:
            self._load_from(kb_dir)
        except (OSError, ValueError, KBError) as err:
            self._reset()
            self.load_error = f"Machine KB at {kb_dir} could not be loaded: {err}"
            logger.error(self.load_error)
            return False
        self.loaded = True
        logger.info(
            "Machine KB loaded from %s (%d chunks, %d claims, %d reference records)",
            kb_dir,
            len(self.chunks),
            len(self.claims),
            len(self.registry),
        )
        return True

    def _load_from(self, kb_dir: Path) -> None:
        manifest_path = kb_dir / "manifest.json"
        if not manifest_path.is_file():
            raise KBError("manifest.json is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._check_compatibility(manifest)
        by_kind: dict[str, list[Path]] = defaultdict(list)
        for art in manifest.get("artifacts", []):
            if art["kind"] == "schema":
                continue  # schemas are for strict validation; this consumer does not use them
            local = self._local_path(kb_dir, art["path"])
            if not local.is_file():
                raise KBError(f"manifest artifact missing on disk: {art['path']}")
            if _sha256(local) != art["sha256"]:
                self.hash_mismatches.append(art["path"])
            by_kind[art["kind"]].append(local)
        for required in ("retrieval_chunks", "claim_records"):
            if not by_kind.get(required):
                raise KBError(f"manifest lists no {required} artifact")
        self.hashes_verified = not self.hash_mismatches
        if self.hash_mismatches:
            msg = "SHA-256 mismatch for: " + ", ".join(self.hash_mismatches)
            if self.strict:
                raise KBError(msg)
            logger.warning("%s (loading anyway; set OPENWEBNET_KB_STRICT=1 to refuse)", msg)

        self.kb_dir = kb_dir
        self.manifest = manifest
        for path in by_kind["retrieval_chunks"]:
            for chunk in _read_jsonl(path):
                self.chunks[chunk["id"]] = chunk
                self._chunk_by_section[chunk["section_id"]] = chunk["id"]
        for path in by_kind["claim_records"]:
            for claim in _read_jsonl(path):
                self.claims[claim["id"]] = claim
        for path in by_kind["reference_registry"]:
            for rec in _read_jsonl(path):
                self.registry[rec["id"]] = rec
        for path in by_kind["id_registry"]:
            self._load_id_registry(path)
        self._build_index()

    @staticmethod
    def _local_path(kb_dir: Path, manifest_path: str) -> Path:
        """Map a repo-relative manifest path ('knowledge/x/y') into ``kb_dir``, refusing escapes."""
        parts = Path(manifest_path).parts
        if not parts or parts[0] != "knowledge":
            raise KBError(f"manifest path outside knowledge/: {manifest_path}")
        local = kb_dir.joinpath(*parts[1:]).resolve()
        if not local.is_relative_to(kb_dir.resolve()):
            raise KBError(f"manifest path escapes the KB directory: {manifest_path}")
        return local

    def _load_id_registry(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        for alias in data.get("aliases", []):
            self.aliases[alias["alias"]] = alias
        for entry in data.get("ids", []):
            if entry.get("lifecycle", "live") != "live":
                self.lifecycle[entry["id"]] = entry

    def _check_compatibility(self, manifest: dict[str, Any]) -> None:
        version = str(manifest.get("schema_compatibility_version", ""))
        try:
            major, minor = (int(p) for p in version.split(".")[:2])
        except ValueError as err:
            raise KBError(f"unreadable schema_compatibility_version {version!r}") from err
        if (major, minor) != SUPPORTED_SCHEMA:
            raise KBError(
                f"schema_compatibility_version {version} is not supported "
                f"(this consumer understands {SUPPORTED_SCHEMA[0]}.{SUPPORTED_SCHEMA[1]}.x)"
            )

    # ── search index (BM25 over chunks + claims) ─────────────────────
    def _build_index(self) -> None:
        for cid, chunk in self.chunks.items():
            head = " ".join(chunk.get("section_path", [])) + " " + chunk.get("label", "")
            self._add_doc("chunk", cid, _tokenize(head) * 2 + _tokenize(chunk.get("text", "")))
        for cid, claim in self.claims.items():
            statement, _ = clean_statement(claim.get("statement", ""))
            head = claim.get("label", "") + " " + claim.get("context", {}).get("description", "")
            self._add_doc("claim", cid, _tokenize(head) * 2 + _tokenize(statement))
        self._avg_len = sum(self._doc_len) / max(len(self._doc_len), 1)

    def _add_doc(self, kind: str, rec_id: str, tokens: list[str]) -> None:
        tf = Counter(tokens)
        self._docs.append((kind, rec_id))
        self._tf.append(tf)
        self._doc_len.append(len(tokens))
        for term in tf:
            self._df[term] += 1

    def search(
        self,
        query: str,
        *,
        kind: str = "all",
        area: str | None = None,
        epistemic_status: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Rank chunks and claims for ``query``. Filters are exact-match; ``area`` is the top-level doc area."""
        terms = _tokenize(query)
        if not terms or not self._docs:
            return []
        n_docs = len(self._docs)
        scored: list[tuple[float, str, str]] = []
        for i, (dkind, rec_id) in enumerate(self._docs):
            if kind != "all" and dkind != kind:
                continue
            if area and self._area_of(dkind, rec_id) != area:
                continue
            if epistemic_status and (
                dkind != "claim" or self.claims[rec_id].get("epistemic_status") != epistemic_status
            ):
                continue
            tf = self._tf[i]
            score = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                idf = math.log(1 + (n_docs - self._df[term] + 0.5) / (self._df[term] + 0.5))
                norm = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * self._doc_len[i] / self._avg_len)
                score += idf * f * (_BM25_K1 + 1) / norm
            if score > 0:
                scored.append((score, dkind, rec_id))
        scored.sort(key=lambda t: (-t[0], t[2]))
        return [
            {"score": round(score, 3), "kind": dkind, "id": rec_id}
            for score, dkind, rec_id in scored[: max(limit, 1)]
        ]

    def _area_of(self, kind: str, rec_id: str) -> str:
        if kind == "chunk":
            return self.chunks[rec_id].get("namespace_context", {}).get("area", "")
        prov = self.claims[rec_id].get("provenance") or [{}]
        path = prov[0].get("location", {}).get("path", "")
        return path.split("/", 1)[0]

    # ── lookup ───────────────────────────────────────────────────────
    def get(self, rec_id: str) -> dict[str, Any] | None:
        """Return any record by stable ID (chunk, claim or reference record)."""
        return self.lookup(rec_id)[0]

    def lookup(self, rec_id: str) -> tuple[dict[str, Any] | None, str | None]:
        """Resolve ``rec_id`` honouring id-registry aliases, deprecations and retirements.

        Returns ``(record, note)``; ``note`` explains any redirect or lifecycle state and must be shown.
        """
        note = None
        alias = self.aliases.get(rec_id)
        if alias:
            note = f"`{rec_id}` is an alias of `{alias['canonical_id']}` ({alias['reason']})."
            rec_id = alias["canonical_id"]
        rec = self._direct(rec_id)
        entry = self.lifecycle.get(rec_id)
        if entry:
            state = f"`{rec_id}` is {entry['lifecycle']}: {entry.get('reason', 'no reason given')}."
            note = f"{note} {state}" if note else state
            if rec is None:
                for successor in entry.get("replaced_by", []):
                    rec = self._direct(successor)
                    if rec:
                        note += f" Showing its replacement `{successor}`."
                        break
        return rec, note

    def _direct(self, rec_id: str) -> dict[str, Any] | None:
        return self.chunks.get(rec_id) or self.claims.get(rec_id) or self.registry.get(rec_id)

    def chunk_for_claim(self, claim: dict[str, Any]) -> dict[str, Any] | None:
        """Return the retrieval chunk of the section a claim was extracted from."""
        for prov in claim.get("provenance", []):
            chunk_id = self._chunk_by_section.get(prov.get("location", {}).get("section_id", ""))
            if chunk_id:
                return self.chunks[chunk_id]
        return None

    def registry_label(self, rec_id: str) -> str:
        rec = self.registry.get(rec_id)
        if not rec:
            return rec_id
        return rec.get("label") or rec.get("title") or rec_id

    def status(self) -> dict[str, Any]:
        """Identity and integrity summary for ``get_knowledge_status``."""
        by_status: Counter[str] = Counter(c.get("epistemic_status", "?") for c in self.claims.values())
        degraded = sum(1 for c in self.claims.values() if clean_statement(c.get("statement", ""))[1])
        registry_kinds: defaultdict[str, int] = defaultdict(int)
        for rec in self.registry.values():
            registry_kinds[rec.get("kind", "?")] += 1
        return {
            "loaded": self.loaded,
            "load_error": self.load_error,
            "kb_dir": str(self.kb_dir) if self.kb_dir else None,
            "generator_version": self.manifest.get("generator_version"),
            "schema_compatibility_version": self.manifest.get("schema_compatibility_version"),
            "input_content_sha256": self.manifest.get("input_content_sha256"),
            "hashes_verified": self.hashes_verified,
            "hash_mismatches": list(self.hash_mismatches),
            "chunks": len(self.chunks),
            "claims": len(self.claims),
            "claims_by_epistemic_status": dict(by_status.most_common()),
            "claims_with_degraded_statement": degraded,
            "reference_records": dict(registry_kinds),
        }
