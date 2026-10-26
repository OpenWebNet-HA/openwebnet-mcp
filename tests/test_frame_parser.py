"""Tests for FrameParser and frame syntax validator."""

import pytest
from openwebnet_mcp.frame_parser import FrameParser


def test_parse_ack_and_nack():
    parser = FrameParser()

    p_ack = parser.parse("*#*1##")
    assert p_ack.is_valid is True
    assert p_ack.frame_type == "ACK"
    assert "Acknowledge" in p_ack.explanation

    p_nack = parser.parse("*#*0##")
    assert p_nack.is_valid is True
    assert p_nack.frame_type == "NACK"
    assert "Negative Acknowledge" in p_nack.explanation


def test_parse_sessions_and_auth():
    parser = FrameParser()

    p_cmd = parser.parse("*99*0##")
    assert p_cmd.is_valid is True
    assert p_cmd.frame_type == "SESSION"
    assert "Command Session" in p_cmd.explanation

    p_evt = parser.parse("*99*1##")
    assert p_evt.is_valid is True
    assert p_evt.frame_type == "SESSION"
    assert "Event Session" in p_evt.explanation

    p_nonce = parser.parse("*#123456789##")
    assert p_nonce.is_valid is True
    assert p_nonce.frame_type == "AUTH_NONCE"

    p_sha = parser.parse("*98*2##")
    assert p_sha.is_valid is True
    assert p_sha.frame_type == "AUTH_RESPONSE"


def test_parse_status_event():
    parser = FrameParser()

    # Lighting ON
    p1 = parser.parse("*1*1*12##")
    assert p1.is_valid is True
    assert p1.frame_type == "STATUS_EVENT"
    assert p1.who == 1
    assert p1.what == 1
    assert p1.where == "12"
    assert "Turn ON" in p1.explanation

    # Lighting with speed: *1*1#5*12##
    p2 = parser.parse("*1*1#5*12##")
    assert p2.is_valid is True
    assert p2.what_params == ["5"]
    assert "Turn ON with transition speed" in p2.explanation

    # Bus routed: *1*1*12#4#1##
    p3 = parser.parse("*1*1*12#4#1##")
    assert p3.is_valid is True
    assert "routed to private SCS bus 1" in p3.explanation


def test_parse_command_translation():
    parser = FrameParser()
    p = parser.parse("*1*1000#1*12##")
    assert p.is_valid is True
    assert p.frame_type == "COMMAND_TRANSLATION"
    assert p.who == 1
    assert p.what == 1
    assert "[Translation]" in p.explanation


def test_parse_status_request():
    parser = FrameParser()

    p1 = parser.parse("*#1*12##")
    assert p1.is_valid is True
    assert p1.frame_type == "STATUS_REQUEST"
    assert p1.who == 1
    assert p1.where == "12"
    assert "Query status of Lighting" in p1.explanation

    # Subsystem status request without where
    p2 = parser.parse("*#5*0##")
    assert p2.is_valid is True
    assert p2.who == 5


def test_parse_dimensions():
    parser = FrameParser()

    # Dimension request: *#4*1*0## (Query temperature)
    p_req = parser.parse("*#4*1*0##")
    assert p_req.is_valid is True
    assert p_req.frame_type == "DIMENSION_REQUEST"
    assert p_req.dimension == 0
    assert "Measured Temperature" in p_req.explanation

    # Dimension reply: *#4*1*0*0215## (21.5°C)
    p_rep = parser.parse("*#4*1*0*0215##")
    assert p_rep.is_valid is True
    assert p_rep.frame_type == "DIMENSION_REPLY"
    assert p_rep.dimension_values == ["0215"]
    assert "reports Measured Temperature = [0215]" in p_rep.explanation

    # Dimension writing: *#1*12*#1*50*5##
    p_write = parser.parse("*#1*12*#1*50*5##")
    assert p_write.is_valid is True
    assert p_write.frame_type == "DIMENSION_WRITING"
    assert p_write.dimension == 1
    assert p_write.dimension_values == ["50", "5"]


