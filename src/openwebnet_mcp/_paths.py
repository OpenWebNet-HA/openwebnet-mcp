"""Path resolution and environment configuration for openwebnet-mcp."""

from __future__ import annotations

import os
from pathlib import Path


def get_package_root() -> Path:
    """Return the path to src/openwebnet_mcp."""
    return Path(__file__).resolve().parent


def get_project_root() -> Path:
    """Return the repository root (2 levels up from package root)."""
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """Return the path to the internal data directory."""
    return get_package_root() / "data"


def get_who_catalog_path() -> Path:
    """Return path to who_catalog.json (env overrideable)."""
    env_path = os.environ.get("OPENWEBNET_WHO_CATALOG_PATH")
    if env_path:
        return Path(env_path)
    return get_data_dir() / "who_catalog.json"


def get_protocol_grammar_path() -> Path:
    """Return path to protocol_grammar.json (env overrideable)."""
    env_path = os.environ.get("OPENWEBNET_GRAMMAR_PATH")
    if env_path:
        return Path(env_path)
    return get_data_dir() / "protocol_grammar.json"


def get_embedded_docs_dir() -> Path:
    """Return path to embedded documentation directory."""
    return get_data_dir() / "docs"


def get_external_docs_paths() -> list[Path]:
    """Return list of candidate external documentation directories to index."""
    candidates: list[Path] = []
    
    # Explicit env override
    env_docs = os.environ.get("OPENWEBNET_DOCS_PATH")
    if env_docs:
        for p in env_docs.split(os.pathsep):
            cand = Path(p.strip())
            if cand.exists():
                candidates.append(cand)

    # Standard adjacent directories if available
    project_root = get_project_root()
    parent_dir = project_root.parent

    myhome_docs = parent_dir / "MyHOME" / "docs"
    if myhome_docs.exists():
        candidates.append(myhome_docs)

    myhome_root = parent_dir / "MyHOME"
    if myhome_root.exists():
        candidates.append(myhome_root)

    wiki_dir = parent_dir / "OpenWebNet-HA_wiki"
    if wiki_dir.exists():
        candidates.append(wiki_dir)

    return candidates


def get_myhome_repo_path() -> Path | None:
    """Return path to MyHOME custom component repo if available."""
    env_repo = os.environ.get("MYHOME_REPO_PATH")
    if env_repo:
        p = Path(env_repo)
        if p.exists():
            return p

    cand = get_project_root().parent / "MyHOME"
    if cand.exists():
        return cand
    return None


def get_log_dir() -> Path:
    """Return path to directory where server logs are stored."""
    env_log = os.environ.get("OPENWEBNET_LOG_DIR")
    if env_log:
        p = Path(env_log)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Fallback to local project root
    p = get_project_root()
    return p
