"""Tests for FrameGenerator."""

import pytest
from openwebnet_mcp.frame_generator import FrameGenerator


def test_build_frame_command():
    gen = FrameGenerator()
    frame, parsed = gen.build_frame(who=1, command_type="command", where="12", what=1)
    assert frame == "*1*1*12##"
    assert parsed.is_valid is True
    assert parsed.who == 1


def test_build_frame_status_request():
    gen = FrameGenerator()
    frame, parsed = gen.build_frame(who=1, command_type="status_request", where="12")
    assert frame == "*#1*12##"
    assert parsed.is_valid is True


def test_build_frame_dimension_request():
    gen = FrameGenerator()
    frame, parsed = gen.build_frame(who=4, command_type="dimension_request", where="1", dimension=0)
    assert frame == "*#4*1*0##"
    assert parsed.is_valid is True


def test_build_frame_dimension_writing():
    gen = FrameGenerator()
    frame, parsed = gen.build_frame(who=1, command_type="dimension_writing", where="12", dimension=1, values=["50", "5"])
    assert frame == "*#1*12*#1*50*5##"
    assert parsed.is_valid is True


def test_build_frame_invalid_types():
    gen = FrameGenerator()
    with pytest.raises(ValueError):
        gen.build_frame(who=1, command_type="command", where="12", what=None)

    with pytest.raises(ValueError):
        gen.build_frame(who=1, command_type="dimension_request", where="12", dimension=None)

    with pytest.raises(ValueError):
        gen.build_frame(who=1, command_type="dimension_writing", where="12", dimension=None)

    with pytest.raises(ValueError):
        gen.build_frame(who=1, command_type="unknown_type", where="12")


def test_generate_lighting():
    gen = FrameGenerator()
    assert gen.generate_lighting("12", "on") == "*1*1*12##"
    assert gen.generate_lighting("12", "off") == "*1*0*12##"
    assert gen.generate_lighting("12", "on", transition_speed=5) == "*1*1#5*12##"
    assert gen.generate_lighting("12", "dim", brightness_pct=75, transition_speed=2) == "*#1*12*#1*75*2##"
    assert gen.generate_lighting("12", "toggle") == "*1*13*12##"

    with pytest.raises(ValueError):
        gen.generate_lighting("12", "invalid_action")


def test_generate_cover():
    gen = FrameGenerator()
    assert gen.generate_cover("21", "up") == "*2*1*21##"
    assert gen.generate_cover("21", "down") == "*2*2*21##"
    assert gen.generate_cover("21", "stop") == "*2*0*21##"
    # WHO_2.pdf p. 20: the level write is the dimension 11 GoToLevel with a
    # priority; dimension 10 is the read-only status and has no write form.
    assert gen.generate_cover("21", "position", position_pct=60) == "*#2*21*#11#001*60##"
    assert gen.generate_cover("21", "position", position_pct=0) == "*#2*21*#11#001*0##"
    assert gen.generate_cover("21", "position", position_pct=100) == "*#2*21*#11#001*100##"
    assert "*#10*" not in gen.generate_cover("21", "position", position_pct=60)

    with pytest.raises(ValueError, match="0..100"):
        gen.generate_cover("21", "position", position_pct=101)
    with pytest.raises(ValueError, match="position_pct"):
        gen.generate_cover("21", "position")
    with pytest.raises(ValueError):
        gen.generate_cover("21", "invalid_action")


def test_generate_climate_central_unit_plant():
    """Default plant: the zone is addressed through the central unit (`#Z`) for
    both the set point (WHO_4.pdf p. 8) and the mode commands (pp. 9-11)."""
    gen = FrameGenerator()
    assert gen.generate_climate(zone=1, target_temp=21.5, mode="heat") == "*#4*#1*#14*0215*1##"
    assert gen.generate_climate(zone=1, target_temp=24.0, mode="cool") == "*#4*#1*#14*0240*2##"
    assert gen.generate_climate(zone=1, target_temp=21.0, mode="generic") == "*#4*#1*#14*0210*3##"
    assert gen.generate_climate(zone=1, target_temp=21.0) == "*#4*#1*#14*0210*1##"
    assert gen.generate_climate(zone="12", target_temp=5.0, mode="heating") == "*#4*#12*#14*0050*1##"
    # WHO_4.pdf: OFF is WHAT 303, anti-freeze 102, protection 202 and the
    # automatic program 311, all on the zone via the central unit (pp. 9-11);
    # WHATs 100 / 101 / 110 / 301 are not commands in the document.
    assert gen.generate_climate(zone=1, mode="off") == "*4*303*#1##"
    assert gen.generate_climate(zone=1, mode="antifreeze") == "*4*102*#1##"
    assert gen.generate_climate(zone=1, mode="anti-freeze") == "*4*102*#1##"
    assert gen.generate_climate(zone=1, mode="protection") == "*4*202*#1##"
    assert gen.generate_climate(zone=1, mode="auto") == "*4*311*#1##"
    # The central unit itself (#0, pp. 23-27)
    assert gen.generate_climate(zone=0, mode="off") == "*4*303*#0##"
    assert gen.generate_climate(zone=0, target_temp=20.0, mode="cool") == "*#4*#0*#14*0200*2##"


