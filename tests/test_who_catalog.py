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
    for absent in ("301", "311#T#M", "115#P", "215#P", "315#P"):
        assert absent not in who_4["what_commands"], absent
    for bare in ("115", "215", "315"):
        assert "#P" in who_4["what_commands"][bare]
    assert "1101-1103" in who_4["what_commands"]["115"] and "p. 40" in who_4["what_commands"]["115"]
    patterns = [w["pattern"] for w in who_4["where_forms"]]
    assert "^3#(0|[1-9][0-9]?)#([1-9])$" in patterns
    assert "^#([1-9][0-9]?)#(0[1-9]|[1-9][0-9]?)$" in patterns
    assert patterns.index("^3#(0|[1-9][0-9]?)#([1-9])$") < patterns.index("^([1-9][0-9]?)$")
    assert "^0(0[1-9]|[1-9][0-9])$" in patterns and "^([1-8])(0[1-9]|[1-9][0-9])$" in patterns
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



def test_who4_and_who2_catalogue_wording_follows_the_review():
    """Review 5659295137 on #24: SP scaling and crash scope of dimension 22, p. 56 for
    WHAT 23 / 24 / 30 / 31, the dimension 14 echo split, the WHO 2 notes and the
    canonical `WHO_4.pdf` filename."""
    catalog = WhoCatalog()
    who_4 = catalog.get_family(4)
    assert who_4["pdf_filename"] == "WHO_4.pdf"
    dim_22 = who_4["dimensions"]["22"]["description"]
    assert "tenths of a degree Celsius in 0.5 °C steps" in dim_22
    assert "`*0215*` = 21.5 °C" in dim_22
    assert "in 0.5 °C, " not in dim_22
    assert "F461 020011" in dim_22 and "bt_termo" in dim_22 and "OWNd (#136)" in dim_22
    assert "`thermo-dim22`" in dim_22 and "crash the thermoregulation daemon on 10 of 13" in dim_22
    assert "no replayed dimension 22 row" not in dim_22
    for what in ("23", "24", "30", "31"):
        assert "p. 56" in who_4["what_commands"][what] or "pp. 24, 56" in who_4["what_commands"][what], what
    dim_14 = who_4["dimensions"]["14"]["description"]
    assert "*#4*Z*0*T_measured##" in dim_14 and "pp. 8-9" in dim_14
    assert "`*4*110#T*#0##` or `*4*210#T*#0##`" in dim_14 and "never 310" in dim_14
    assert "301" in who_4["notes"] and "*4*312#T#D*WHERE##" in who_4["notes"]
    who_2 = catalog.get_family(2)
    assert "six WHATs (0, 1, 2, 10, 11, 12; p. 11)" in who_2["notes"]
    assert "only its Local bus row" in who_2["notes"]
    assert "`0#4#02`" in who_2["notes"] and "`<area>#4#<interface>` was not observed" in who_2["notes"]
    assert "point addresses only" not in who_2["notes"]


def test_who4_myhome_suite_forms_are_cited_as_implementation_evidence():
    """Encyclopedia who-4-temperature-control/dimensions.md: the dimension 7 presets and
    the dimension 11 write are MyHOME_Suite ScenarioDevices templates, not WHO_4.pdf;
    dimension 22 NULL fields are empty fields between `*`; `#Z#C` is not an actuator."""
    catalog = WhoCatalog()
    who_4 = catalog.get_family(4)
    dims = who_4["dimensions"]
    assert dims["7"]["query"] == "" and dims["7"]["write"] == "*#4*WHERE*#7*<CTX>*<STATE>*<T>##"
    assert "ScenarioDevices" in dims["7"]["description"] and "Not in WHO_4.pdf" in dims["7"]["description"]
    assert "*#4*ZAZB*#7*0*5*##" in dims["7"]["description"]
    assert list(dims)[:3] == ["0", "7", "11"]
    assert "ScenarioDevices" in dims["11"]["description"] and "*#4*ZAZB*#11*val##" in dims["11"]["description"]
    assert "implementation evidence" in dims["11"]["description"]
    assert "*#4*45#1*#22*3**1*1##" in dims["22"]["description"]
    assert "Never send the letters NULL" in dims["22"]["description"]
    assert "ScenarioDevices" in who_4["notes"] and "not an actuator" in who_4["notes"]
    assert "configured zone ZAZB" not in who_4["addressing"]
    assert "central-unit selector" in who_4["addressing"]
    zc = next(w for w in who_4["where_forms"] if w["pattern"] == "^#([1-9][0-9]?)#(0[1-9]|[1-9][0-9]?)$")
    assert "not an actuator address" in zc["description"]


