"""Tests for AstIndexer module."""

import pytest
from pathlib import Path
from openwebnet_mcp.ast_indexer import AstIndexer


def test_ast_builtin_reference():
    indexer = AstIndexer(repo_path=None)
    assert len(indexer._cache) >= 4

    light_sym = indexer.get_symbol("MyHOMELight")
    assert light_sym is not None
    assert "async_turn_on" in light_sym["methods"]
    assert "LightEntityFeature.TRANSITION" in light_sym["supported_features"][0]

    cover_sym = indexer.get_symbol("MyHOMECover")
    assert cover_sym is not None
    assert "async_open_cover" in cover_sym["methods"]

    msg_sym = indexer.get_symbol("OWNMessage")
    assert msg_sym is not None


def test_format_symbol_markdown():
    indexer = AstIndexer(repo_path=None)
    md = indexer.format_symbol_markdown("MyHOMELight")
    assert "# `MyHOMELight`" in md
    assert "async_turn_on" in md
    assert "Supported Entity Features" in md

    # Unknown symbol
    md_err = indexer.format_symbol_markdown("NonExistentClass")
    assert "**Error**" in md_err

    # Symbol with no public methods
    indexer._cache["EmptyClass"] = {
        "class_name": "EmptyClass",
        "module": "test.empty",
        "methods": {},
        "supported_features": [],
    }
    md_empty = indexer.format_symbol_markdown("EmptyClass")
    assert "No public methods found" in md_empty


def test_ast_parsing_complex_signatures(tmp_path):
    repo = tmp_path / "repo"
    custom_comp = repo / "custom_components" / "myhome"
    custom_comp.mkdir(parents=True)

    py_code = """
class ComplexEntity:
    def execute(self, a: int, *args: str, flag: bool = False, **kwargs: dict) -> bool:
        \"\"\"Complex docstring\"\"\"
        return True
"""
    (custom_comp / "complex.py").write_text(py_code, encoding="utf-8")

    # Also write a syntax-broken python file to test resilience
    (custom_comp / "broken.py").write_text("def syntax_error(:", encoding="utf-8")

    indexer = AstIndexer(repo_path=repo, ownd_path=None)
    sym = indexer.get_symbol("ComplexEntity")
    assert sym is not None
    assert "*args" in sym["methods"]["execute"]
    assert "**kwargs" in sym["methods"]["execute"]
    assert "-> bool" in sym["methods"]["execute"]
    assert "flag: bool=False" in sym["methods"]["execute"]


def test_ast_property_and_defaults(tmp_path):
    ownd_dir = tmp_path / "OWNd" / "OWNd"
    ownd_dir.mkdir(parents=True)

    py_code = """
class OWNEvent:
    @property
    def is_valid(self) -> bool:
        return True

    def configure(self, mode: str, speed: int = 5, *, timeout: int = 10) -> None:
        pass

    def pos_only(self, x: int = 1, /, y: int = 2) -> None:
        pass
"""
    (ownd_dir / "event.py").write_text(py_code, encoding="utf-8")

    indexer = AstIndexer(repo_path=None, ownd_path=tmp_path / "OWNd")
    sym = indexer.get_symbol("OWNEvent")
    assert sym is not None
    assert "@property is_valid -> bool" in sym["methods"]["is_valid"]
    assert "speed: int=5" in sym["methods"]["configure"]
    assert "timeout: int=10" in sym["methods"]["configure"]

    # Test Class.method lookup syntax
    sym_method = indexer.get_symbol("OWNEvent.configure")
    assert sym_method is not None
    assert "configure" in sym_method["methods"]
    assert "speed: int=5" in sym_method["methods"]["configure"]

    # Test empty query
    assert indexer.get_symbol("") is None


def test_ast_top_level_functions(tmp_path):
    repo = tmp_path / "MyHOME"
    custom_comp = repo / "custom_components" / "myhome"
    custom_comp.mkdir(parents=True)

    code = """
async def async_setup_entry(hass, entry) -> bool:
    \"\"\"Setup integration entry.\"\"\"
    return True
"""
    (custom_comp / "__init__.py").write_text(code, encoding="utf-8")

    indexer = AstIndexer(repo_path=repo, ownd_path=None)
    func_sym = indexer.get_symbol("async_setup_entry")
    assert func_sym is not None
    assert "async def async_setup_entry" in func_sym["methods"]["async_setup_entry"]