def test_parse_cen_frames():
    parser = FrameParser()

    # CEN: button in WHAT, phase as WHAT parameter, source in WHERE
    p_cen = parser.parse("*15*02*22##")
    assert p_cen.is_valid is True
    assert p_cen.who == 15
    assert p_cen.what == 2
    assert p_cen.where == "22"
    assert "Pressure on pushbutton 02 at address '22'" in p_cen.explanation
    assert p_cen.warnings == []

    for frame, phase in [
        ("*15*02#1*22##", "Release after short pressure"),
        ("*15*02#2*22##", "Release after extended pressure"),
        ("*15*02#3*22##", "Extended pressure"),
    ]:
        parsed = parser.parse(frame)
        assert f"{phase}" in parsed.explanation and "pushbutton 02" in parsed.explanation, frame
        assert parsed.warnings == [], frame

    # Local-bus source keeps the button in WHAT
    p_local = parser.parse("*15*06*36#4#01##")
    assert "Pressure on pushbutton 06" in p_local.explanation
    assert "private SCS bus 01" in p_local.explanation
    assert p_local.warnings == []

    # The old "button in WHERE" form is button 01 from an undocumented source, not button 2
    p_old = parser.parse("*15*1*11#2##")
    assert "Pressure on pushbutton 01" in p_old.explanation
    assert "pushbutton 2" not in p_old.explanation
    assert any("not a documented CEN address form" in w for w in p_old.warnings)

    # Out-of-range button and unknown phase are flagged
    assert any("outside 00..31" in w for w in parser.parse("*15*32*22##").warnings)
    assert any("phase #5" in w for w in parser.parse("*15*02#5*22##").warnings)

    # CEN+: interaction in WHAT, pushbutton as its parameter, WHERE = "2" + Object
    p_cenp = parser.parse("*25*21#2*21##")
    assert p_cenp.is_valid is True
    assert p_cenp.who == 25
    assert p_cenp.what == 21
    assert p_cenp.what_params == ["2"]
    assert "Short pressure (complete; no release frame follows) on pushbutton 2 at CEN+ Object 1" in p_cenp.explanation
    assert p_cenp.warnings == []

    for frame, phase in [
        ("*25*22#1*21##", "Start of extended pressure on pushbutton 1"),
        ("*25*23#1*21##", "Extended pressure (repeats while held) on pushbutton 1"),
        ("*25*24#1*21##", "Release after extended pressure on pushbutton 1"),
        ("*25*26#1*21##", "Rotary selector, fast clockwise on pushbutton 1"),
        ("*25*28#0*20##", "Rotary selector, fast counter-clockwise on pushbutton 0 at CEN+ Object 0"),
    ]:
        parsed = parser.parse(frame)
        assert phase in parsed.explanation, frame
        assert parsed.warnings == [], frame

    assert "CEN+ Object 101" in parser.parse("*25*21#1*2101##").explanation
    assert "CEN+ Object 2047" in parser.parse("*25*21#1*22047##").explanation

    # CEN+ misuse is flagged: no pushbutton, out-of-range pushbutton, non-Object WHERE
    assert any("no pushbutton" in w for w in parser.parse("*25*21*21##").warnings)
    assert any("outside 0..31" in w for w in parser.parse("*25*21#32*21##").warnings)
    assert any("not a CEN+ virtual Object" in w for w in parser.parse("*25*21#1*12##").warnings)
    assert any("not a CEN+ virtual Object" in w for w in parser.parse("*25*21#1*22048##").warnings)

    # Dry contact / IR shares WHO 25: the parameter is event (1) or state reply (0), not a button
    p_dry = parser.parse("*25*31#1*15##")
    assert "Dry contact ON / IR detection (event) at interface '15'" in p_dry.explanation
    assert "pushbutton" not in p_dry.explanation
    assert p_dry.warnings == []
    assert "Dry contact OFF / IR not detected (state reply)" in parser.parse("*25*32#0*15##").explanation
    assert any("expected #1 (event) or #0" in w for w in parser.parse("*25*31#2*15##").warnings)
    assert any("dry-contact / IR address" in w for w in parser.parse("*25*31#1*202##").warnings)
    assert any("not standard for WHO=25" in w for w in parser.parse("*25*29#1*21##").warnings)

    # Rich dimension decoding: WHO 4 setpoint
    p_target = parser.parse("*#4*1*#14*0215*1##")
    assert p_target.is_valid is True
    assert "Target 21.5" in p_target.explanation
    assert "Heating mode" in p_target.explanation

    # Rich dimension decoding: WHO 18 power
    p_power = parser.parse("*#18*1*1*1450##")
    assert p_power.is_valid is True
    assert "1450 W" in p_power.explanation

    # Rich dimension decoding: WHO 2 cover position
    p_cov = parser.parse("*#2*21*10*60##")
    assert p_cov.is_valid is True
    assert "60% open" in p_cov.explanation

    # WHO 18 totalizer
    p_wh = parser.parse("*#18*1*52*12345##")
    assert "12345 Wh" in p_wh.explanation

    # WHO 1 RGB and Kelvin
    p_rgb = parser.parse("*#1*12*#2*255*128*0##")
    assert "RGB(255, 128, 0)" in p_rgb.explanation

    p_k = parser.parse("*#1*12*#3*3000##")
    assert "3000 K" in p_k.explanation

    # WHO 2 Slat angle
    p_slat = parser.parse("*#2*21*#11*45##")
    assert "Slat tilt 45%" in p_slat.explanation

    # WHO 4 Fancoil and offset
    p_fan = parser.parse("*#4*1*11*2##")
    assert "Fancoil Speed 2" in p_fan.explanation
    assert len(p_fan.warnings) == 0

    # WHO 4 invalid fan speed code 4
    p_fan_invalid = parser.parse("*#4*1*#11*4##")
    assert any("Invalid fan speed code '4'" in w for w in p_fan_invalid.warnings)

    # WHO 4 fan speed 15 write warning (read-only in spec)
    p_fan_off_write = parser.parse("*#4*1*#11*15##")
    assert any("Read-Only" in w for w in p_fan_off_write.warnings)

    # WHO 4 fan speed 15 read response (allowed status)
    p_fan_off_read = parser.parse("*#4*1*11*15##")
    assert "Fancoil OFF" in p_fan_off_read.explanation
    assert len(p_fan_off_read.warnings) == 0

    p_off = parser.parse("*#4*1*22*1##")
    assert "Offset 1" in p_off.explanation

    # WHO 16 Sound system: volume is 0-31, and the tuner lives on DIMENSION 6
    p_vol = parser.parse("*#16*1*1*15##")
    assert "Volume 15/31 (48%)" in p_vol.explanation

    p_tune = parser.parse("*#16*101*6*0*102500##")
    assert "Tuner 102.50 MHz" in p_tune.explanation

    p_station = parser.parse("*#16*101*7*0*3##")
    assert "Stored station/track 3" in p_station.explanation

    p_rds = parser.parse("*#16*101*8*32*82*97*100*105*111*32*49##")
    assert "RDS text" in p_rds.explanation
    assert "Radio 1" in p_rds.explanation

    # WHO 4 Manual heating setpoint command (*4*301*Z#T##) and with timeout
    p_sp = parser.parse("*4*301*2#0215##")
    assert p_sp.is_valid is True
    assert "Zone 2 with target setpoint 21.5" in p_sp.explanation

    p_sp_timeout = parser.parse("*4*311*2#0215#60##")
    assert "duration 60 min" in p_sp_timeout.explanation

    # CEN with non-bus extra WHERE parameters
    p_cen_extra = parser.parse("*15*1*11#2#8##")
    assert "parameters (2, 8)" in p_cen_extra.explanation




