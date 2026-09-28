"""Download a Machine KB release into the local cache.

Usage:  python -m openwebnet_mcp.kb_fetch [TAG]     (default: machine-kb-v0.1.0)

Fetches ``knowledge/manifest.json`` from the tagged Encyclopedia revision, then every
manifest-listed data artifact (schemas are skipped), verifying each SHA-256 before it is
written. Nothing is loaded unless the whole set verifies.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

from openwebnet_mcp._paths import get_cache_dir

DEFAULT_TAG = "machine-kb-v0.1.0"
RAW_URL = "https://raw.githubusercontent.com/OpenWebNet-HA/OpenWebNet-Encyclopedia/{tag}/{path}"
_DATA_KINDS = {"claim_records", "id_registry", "llm_corpus", "reference_registry", "retrieval_chunks"}


_TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _safe_target(target: Path, rel: str) -> Path:
    """Return ``target / rel``, refusing manifest paths that leave the ``knowledge/`` tree."""
    parts = Path(rel).parts
    out = (target / rel).resolve()
    if not parts or parts[0] != "knowledge" or ".." in parts or not out.is_relative_to(target.resolve()):
        raise ValueError(f"unsafe manifest path {rel!r}; nothing was written")
    return out


def _download(tag: str, path: str) -> bytes:
    url = RAW_URL.format(tag=tag, path=path)
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - fixed https host
        return resp.read()


def fetch(tag: str = DEFAULT_TAG) -> Path:
    """Fetch and verify ``tag``; return the resulting ``knowledge`` directory."""
    if not _TAG_RE.fullmatch(tag) or ".." in tag:
        raise ValueError(f"invalid tag {tag!r}")
    manifest_bytes = _download(tag, "knowledge/manifest.json")
    manifest = json.loads(manifest_bytes)
    staged: dict[str, bytes] = {"knowledge/manifest.json": manifest_bytes}
    for art in manifest["artifacts"]:
        if art["kind"] not in _DATA_KINDS:
            continue
        _safe_target(get_cache_dir() / "machine-kb" / tag, art["path"])  # validate before downloading
        data = _download(tag, art["path"])
        if hashlib.sha256(data).hexdigest() != art["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {art['path']} at {tag}; nothing was written")
        staged[art["path"]] = data

    target = get_cache_dir() / "machine-kb" / tag
    for rel, data in staged.items():
        out = _safe_target(target, rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return target / "knowledge"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    tag = args[0] if args else DEFAULT_TAG
    try:
        kb_dir = fetch(tag)
    except (OSError, ValueError) as err:
        print(f"kb_fetch failed: {err}", file=sys.stderr)
        return 1
    print(f"Machine KB {tag} verified and stored in {kb_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
