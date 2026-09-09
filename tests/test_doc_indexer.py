"""Tests for DocIndexer and documentation search."""

import pytest
from pathlib import Path
from openwebnet_mcp.doc_indexer import DocIndexer


def test_doc_indexer_indexing():
    indexer = DocIndexer()
    assert len(indexer.sections) > 10
    assert len(indexer.docs_by_topic) >= 5


def test_doc_search_query():
    indexer = DocIndexer()

    # Search for transition
    hits_trans = indexer.search("transition")
    assert len(hits_trans) > 0
    assert any("transition" in h["content"].lower() or "transition" in h["heading"].lower() for h in hits_trans)

    # Search for CEN
    hits_cen = indexer.search("cen pushbutton")
    assert len(hits_cen) > 0

    # Search with empty query returns top sections
    hits_empty = indexer.search("")
    assert len(hits_empty) > 0


def test_get_guide():
    indexer = DocIndexer()

    guide_lighting = indexer.get_guide("lighting")
    assert guide_lighting is not None
    assert "Lighting Platform Configuration" in guide_lighting

    guide_cen = indexer.get_guide("cen_scenarios")
    assert guide_cen is not None
    assert "CEN" in guide_cen

    # Non-existent guide
    guide_none = indexer.get_guide("completely_unknown_topic_xyz")
    assert guide_none is None


def test_table_of_contents():
    indexer = DocIndexer()
    toc = indexer.get_table_of_contents()
    assert "# OpenWebNet & MyHOME Documentation Table of Contents" in toc
    assert "lighting_guide" in toc


def test_external_doc_indexing(tmp_path):
    ext_dir = tmp_path / "custom_docs"
    ext_dir.mkdir()
    (ext_dir / "custom_note.md").write_text("# Custom Note\nThis is a custom openwebnet note.", encoding="utf-8")

    indexer = DocIndexer(external_paths=[ext_dir])
    hits = indexer.search("custom openwebnet note")
    assert len(hits) > 0
    assert any("custom openwebnet note" in h["content"].lower() for h in hits)

    # Category filter
    hits_cat = indexer.search("custom openwebnet note", category="external_reference")
    assert len(hits_cat) > 0

    hits_cat_miss = indexer.search("custom openwebnet note", category="non_existent_category")
    assert len(hits_cat_miss) == 0


def test_get_guide_fuzzy_and_substring():
    indexer = DocIndexer()
    # Substring match
    guide = indexer.get_guide("light")
    assert guide is not None
    assert "Lighting" in guide

    # Fuzzy match with slight typo (e.g. 'ligting')
    guide_fuzzy = indexer.get_guide("ligting")
    assert guide_fuzzy is not None
    assert "Lighting" in guide_fuzzy


def test_doc_indexer_unreadable_file(tmp_path, monkeypatch):
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("# Bad File", encoding="utf-8")
    
    indexer = DocIndexer()
    with monkeypatch.context() as m:
        def err_read(*args, **kwargs):
            raise PermissionError("Access denied")
        m.setattr(Path, "read_text", err_read)
        indexer._index_file(bad_file, "error_cat")