def test_parse_errors_and_edge_cases():
    parser = FrameParser()

    # Empty frame
    p_empty = parser.parse("")
    assert p_empty.is_valid is False
    assert "Empty frame" in p_empty.warnings[0]

    # Malformed delimiters
    p_delim = parser.parse("1*1*12")
    assert p_delim.is_valid is False
    assert "Frame must begin with" in p_delim.warnings[0]

    # Syntax error
    p_err = parser.parse("*abc*def##")
    assert p_err.is_valid is False
    assert p_err.frame_type == "SYNTAX_ERROR"

    # Unknown WHO
    p_unknown = parser.parse("*999*1*12##")
    assert p_unknown.is_valid is True
    assert any("not documented" in w for w in p_unknown.warnings)

    # Unknown WHAT
    p_what = parser.parse("*1*999*12##")
    assert any("not standard" in w for w in p_what.warnings)

    # Unknown Dimension
    p_dim = parser.parse("*#1*12*#999*1##")
    assert any("not officially documented" in w for w in p_dim.warnings)

    # WHERE with arbitrary params
    p_where_params = parser.parse("*1*1*12#1#2##")
    assert "with parameters" in p_where_params.explanation

    # Status request without WHERE
    p_req_nowhere = parser.parse("*#1##")
    assert "system-wide" in p_req_nowhere.explanation

    # To dict serialization
    d = p_empty.to_dict()
    assert isinstance(d, dict)
    assert d["raw_frame"] == ""