def test_who13_catalog_follows_the_published_registry():
    """Encyclopedia who-13-integration-gateway/dimensions.md: 0 time, 1 date, 22 date-time
    (R/W); 10 IP, 11 netmask, 12 MAC, 16 firmware, 19 uptime (R); empty WHERE; no WHAT."""
    catalog = WhoCatalog()
    who_13 = catalog.get_family(13)
    dims = who_13["dimensions"]
    assert set(dims) == {"0", "1", "10", "11", "12", "16", "19", "22"}
    assert dims["1"]["name"] == "Date" and dims["1"]["write"] == "*#13**#1*<W>*<D>*<M>*<YYYY>##"
    assert dims["0"]["write"] == "*#13**#0*<H>*<M>*<S>*<T>##"
    assert dims["22"]["write"].startswith("*#13**#22*<H>*<M>*<S>*<T>*<W>")
    assert dims["16"]["name"] == "Firmware Version" and dims["16"]["write"] == ""
    assert dims["19"]["name"] == "Uptime" and dims["19"]["query"] == "*#13**19##"
    assert dims["12"]["query"] == "*#13**12##" and "decimal" in dims["12"]["description"]
    assert who_13["what_commands"] == {}
    assert "WHERE is empty" in who_13["addressing"]
    assert "Reboot" in who_13["notes"] and "dimension 15" in who_13["notes"]
    frames = {ex["frame"] for ex in who_13["examples"]}
    assert "*#13**16##" in frames and "*#13**#1*04*15*10*2026##" in frames and "*#13**1##" not in frames
    md = catalog.format_family_details(13)
    assert "No standard WHAT commands" in md and "### Dimension 1: Date" in md


def test_who18_catalog_follows_the_published_forms():
    """Encyclopedia who-18-energy-management/{addressing,what,dimensions}.md: WHERE 1N / 5N /
    7N#0, active power is 113, totalizers 51..54 / 72, 57 / 58 / 59 / 510 are the published
    series commands, 73#Time is in tens of minutes, 251 / 258 are one-bit flags."""
    catalog = WhoCatalog()
    who_18 = catalog.get_family(18)
    dims = who_18["dimensions"]
    for absent in ("1", "2", "3", "4", "11"):
        assert absent not in dims, absent
    assert dims["113"]["name"] == "Active Power" and "tariff" not in dims["113"]["name"].lower()
    assert "Not the active power" in dims["51"]["description"]
    assert dims["72"]["query"] == "*#18*WHERE*72#<Tot_N>##" and "Wh" in dims["72"]["description"]
    assert "forcing" not in dims["73"]["name"].lower() and "1..3" in dims["73"]["description"]
    assert "1..180" in dims["212"]["description"] and "TS10" in dims["212"]["name"]
    assert dims["251"]["name"] == "Stop&Go Open / Closed"
    assert "counter" not in dims["258"]["name"].lower() and "b8" in dims["258"]["description"]
    assert "EXCEEDED1*ENABLED1" in dims["516"]["description"] and "totalizer" not in dims["516"]["name"].lower()
    assert "Watts" not in dims["517"]["description"]
    assert dims["1200"]["query"] == "" and "1..255 minutes" in dims["1200"]["description"]
    whats = who_18["what_commands"]
    assert "TS10" not in whats["57#M#D"] and "511" in whats["57#M#D"]
    assert "514" in whats["510#M"] and "512" in whats["58#M"] and "513" in whats["59#M"]
    assert "self-test" in whats["23"] and "positive" not in whats["23"]
    assert "Time x 10 minutes" in whats["73#Time"] and "indefinite" not in whats["73#Time"].split("not")[0]
    assert "'1N' Stop&Go, N = 1..127" in who_18["addressing"] and "'7N#0'" in who_18["addressing"]
    assert "phase line" not in who_18["addressing"].split("No bare")[0]
    examples = {ex["frame"]: ex["description"] for ex in who_18["examples"]}
    assert "*#18*51*113##" in examples and "150 minutes" in examples["*18*73#15*71#0##"]
    assert "active power" not in examples["*#18*51*51##"].lower()
    md = catalog.format_family_details(18)
    assert "### Dimension 113: Active Power" in md and "Dimension 1: Instantaneous" not in md


def test_who4_zc_provenance_and_who18_series_read_forms_are_ts10():
    """Review follow-up: `#0#C` is the OPEN.db rule `#0#[ZA][ZB]`, `#Z#C` the touchscreen
    Configuration mapping; the 512..514 direct reads are TS10 old-PIC variants."""
    catalog = WhoCatalog()
    who_4 = catalog.get_family(4)
    assert "`#0#[ZA][ZB]`" in who_4["notes"] and "not an OPEN.db rule" in who_4["notes"]
    zc = next(w for w in who_4["where_forms"] if w["pattern"] == "^#([1-9][0-9]?)#(0[1-9]|[1-9][0-9]?)$")
    assert "OPEN.db / MHCatalogue" not in zc["description"] and "Historical central-unit variants" in zc["description"]
    dims = catalog.get_family(18)["dimensions"]
    for k in ("512", "513", "514"):
        assert "TS10" in dims[k]["name"] and "not a published query" in dims[k]["description"], k
