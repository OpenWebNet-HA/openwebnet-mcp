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


def test_who4_dimensions_and_where_forms():
    catalog = WhoCatalog()
    who_4 = catalog.get_family(4)
    dims = who_4["dimensions"]
    assert {"0", "11", "12", "13", "14", "19", "20", "22", "60"} <= set(dims)
    assert dims["19"]["name"] == "Valve Status"
    assert dims["19"]["write"] == ""
    assert dims["20"]["name"] == "Actuator Status"
    assert dims["20"]["write"] == ""
    assert "ON Fan Coil" in dims["20"]["description"]
    assert dims["60"]["name"] == "Relative Humidity"
    assert dims["60"]["write"] == ""
    assert "F459" in dims["60"]["description"]
    assert "NOT implemented in gateway WHO=4 translators" in who_4["addressing"]
    patterns = {wf["pattern"] for wf in who_4["where_forms"]}
    assert "^#0$" in patterns
    assert "^([1-9][0-9]?)#([1-9])$" in patterns


def test_who4_catalog_follows_the_legrand_document():
    """WHO_4.pdf (v2.0.0): dimension 22 is the split-unit control, the knob offset is 13,
    the mode WHATs are 102 / 202 / 302 / 303 / 311 on `#Z`, and 100 / 101 / 103 / 301
    are not WHAT codes (openwebnet-mcp#23)."""
    catalog = WhoCatalog()
    who_4 = catalog.get_family(4)
    dims = who_4["dimensions"]
    assert "Split" in dims["22"]["name"]
    assert "knob" not in dims["22"]["name"].lower()
    assert dims["22"]["query"] == "*#4*3#Z#N*22##"
    assert "knob" in dims["13"]["name"].lower()
    for present in ("102", "202", "302", "303", "311", "40", "3000", "3100", "3200"):
        assert present in who_4["what_commands"], present
    for absent in ("100", "101"):
        assert absent not in who_4["what_commands"], absent
    assert "reply only" in who_4["what_commands"]["103"]
    assert "NOT in the Legrand document" in who_4["what_commands"]["301"]
    assert "*4*311*#Z##" in who_4["what_commands"]["311"]
    assert "*4*303*#Z##" in who_4["what_commands"]["303"]
    assert {(r["from"], r["to"]) for r in who_4["what_ranges"]} >= {(1101, 1103), (1201, 1216), (13001, 13255)}
    assert "31" in dims and "30" in dims
    assert "CV = conditioning valve first" in dims["19"]["description"]
    assert not any("#0#([1-4])" in w["pattern"] for w in who_4["where_forms"])
    assert any("#0#" in w["pattern"] and "[1-9][0-9]?" in w["pattern"] for w in who_4["where_forms"])
    md = catalog.format_family_details(4)
    assert "Split Control" in md
    assert "Local Knob Offset" not in md
    assert "| `1101..1103` |" in md
    assert not any(ex["frame"] == "*4*110*1##" for ex in who_4["examples"])


def test_who2_catalog_follows_the_legrand_document():
    """WHO_2.pdf (v1.0): dimension 10 is the status read, dimension 11 the GoToLevel write,
    and there is no tilt dimension (openwebnet-mcp#23)."""
    catalog = WhoCatalog()
    who_2 = catalog.get_family(2)
    dims = who_2["dimensions"]
    assert set(dims) == {"10", "11"}
    assert dims["10"]["write"] == ""
    assert "<STATUS>*<LEVEL>*<PRIORITY>*<INFO>" in dims["10"]["description"]
    assert dims["11"]["query"] == ""
    assert dims["11"]["write"] == "*#2*WHERE*#11#<PRIORITY>*<LEVEL>##"
    md = catalog.format_family_details(2)
    assert "Slat / Louvre Tilt" not in md
    assert not any("tilt" in dim["name"].lower() for dim in dims.values())
    assert "*#2*21*#10*75##" not in md
    assert "*#2*21*#11#001*75##" in md