def test_parse_who_14():
    parser = FrameParser()

    # Lock command
    p_lock = parser.parse("*14*0*12##")
    assert p_lock.is_valid is True
    assert p_lock.who == 14
    assert p_lock.what == 0
    assert p_lock.where == "12"
    assert "Lock" in p_lock.explanation

    # Unlock command
    p_unlock = parser.parse("*14*1*12##")
    assert p_unlock.is_valid is True
    assert p_unlock.who == 14
    assert p_unlock.what == 1
    assert p_unlock.where == "12"
    assert "Unlock" in p_unlock.explanation

    # Status request
    p_status = parser.parse("*#14*12##")
    assert p_status.is_valid is True
    assert p_status.who == 14
    assert p_status.frame_type == "STATUS_REQUEST"


def test_who16_sound_addressing():
    """WHO 16 addresses: amplifier EA, source 10S, and the 1ES routing form.

    The routing form is not in WHO_16.pdf. It is corroborated by captures on
    two F441M installations and by the WHO 22 frames one of them emits
    alongside, where the environment and the source sit in separate fields.
    """
    parser = FrameParser()

    amp = parser.parse("*16*3*23##")
    assert "Amplifier 3 in environment 2" in amp.explanation
    assert amp.warnings == []

    source = parser.parse("*16*3*102##")
    assert "Source device 2" in source.explanation

    routing = parser.parse("*16*3*122##")
    assert "environment 2 listening to source 2" in routing.explanation

    other_env = parser.parse("*16*3*112##")
    assert "environment 1 listening to source 2" in other_env.explanation

    # 10S is a source device, never routing to "environment 0"
    assert "environment" not in parser.parse("*16*3*101##").explanation


def test_who16_stereo_channel_and_ranged_whats():
    """Hardware uses the stereo-channel WHATs and magnitude-carrying ranges."""
    parser = FrameParser()

    for frame in ("*16*3*23##", "*16*13*23##", "*16*23*100##", "*16*33*23##", "*16*53*23##"):
        parsed = parser.parse(frame)
        assert parsed.warnings == [], f"{frame} should be recognised: {parsed.warnings}"

    vol_up = parser.parse("*16*1005*23##")
    assert "Increase volume" in vol_up.explanation
    assert vol_up.warnings == []

    station = parser.parse("*16*6001*101##")
    assert "station or track" in station.explanation
    assert station.warnings == []

    # Outside every declared range, a warning is still the right answer
    assert parser.parse("*16*7777*23##").warnings