def test_generate_climate_standalone_plant():
    """Thermostats without a central unit take the bare zone for both forms
    (live F461 / MyHomeServer1 plants); `#Z` is a no-op there."""
    gen = FrameGenerator()
    assert gen.generate_climate(zone=2, target_temp=21.5, mode="heat", standalone=True) == "*#4*2*#14*0215*1##"
    assert gen.generate_climate(zone=2, mode="off", standalone=True) == "*4*303*2##"
    assert gen.generate_climate(zone=2, mode="auto", standalone=True) == "*4*311*2##"
    with pytest.raises(ValueError, match="standalone plant has none"):
        gen.generate_climate(zone=0, mode="off", standalone=True)


def test_generate_climate_zone_validation():
    gen = FrameGenerator()
    # A leading '#' is stripped: the addressing form is chosen by `standalone`.
    assert gen.generate_climate(zone="#1", mode="off") == "*4*303*#1##"
    assert gen.generate_climate(zone="#1", mode="off", standalone=True) == "*4*303*1##"
    assert "##1" not in gen.generate_climate(zone="#1", mode="off")
    for bad in ("100", "-1", "a", "", "1#4#01"):
        with pytest.raises(ValueError, match="zone must be"):
            gen.generate_climate(zone=bad, mode="off")
    # *4*311*#0## is not in WHO_4.pdf and is NACKed by H4684 / MH200.
    with pytest.raises(ValueError, match="not in WHO_4.pdf"):
        gen.generate_climate(zone=0, mode="auto")


def test_generate_climate_mode_validation():
    gen = FrameGenerator()
    # Modes match on their whole name, not on substrings.
    for unknown in ("auto_cool", "cool_off", "eco", "heat_off", "offline"):
        with pytest.raises(ValueError, match="Unknown climate mode"):
            gen.generate_climate(zone=1, target_temp=21.0, mode=unknown)
    with pytest.raises(ValueError, match="Unknown climate mode"):
        gen.generate_climate(zone=1, mode="eco")
    # A manual mode needs a set point; a mode-only command must not carry one.
    with pytest.raises(ValueError, match="dimension 14"):
        gen.generate_climate(zone=2, mode="heat")
    with pytest.raises(ValueError, match="dimension 14"):
        gen.generate_climate(zone=2)
    for mode_only in ("off", "antifreeze", "protection", "auto"):
        with pytest.raises(ValueError, match="mode-only command"):
            gen.generate_climate(zone=1, target_temp=21.0, mode=mode_only)


def test_generate_climate_setpoint_validation():
    """WHO_4.pdf pp. 8, 23: T = 0050..0400 by 0.5° step."""
    gen = FrameGenerator()
    assert gen.generate_climate(zone=1, target_temp=40.0, mode="heat") == "*#4*#1*#14*0400*1##"
    assert gen.generate_climate(zone=1, target_temp=5.0, mode="heat") == "*#4*#1*#14*0050*1##"
    for bad in (4.5, 40.5, 21.3, 21.25, 0.0, -5.0, 20.04, 40.04, 4.96):
        with pytest.raises(ValueError, match="0.5 °C steps"):
            gen.generate_climate(zone=1, target_temp=bad, mode="heat")


