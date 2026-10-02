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


def test_format_family_details_renders_what_ranges():
    catalog = WhoCatalog()
    details_16 = catalog.format_family_details(16)
    assert "| `1001..1015` | Increase volume by 1-15 steps" in details_16
    assert "| `1101..1115` | Decrease volume by 1-15 steps" in details_16


def test_format_family_details_ranges_only(tmp_path):
    custom_file = tmp_path / "ranges_only.json"
    custom_file.write_text(
        '{"families": [{"who": 98, "name": "Ranges Only", "what_commands": {},'
        ' "what_ranges": [{"from": 10, "to": 19, "description": "Step by 0-9"}]}]}',
        encoding="utf-8",
    )
    md = WhoCatalog(catalog_path=custom_file).format_family_details(98)
    assert "| `10..19` | Step by 0-9 |" in md
    assert "No standard WHAT commands" not in md


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


def test_who5_alarm_vocabulary_is_activation_and_engage_not_arm():
    """WHO_5.pdf / Encyclopedia who-5-alarm: WHAT 1 is "activation", WHAT 8 "engage".

    Regression: the catalog once read 1 = "Arm system (Total)" and 0 = "Disarm".
    Field captures show arming as *5*1*0## then *5*8*0## and disarming as
    *5*2*0##, *5*1*0##, *5*9*0##, so WHAT 1 is not the armed state.
    """
    catalog = WhoCatalog()
    who_5 = catalog.get_family(5)
    whats = who_5["what_commands"]

    assert whats["1"].startswith("Activation")
    assert whats["8"].startswith("Engage")
    assert whats["0"].startswith("Maintenance")
    assert whats["9"].startswith("Disengage")
    assert whats["15"].startswith("Intrusion alarm")
    assert set(whats) == {str(n) for n in [*range(19), 26, 27, 31]}
    assert "arm system" not in whats["1"].lower()

    # Examples must not present report values as arm/disarm commands.
    frames = {ex["frame"] for ex in who_5["examples"]}
    assert "*5*0*0##" not in frames
    assert all("Arm the" not in ex["description"] for ex in who_5["examples"])

    # Zones are #-prefixed selectors, not '1'..'8'.
    assert "`#1`..`#8`" in who_5["addressing"]

    spec = catalog.format_family_details(5)
    assert "| `1` | Activation" in spec
    assert "| `8` | Engage" in spec
    assert "## Notes" in spec and "not that it is armed" in spec
