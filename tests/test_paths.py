"""Tests for _paths module."""

import os
from pathlib import Path
from openwebnet_mcp import _paths


def test_paths_resolution():
    pkg_root = _paths.get_package_root()
    assert pkg_root.exists()
    assert (pkg_root / "__init__.py").exists()

    proj_root = _paths.get_project_root()
    assert proj_root.exists()
    assert (proj_root / "pyproject.toml").exists()

    data_dir = _paths.get_data_dir()
    assert data_dir.exists()

    catalog_path = _paths.get_who_catalog_path()
    assert catalog_path.exists()

    grammar_path = _paths.get_protocol_grammar_path()
    assert grammar_path.exists()

    embedded_docs = _paths.get_embedded_docs_dir()
    assert embedded_docs.exists()


def test_path_environment_overrides(monkeypatch, tmp_path):
    fake_catalog = tmp_path / "custom_catalog.json"
    fake_grammar = tmp_path / "custom_grammar.json"
    fake_log = tmp_path / "logs"

    monkeypatch.setenv("OPENWEBNET_WHO_CATALOG_PATH", str(fake_catalog))
    monkeypatch.setenv("OPENWEBNET_GRAMMAR_PATH", str(fake_grammar))
    monkeypatch.setenv("OPENWEBNET_LOG_DIR", str(fake_log))

    assert _paths.get_who_catalog_path() == fake_catalog
    assert _paths.get_protocol_grammar_path() == fake_grammar
    assert _paths.get_log_dir() == fake_log
    assert fake_log.exists()


def test_external_docs_paths(monkeypatch, tmp_path):
    doc_dir1 = tmp_path / "doc1"
    doc_dir1.mkdir()
    monkeypatch.setenv("OPENWEBNET_DOCS_PATH", str(doc_dir1))

    paths = _paths.get_external_docs_paths()
    assert doc_dir1 in paths


def test_myhome_repo_path(monkeypatch, tmp_path):
    repo_dir = tmp_path / "MyHOME"
    repo_dir.mkdir()
    monkeypatch.setenv("MYHOME_REPO_PATH", str(repo_dir))

    p = _paths.get_myhome_repo_path()
    assert p == repo_dir

    # Non-existent env path falls through
    monkeypatch.setenv("MYHOME_REPO_PATH", str(tmp_path / "does_not_exist"))
    with monkeypatch.context() as m:
        m.setattr(_paths, "get_project_root", lambda: tmp_path / "dummy" / "dummy")
        assert _paths.get_myhome_repo_path() is None


def test_cache_and_log_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENWEBNET_LOG_DIR", raising=False)
    cache = _paths.get_cache_dir()
    assert cache.exists()
    assert cache.name == "openwebnet-mcp"

    log_dir = _paths.get_log_dir()
    assert log_dir.exists()
    assert log_dir.name == "logs"

    # Test darwin platform branch
    with monkeypatch.context() as m:
        m.setattr(_paths.sys, "platform", "darwin")
        m.setattr(_paths.Path, "home", lambda: tmp_path / "home")
        cache_darwin = _paths.get_cache_dir()
        assert cache_darwin.name == "openwebnet-mcp"

    # Test linux / other platform branch
    with monkeypatch.context() as m:
        m.setattr(_paths.sys, "platform", "linux")
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        cache_linux = _paths.get_cache_dir()
        assert cache_linux.name == "openwebnet-mcp"



def test_ownd_repo_path(monkeypatch, tmp_path):
    repo_dir = tmp_path / "OWNd"
    repo_dir.mkdir()
    monkeypatch.setenv("OWND_REPO_PATH", str(repo_dir))

    p = _paths.get_ownd_repo_path()
    assert p == repo_dir

    monkeypatch.setenv("OWND_REPO_PATH", str(tmp_path / "does_not_exist"))
    with monkeypatch.context() as m:
        m.setattr(_paths, "get_project_root", lambda: tmp_path / "dummy" / "dummy")
        assert _paths.get_ownd_repo_path() is None