def test_generate_cen():
    gen = FrameGenerator()
    # CEN (WHO=15): *15*BUTTON[#PHASE]*WHERE##
    assert gen.generate_cen("22", button=2, press_type="short") == "*15*02*22##"
    assert gen.generate_cen("22", button=2, press_type="short_release") == "*15*02#1*22##"
    assert gen.generate_cen("22", button=2, press_type="start_long") == "*15*02#3*22##"
    assert gen.generate_cen("22", button=2, press_type="held") == "*15*02#3*22##"
    assert gen.generate_cen("22", button=2, press_type="release") == "*15*02#2*22##"
    assert gen.generate_cen("22", button=2, press_type="long_release") == "*15*02#2*22##"
    assert gen.generate_cen("36#4#01", button=6) == "*15*06*36#4#01##"
    with pytest.raises(ValueError, match="between 0 and 31"):
        gen.generate_cen("22", button=32)

    # CEN+ (WHO=25): *25*WHAT#PUSHBUTTON*WHERE##, WHERE "21" = Object 1
    assert gen.generate_cen("21", button=1, press_type="short", is_cen_plus=True) == "*25*21#1*21##"
    assert gen.generate_cen("21", button=1, press_type="start_long", is_cen_plus=True) == "*25*22#1*21##"
    assert gen.generate_cen("21", button=1, press_type="held", is_cen_plus=True) == "*25*23#1*21##"
    assert gen.generate_cen("21", button=1, press_type="release", is_cen_plus=True) == "*25*24#1*21##"
    assert gen.generate_cen("21", button=1, press_type="long_release", is_cen_plus=True) == "*25*24#1*21##"
    with pytest.raises(ValueError, match="no short-release frame"):
        gen.generate_cen("21", button=1, press_type="short_release", is_cen_plus=True)
    with pytest.raises(ValueError, match="CEN\\+ button must be between 0 and 31"):
        gen.generate_cen("21", button=32, is_cen_plus=True)


def test_generate_ha_yaml():
    gen = FrameGenerator()
    
    # Light
    yaml_light = gen.generate_ha_yaml("light", "Living Room Light", "12", dimmable=True, transition=5)
    assert "lights:" in yaml_light
    assert 'where: "12"' in yaml_light
    assert "dimmable: true" in yaml_light
    assert "transition: 5" in yaml_light

    # Cover
    yaml_cover = gen.generate_ha_yaml("cover", "Kitchen Shutter", "21", run_time=20.5)
    assert "covers:" in yaml_cover
    assert "run_time: 20.5" in yaml_cover

    # Climate
    yaml_climate = gen.generate_ha_yaml("climate", "Zone 1", "1", heat_support=True)
    assert "climates:" in yaml_climate
    assert "zone: 1" in yaml_climate

    # Sensor
    yaml_sensor = gen.generate_ha_yaml("sensor", "Power Meter", "1", type="power")
    assert "sensors:" in yaml_sensor

    # Switch
    yaml_sw = gen.generate_ha_yaml("switch", "Relay Load", "15")
    assert "switches:" in yaml_sw

    # Media Player
    yaml_mp = gen.generate_ha_yaml("media_player", "Dining Audio", "1")
    assert "media_players:" in yaml_mp

    # Binary Sensor
    yaml_bin = gen.generate_ha_yaml("binary_sensor", "Garage Contact", "31", device_class="garage_door", who="1")
    assert "binary_sensor:" in yaml_bin
    assert "binary_sensors:" in yaml_bin
    assert "class: garage_door" in yaml_bin
    assert 'who: "1"' in yaml_bin

    # Custom
    yaml_custom = gen.generate_ha_yaml("custom_platform", "Custom Device", "99", extra_attr="abc")
    assert "Custom entity for platform 'custom_platform'" in yaml_custom

    # Slugify edge case
    assert gen._slugify("---!@#") == "entity"


def test_generate_sound_source_selection():
    """The routing frame uses the environment digit, not the amplifier digit."""
    generator = FrameGenerator()

    assert generator.generate_sound_source_selection("23", 2) == [
        "*16*3*102##",
        "*16*3*122##",
    ]
    # Amplifier 3 versus amplifier 1 in the same room: identical routing
    assert generator.generate_sound_source_selection("21", 2)[1] == "*16*3*122##"
    # A different room
    assert generator.generate_sound_source_selection("11", 2)[1] == "*16*3*112##"
    # A bare environment digit is accepted
    assert generator.generate_sound_source_selection("8", 1)[1] == "*16*3*181##"
    # Base band swaps the WHAT on both frames
    assert generator.generate_sound_source_selection("23", 2, base_band=True) == [
        "*16*0*102##",
        "*16*0*122##",
    ]


def test_generate_sound_source_selection_rejects_bad_input():
    """A bad source or address fails loudly rather than emitting a wrong frame."""
    generator = FrameGenerator()

    with pytest.raises(ValueError):
        generator.generate_sound_source_selection("23", 0)
    with pytest.raises(ValueError):
        generator.generate_sound_source_selection("23", 10)
    with pytest.raises(ValueError):
        generator.generate_sound_source_selection("kitchen", 2)