def test_who22_structured_addresses():
    """WHO 22 WHERE is a tagged class, not a number with punctuation."""
    parser = FrameParser()

    speaker = parser.parse("*22*1#4#1*3#1#1##")
    assert "area 1, point 1" in speaker.explanation
    assert speaker.warnings == []

    volume = parser.parse("*#22*3#1#1*1*17##")
    assert "Volume" in volume.explanation
    assert "area 1, point 1" in volume.explanation

    source_on = parser.parse("*22*2#4#1*5#2#2##")
    assert "Source turned on" in source_on.explanation

    follow_me = parser.parse("*22*34#4#1*3#1#1##")
    assert "Follow Me" in follow_me.explanation
    assert follow_me.warnings == []

    # Local speaker compound address: 5#3#area#point
    local_speaker = parser.parse("*#22*5#3#0#0*12*0*255##")
    assert "Local speaker: area 0, point 0" in local_speaker.explanation
    assert "Device state" in local_speaker.explanation

    # Volume dimension writing: *#22*3#1#1*#1*20##
    vol_write = parser.parse("*#22*3#1#1*#1*20##")
    assert "Volume" in vol_write.explanation
    assert vol_write.frame_type == "DIMENSION_WRITING"
    assert "area 1, point 1" in vol_write.explanation

    # Source matrix active areas query: *#22*2#1*13##
    src_matrix = parser.parse("*#22*2#1*13##")
    assert "Source matrix active areas" in src_matrix.explanation
    assert "Source 1" in src_matrix.explanation

    # Next track / station on source 1: *22*9*2#1##
    next_trk = parser.parse("*22*9*2#1##")
    assert "Next station" in next_trk.explanation
    assert "Source 1" in next_trk.explanation

    # Equalizer preset write: *#22*3#1#1*#19*2##
    preset_write = parser.parse("*#22*3#1#1*#19*2##")
    assert "Preset" in preset_write.explanation
    assert preset_write.frame_type == "DIMENSION_WRITING"

    # Loudness on write: *#22*3#1#1*#20*1##
    loud_write = parser.parse("*#22*3#1#1*#20*1##")
    assert "Loudness" in loud_write.explanation
    assert loud_write.frame_type == "DIMENSION_WRITING"


def test_who16_source_selection_is_not_what_100():
    """WHAT 100-102 are source busy and RDS control, not source selection.

    An earlier catalog listed these as "Select Audio Source N", which would
    send an agent to a frame that means something else entirely.
    """
    parser = FrameParser()

    assert "busy" in parser.parse("*16*100*23##").explanation.lower()
    assert "RDS" in parser.parse("*16*101*23##").explanation
    assert "RDS" in parser.parse("*16*102*23##").explanation


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        # WHO_2.pdf Where Table: A = 00, 1-9 or 100 is an environment, #GR a group
        ("*2*0*1##", "STOP movement at Area 1: every automation actuator in that environment"),
        ("*2*2*00##", "at Area 00:"),
        ("*2*1*100##", "at Area 10 (WHERE 100):"),
        ("*2*1*#3##", "at Group 3: every automation actuator programmed into it"),
        ("*2*1*1#4#02##", "at Area 1: every automation actuator in that environment routed to private SCS bus 02"),
        ("*#2*1#4#02##", "Area 1: every automation actuator in that environment routed to private SCS bus 02"),
        ("*1*1*5##", "at Area 5: every light point in that environment"),
        ("*1*0*#12##", "at Group 12: every light point programmed into it"),
        # point-to-point and general are unchanged
        ("*2*0*11##", "at address '11'"),
        ("*2*1*11#4#02##", "at address '11' routed to private SCS bus 02"),
        ("*2*1*0##", "at General (all devices)"),
    ],
)
def test_who1_who2_area_and_group_where(frame, expected):
    parsed = FrameParser().parse(frame)
    assert parsed.is_valid is True
    assert expected in parsed.explanation, parsed.explanation


