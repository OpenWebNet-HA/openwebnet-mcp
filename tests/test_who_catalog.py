"""Tests for WhoCatalog provider."""

import pytest
from openwebnet_mcp.who_catalog import WhoCatalog


def test_who_catalog_loading():
    catalog = WhoCatalog()
    families = catalog.list_all()
    assert len(families) >= 20
    
    # Verify core families
    who_1 = catalog.get_family(1)
    assert who_1 is not None
    assert who_1["name"] == "Lighting"
    assert "F411" in str(who_1["hardware_models"])
    assert "1" in who_1["dimensions"]

    who_2 = catalog.get_family(2)
    assert who_2 is not None
    assert who_2["name"] == "Automation (Covers & Shutters)"

    who_4 = catalog.get_family(4)
    assert who_4 is not None
    assert who_4["name"] == "Heating / Thermoregulation"


def test_who_catalog_search():
    catalog = WhoCatalog()
    
    # Search by exact number
    res_1 = catalog.search("1")
    assert any(f["who"] == 1 for f in res_1)

    # Search by who=1 format
    res_who_eq = catalog.search("who=1")
    assert any(f["who"] == 1 for f in res_who_eq)

    # Search by text
    res_light = catalog.search("lighting")
    assert any(f["who"] == 1 for f in res_light)

    # Search by platform
    res_climate = catalog.search("climate")
    assert any(f["who"] == 4 for f in res_climate)

    # Search empty string returns all
    all_f = catalog.search("")
    assert len(all_f) == len(catalog.list_all())


def test_format_family_details():
    catalog = WhoCatalog()
    
    details_1 = catalog.format_family_details(1)
    assert "WHO = 1: Lighting" in details_1
    assert "WHO_1.pdf" in details_1
    assert "WHAT Commands" in details_1
    assert "DIMENSIONS" in details_1

    # Invalid WHO
    details_unknown = catalog.format_family_details(99999)
    assert "**Error**" in details_unknown


def test_format_summary_markdown():
    catalog = WhoCatalog()
    summary = catalog.format_summary_markdown()
    assert "# OpenWebNet Master WHO Catalog" in summary
    assert "| **1** | Lighting" in summary
    assert "| **4** | Heating / Thermoregulation" in summary


def test_missing_catalog_file(tmp_path):
    fake_path = tmp_path / "non_existent.json"
    empty_cat = WhoCatalog(catalog_path=fake_path)
    assert len(empty_cat.list_all()) == 0


def test_malformed_catalog_file(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not_json", encoding="utf-8")
    with pytest.raises(Exception):
        WhoCatalog(catalog_path=bad_file)


def test_format_family_details_empty_sections(tmp_path):
    custom_file = tmp_path / "empty_sections.json"
    custom_file.write_text(
        '{"families": [{"who": 99, "name": "Empty Family", "what_commands": {}, "dimensions": {}, "examples": []}]}',
        encoding="utf-8",
    )
    cat = WhoCatalog(catalog_path=custom_file)
    md = cat.format_family_details(99)
    assert "No standard WHAT commands" in md
    assert "No dimension parameters defined" in md
    assert "No examples provided" in md
