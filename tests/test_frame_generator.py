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
    assert gen.generate_cover("21", "position", position_pct=60) == "*#2*21*#10*60##"

    with pytest.raises(ValueError):
        gen.generate_cover("21", "invalid_action")


def test_generate_climate():
    gen = FrameGenerator()
    assert gen.generate_climate(zone=1, target_temp=21.5, mode="heat") == "*#4*1*#14*0215*1##"
    assert gen.generate_climate(zone=1, target_temp=24.0, mode="cool") == "*#4*1*#14*0240*2##"
    assert gen.generate_climate(zone=1, mode="off") == "*4*100*1##"
    assert gen.generate_climate(zone=1, mode="antifreeze") == "*4*110*1##"
    assert gen.generate_climate(zone=2, mode="heat") == "*4*101*2##"


def test_generate_cen():
    gen = FrameGenerator()
    # CEN (WHO=15)
    assert gen.generate_cen("11", button=2, press_type="short") == "*15*1*11#2##"
    assert gen.generate_cen("11", button=2, press_type="start_long") == "*15*0*11#2##"
    assert gen.generate_cen("11", button=2, press_type="release") == "*15*2*11#2##"

    # CEN+ (WHO=25)
    assert gen.generate_cen("12", button=1, press_type="short", is_cen_plus=True) == "*25*21#1*12##"
    assert gen.generate_cen("12", button=1, press_type="start_long", is_cen_plus=True) == "*25*22#1*12##"
    assert gen.generate_cen("12", button=1, press_type="release", is_cen_plus=True) == "*25*24#1*12##"


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