def test_who2_advanced_what_is_10_11_12():
    """WHO_2.pdf 2.3.1: StopAdvanced 10, UpAdvanced 11, DownAdvanced 12 (not 30-32)."""
    from openwebnet_mcp.who_catalog import WhoCatalog

    whats = WhoCatalog().get_family(2)["what_commands"]
    assert whats["10"].startswith("Advanced STOP")
    assert whats["11"].startswith("Advanced UP")
    assert whats["12"].startswith("Advanced DOWN")
    assert not {"30", "31", "32"} & set(whats)
    assert "Advanced UP" in FrameParser().parse("*2*11*21##").explanation



@pytest.mark.parametrize(
    "frame, expected",
    [
        ("*5*1*0##", "Burglar Alarm: Activation (central unit active"),
        ("*5*1*0##", "at Central unit"),
        ("*5*8*0##", "Burglar Alarm: Engage: system engaged, i.e. armed (report) at Central unit"),
        ("*5*9*0##", "Disengage"),
        ("*5*11*#1##", "Active zone: zone engaged (report, WHERE #N) at Zone 1"),
        ("*5*18*#8##", "at Zone 8"),
        ("*5*15*#3##", "Intrusion alarm (event) at Zone 3"),
        ("*5*15*12##", "at Zone 1 sensor 2"),
        ("*#5*#1##", "Query status of Burglar Alarm at Zone 1"),
    ],
)
def test_who5_alarm_frames(frame, expected):
    parsed = FrameParser().parse(frame)
    assert parsed.is_valid is True
    assert not parsed.warnings, parsed.warnings
    assert expected in parsed.explanation, parsed.explanation


@pytest.mark.parametrize(
    "frame, expected",
    [
        ("*6*0*4000##", "Turn camera ON"),
        ("*6*0*4000##", "Entrance panel 4000"),
        ("*6*9##", "Turn camera OFF (*6*9##, short form without WHERE) at system-wide"),
        ("*6*6*1##", "Incoming apartment or broadcast call"),
        ("*6*6*4100##", "Broadcast call sentinel (4100)"),
        ("*6*10*4000#2##", "Entrance panel 4000 on riser #2"),
        ("*6*12*4000##", "Staircase light ON"),
        ("*6*18*4000##", "Cycle camera"),
        ("*6*20*1##", "Incoming call chime"),
        ("*6*22*4000##", "Open lock confirmation with external unit in conversation"),
        ("*8*1#1#4*74##", "Initiate call: Entrance panel PE1 (Kind=1) [Audio/Video] at address '74'"),
        ("*8*1#6#2#11*16##", "Initiate call: Internal intercom (Kind=6) [Audio] from caller 11 at address '16'"),
        ("*8*1#14#2#11*4##", "Initiate call: Pager call (Kind=14) [Audio] from caller 11 at Broadcast (all stations, WHERE=4)"),
        ("*8*2#1#4*11##", "Answer call: Entrance panel PE1 (Kind=1) [Audio/Video] at address '11'"),
        ("*8*3#1#4*411##", "End call: Entrance panel PE1 (Kind=1) [Audio/Video] at station '11' (END_ALL_CALLS prefix 4)"),
        ("*8*3#1#3*11##", "Stop video reproduction (Entrance panel PE1 (Kind=1)) at address '11'"),
        ("*8*4#11*20##", "Auto-switch / camera turn ON from caller 11 at address '20'"),
        ("*8*6#11*20##", "Cycle external units / cameras from caller 11 at address '20'"),
        ("*8*9#1#4*73##", "Caller address notification: Entrance panel PE1 (Kind=1) [Audio/Video] at address '73'"),
        ("*8*37#1*11##", "Initialize VCT process (SCS mode) at address '11'"),
        ("*8*40#1#4*20##", "Rearm session: Entrance panel PE1 (Kind=1) [Audio/Video] at address '20'"),
        ("*8*77#5*11##", "Teleloop: Association (ID=5) at address '11'"),
        ("*8*79#1#4#5*11##", "Teleloop: Active session (Entrance panel PE1 (Kind=1) [Audio/Video], ID=5) at address '11'"),
        ("*8*9012#1*11#00#1##", "Guard Unit messaging: Begin message (ID=1)"),
        ("*#8*11#00#99*#9001*1*2##", "Guard Unit Message Parameter Block"),
        ("*#8*11#00#99*#9002*66*116*105*99*105*110*111##", "UTF-16 text 'Bticino'"),
        ("*8*1#1101#4#74*11##", "Initiate call: IP movable camera (Kind=1101) [Audio/Video] from caller 74 at address '11'"),
    ],
)
def test_who6_and_who8_frames(frame, expected):
    parsed = FrameParser().parse(frame)
    assert parsed.is_valid is True
    assert not parsed.warnings, f"{frame}: {parsed.warnings}"
    assert expected in parsed.explanation, parsed.explanation


