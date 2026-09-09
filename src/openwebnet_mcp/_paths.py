"""Path resolution and environment configuration for openwebnet-mcp."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_NAME = "openwebnet-mcp"


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


def get_cache_dir() -> Path:
    """Return the platform-specific runtime cache directory.

    - Windows: %LOCALAPPDATA%/openwebnet-mcp/
    - Linux: $XDG_CACHE_HOME/openwebnet-mcp/ (defaults to ~/.cache/openwebnet-mcp/)
    - macOS: ~/Library/Caches/openwebnet-mcp/
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

    cache = base / _APP_NAME
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def get_log_dir() -> Path:
    """Return directory where server logs are stored.

    Resolution order:
    1. OPENWEBNET_LOG_DIR environment variable
    2. Platform cache directory (<cache_dir>/logs)
    """
    env_log = os.environ.get("OPENWEBNET_LOG_DIR")
    if env_log:
        p = Path(env_log)
        p.mkdir(parents=True, exist_ok=True)
        return p

    log_dir = get_cache_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_external_docs_paths() -> list[Path]:
    """Return list of candidate external documentation directories to index."""
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(cand: Path):
        norm = str(cand.resolve()) if cand.exists() else str(cand)
        if cand.exists() and norm not in seen:
            candidates.append(cand)
            seen.add(norm)

    # Explicit env override
    env_docs = os.environ.get("OPENWEBNET_DOCS_PATH")
    if env_docs:
        for p in env_docs.split(os.pathsep):
            cand = Path(p.strip())
            _add(cand)

    # Standard adjacent directories
    project_root = get_project_root()
    parent_dir = project_root.parent

    if parent_dir.exists():
        _add(parent_dir / "MyHOME" / "docs")
        _add(parent_dir / "MyHOME")
        _add(parent_dir / "OpenWebNet-HA_wiki")
        _add(parent_dir / "who16_doc.txt")

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


def get_ownd_repo_path() -> Path | None:
    """Return path to OWNd repository if available."""
    env_repo = os.environ.get("OWND_REPO_PATH")
    if env_repo:
        p = Path(env_repo)
        if p.exists():
            return p

    cand = get_project_root().parent / "OWNd"
    if cand.exists():
        return cand
    return None
