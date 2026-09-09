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

    # CEN button press
    p_cen = parser.parse("*15*1*11#2##")
    assert p_cen.is_valid is True
    assert p_cen.who == 15
    assert p_cen.what == 1
    assert p_cen.where == "11"
    assert p_cen.where_params == ["2"]
    assert "pushbutton 2 on CEN interface '11'" in p_cen.explanation

    # CEN+ button press: *25*21#2*11##
    p_cenp = parser.parse("*25*21#2*11##")
    assert p_cenp.is_valid is True
    assert p_cenp.who == 25
    assert p_cenp.what == 21
    assert p_cenp.what_params == ["2"]
    assert "on pushbutton 2" in p_cenp.explanation

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

    p_off = parser.parse("*#4*1*22*1##")
    assert "Offset 1" in p_off.explanation

    # WHO 16 Sound system volume and tuner
    p_vol = parser.parse("*#16*1*1*15##")
    assert "Volume 15/30 (50%)" in p_vol.explanation

    p_tune = parser.parse("*#16*1*2*102500##")
    assert "Tuner 102.5 MHz" in p_tune.explanation

    # WHO 4 Manual heating setpoint command (*4*301*Z#T##)
    p_sp = parser.parse("*4*301*2#0215##")
    assert p_sp.is_valid is True
    assert "Zone 2 with target setpoint 21.5" in p_sp.explanation




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