def test_who4_addressing_dimensions_and_warnings():
    parser = FrameParser()

    # Valid Dimension 20 actuator queries (no warnings)
    for frame, expected in [
        ("*#4*#0*20##", "99-zone central unit (#0)"),
        ("*#4*#0#2*20##", "4-zone central unit #2"),
        ("*#4*0#0*20##", "All zones, all actuators (0#0)"),
        ("*#4*2#0*20##", "Zone 2, all actuators (2#0)"),
        ("*#4*2#1*20##", "Zone 2, actuator 1 (2#1)"),
        ("*#4*002*0##", "Zone 02, all probes"),
        ("*#4*102*0##", "Zone 02, slave probe 1"),
        ("*#4*2*19*0*1##", "Conditioning valve OFF, heating valve ON"),
        ("*#4*2*19*15*0##", "Conditioning valve Fan-coil OFF speed 2, heating valve OFF"),
        ("*#4*2*60*55##", "55% RH"),
        ("*#4*2#1*20*6##", "Actuator On Speed 1"),
        ("*#4*2#1*20*9##", "Actuator Fan-coil ON"),
        ("*4*301*1#0210##", "Zone 1 with target setpoint 21.0°C"),
        ("*4*301*1#50##", "Zone 1 with target setpoint 5.0°C"),
        ("*4*311*1#0215#60##", "Zone 1 with target setpoint 21.5°C (duration 60 min)"),
    ]:
        parsed = parser.parse(frame)
        assert parsed.is_valid is True
        assert not parsed.warnings, f"{frame}: {parsed.warnings}"
        assert expected in parsed.explanation, parsed.explanation

    # Dimensionless actuator status request (*#4*2#1##) warns about NACK + MH202 coso crash
    p_act_status = parser.parse("*#4*2#1##")
    assert p_act_status.is_valid is True
    assert any("crashes coso with SIGSEGV" in w and "Dimension 20" in w for w in p_act_status.warnings)

    # 4-zone central unit status request (*#4*#0#1##) is NOT an actuator address
    p_cu4 = parser.parse("*#4*#0#1##")
    assert p_cu4.is_valid is True
    assert not p_cu4.warnings

    # WHO=4 #4#INTERFACE status request warns about unrouted #4# AND MH202 coso crash on 01..09
    p_if_crash = parser.parse("*#4*2#4#01##")
    assert p_if_crash.is_valid is True
    assert "unrouted #4#01" in p_if_crash.explanation
    assert any("misparses 3-token *#4*2#4#01##" in w and "SIGSEGV" in w for w in p_if_crash.warnings)

    # WHO=4 #4#INTERFACE dimension request warns about unrouted local-bus truncation
    p_if_dim = parser.parse("*#4*2#4#01*20##")
    assert p_if_dim.is_valid is True
    assert "unrouted #4#01" in p_if_dim.explanation
    assert any("not implemented in gateway translators" in w for w in p_if_dim.warnings)

    p_if_act_dim = parser.parse("*#4*2#1#4#01*20##")
    assert p_if_act_dim.is_valid is True
    assert "Zone 2, actuator 1 with unrouted #4#01" in p_if_act_dim.explanation
    assert any("not implemented in gateway translators" in w for w in p_if_act_dim.warnings)

