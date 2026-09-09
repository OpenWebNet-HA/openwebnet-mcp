"""OpenWebNet frame syntax parser and semantic validator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from openwebnet_mcp.who_catalog import WhoCatalog


# Compiled regular expressions for OpenWebNet grammar
_RE_ACK = re.compile(r"^\*#\*1##$")
_RE_NACK = re.compile(r"^\*#\*0##$")
_RE_COMMAND_SESSION = re.compile(r"^\*99\*0##$")
_RE_EVENT_SESSION = re.compile(r"^\*99\*1##$")
_RE_NONCE = re.compile(r"^\*#(?P<nonce>\d{5,})##$")
_RE_SHA = re.compile(r"^\*98\*(?P<sha>\d+)##$")

_RE_STATUS_EVENT = re.compile(
    r"^\*(?P<who>\d+)\*(?P<what>\d+)(?P<what_param>(?:#\d+)*)\*(?P<where>\*|#?\d+)(?P<where_param>(?:#\d+)*)##$"
)
_RE_COMMAND_TRANSLATION = re.compile(
    r"^\*(?P<who>\d+)\*1000#(?P<what>\d+)(?P<what_param>(?:#\d+)*)\*(?P<where>\*|#?\d+)(?P<where_param>(?:#\d+)*)##$"
)
_RE_STATUS_REQUEST = re.compile(
    r"^\*#(?P<who>\d+)(?:\*(?P<where>#?\d+)(?P<where_param>(?:#\d+)*))?##$"
)
_RE_DIMENSION_REQUEST = re.compile(
    r"^\*#(?P<who>\d+)\*(?P<where>#?\d+)?(?P<where_param>(?:#\d+)*)?\*(?P<dimension>\d+)##$"
)
_RE_DIMENSION_WRITING = re.compile(
    r"^\*#(?P<who>\d+)\*(?P<where>#?\d+)?(?P<where_param>(?:#\d+)*)?\*#(?P<dimension>\d+)(?P<dimension_param>(?:#\d+)*)?(?P<dimension_value>(?:\*\d*)+)##$"
)
_RE_DIMENSION_REPLY = re.compile(
    r"^\*#(?P<who>\d+)\*(?P<where>#?\d+)?(?P<where_param>(?:#\d+)*)?\*(?P<dimension>\d+)(?P<dimension_param>(?:#\d+)*)?(?P<dimension_value>(?:\*\d*)+)##$"
)


@dataclass
class ParsedFrame:
    """Structured representation of a parsed OpenWebNet frame."""

    raw_frame: str
    is_valid: bool = False
    frame_type: str = "UNKNOWN"
    who: int | None = None
    what: int | None = None
    what_params: list[str] = field(default_factory=list)
    where: str | None = None
    where_params: list[str] = field(default_factory=list)
    dimension: int | None = None
    dimension_params: list[str] = field(default_factory=list)
    dimension_values: list[str] = field(default_factory=list)
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_frame": self.raw_frame,
            "is_valid": self.is_valid,
            "frame_type": self.frame_type,
            "who": self.who,
            "what": self.what,
            "what_params": self.what_params,
            "where": self.where,
            "where_params": self.where_params,
            "dimension": self.dimension,
            "dimension_params": self.dimension_params,
            "dimension_values": self.dimension_values,
            "explanation": self.explanation,
            "warnings": self.warnings,
        }


class FrameParser:
    """Parses and semantically validates OpenWebNet frames."""

    def __init__(self, catalog: WhoCatalog | None = None) -> None:
        self.catalog = catalog or WhoCatalog()

    def parse(self, frame_str: str) -> ParsedFrame:
        """Parse raw frame string and annotate with semantic explanation."""
        f = frame_str.strip()
        result = ParsedFrame(raw_frame=f)

        if not f:
            result.warnings.append("Empty frame string")
            result.explanation = "Empty frame string"
            return result

        if not (f.startswith("*") and f.endswith("##")):
            result.warnings.append("Frame must begin with '*' and end with '##'")
            result.explanation = "Malformed frame delimiters"
            return result

        # Session & handshake frames
        if _RE_ACK.match(f):
            result.is_valid = True
            result.frame_type = "ACK"
            result.explanation = "Acknowledge (*#*1##): Command accepted by gateway"
            return result

        if _RE_NACK.match(f):
            result.is_valid = True
            result.frame_type = "NACK"
            result.explanation = "Negative Acknowledge (*#*0##): Command rejected, invalid address, or bus busy"
            return result

        if _RE_COMMAND_SESSION.match(f):
            result.is_valid = True
            result.frame_type = "SESSION"
            result.explanation = "Command Session Handshake (*99*0##): Client initiates control connection"
            return result

        if _RE_EVENT_SESSION.match(f):
            result.is_valid = True
            result.frame_type = "SESSION"
            result.explanation = "Event Session Handshake (*99*1##): Client initiates bus monitor event listener"
            return result

        m_nonce = _RE_NONCE.match(f)
        if m_nonce:
            result.is_valid = True
            result.frame_type = "AUTH_NONCE"
            nonce_val = m_nonce.group("nonce")
            result.explanation = f"Authentication Nonce Challenge: gateway requested HMAC hash for nonce {nonce_val}"
            return result

        m_sha = _RE_SHA.match(f)
        if m_sha:
            result.is_valid = True
            result.frame_type = "AUTH_RESPONSE"
            result.explanation = "Authentication SHA Response: client submitted password digest"
            return result

        # Command translation
        m_trans = _RE_COMMAND_TRANSLATION.match(f)
        if m_trans:
            result.is_valid = True
            result.frame_type = "COMMAND_TRANSLATION"
            result.who = int(m_trans.group("who"))
            result.what = int(m_trans.group("what"))
            result.what_params = [p for p in m_trans.group("what_param").split("#") if p]
            result.where = m_trans.group("where")
            result.where_params = [p for p in m_trans.group("where_param").split("#") if p]
            self._enrich(result)
            return result

        # Dimension writing
        m_dim_w = _RE_DIMENSION_WRITING.match(f)
        if m_dim_w:
            result.is_valid = True
            result.frame_type = "DIMENSION_WRITING"
            result.who = int(m_dim_w.group("who"))
            result.where = m_dim_w.group("where") or "0"
            result.where_params = [p for p in (m_dim_w.group("where_param") or "").split("#") if p]
            result.dimension = int(m_dim_w.group("dimension"))
            result.dimension_params = [p for p in (m_dim_w.group("dimension_param") or "").split("#") if p]
            vals = m_dim_w.group("dimension_value").split("*")
            result.dimension_values = [v for v in vals if v]
            self._enrich(result)
            return result

        # Dimension reply
        m_dim_r = _RE_DIMENSION_REPLY.match(f)
        if m_dim_r:
            result.is_valid = True
            result.frame_type = "DIMENSION_REPLY"
            result.who = int(m_dim_r.group("who"))
            result.where = m_dim_r.group("where") or "0"
            result.where_params = [p for p in (m_dim_r.group("where_param") or "").split("#") if p]
            result.dimension = int(m_dim_r.group("dimension"))
            result.dimension_params = [p for p in (m_dim_r.group("dimension_param") or "").split("#") if p]
            vals = m_dim_r.group("dimension_value").split("*")
            result.dimension_values = [v for v in vals if v]
            self._enrich(result)
            return result

        # Dimension request
        m_dim_req = _RE_DIMENSION_REQUEST.match(f)
        if m_dim_req:
            result.is_valid = True
            result.frame_type = "DIMENSION_REQUEST"
            result.who = int(m_dim_req.group("who"))
            result.where = m_dim_req.group("where") or "0"
            result.where_params = [p for p in (m_dim_req.group("where_param") or "").split("#") if p]
            result.dimension = int(m_dim_req.group("dimension"))
            self._enrich(result)
            return result

        # Status request
        m_status_req = _RE_STATUS_REQUEST.match(f)
        if m_status_req:
            result.is_valid = True
            result.frame_type = "STATUS_REQUEST"
            result.who = int(m_status_req.group("who"))
            result.where = m_status_req.group("where")
            result.where_params = [p for p in (m_status_req.group("where_param") or "").split("#") if p]
            self._enrich(result)
            return result

        # Status / Command event
        m_status = _RE_STATUS_EVENT.match(f)
        if m_status:
            result.is_valid = True
            result.frame_type = "STATUS_EVENT"
            result.who = int(m_status.group("who"))
            result.what = int(m_status.group("what"))
            result.what_params = [p for p in m_status.group("what_param").split("#") if p]
            result.where = m_status.group("where")
            result.where_params = [p for p in m_status.group("where_param").split("#") if p]
            self._enrich(result)
            return result

        result.is_valid = False
        result.frame_type = "SYNTAX_ERROR"
        result.warnings.append("Frame does not match any valid OpenWebNet message grammar pattern.")
        result.explanation = "Unrecognized OpenWebNet syntax"
        return result

    def _enrich(self, parsed: ParsedFrame) -> None:
        """Enrich parsed frame with subsystem details from the WHO catalog."""
        if parsed.who is None:
            return

        family = self.catalog.get_family(parsed.who)
        if not family:
            parsed.warnings.append(f"WHO={parsed.who} is not documented in the master OpenWebNet catalog.")
            parsed.explanation = f"Frame for unknown subsystem WHO={parsed.who} on WHERE={parsed.where}"
            return

        subsystem = family.get("name", f"WHO {parsed.who}")
        where_desc = self._describe_where(parsed.where, parsed.where_params, who=parsed.who)

        if parsed.frame_type == "STATUS_REQUEST":
            parsed.explanation = f"Query status of {subsystem} at {where_desc}"
            return

        if parsed.frame_type in ("DIMENSION_REQUEST", "DIMENSION_WRITING", "DIMENSION_REPLY"):
            dims = family.get("dimensions", {})
            dim_meta = dims.get(str(parsed.dimension), {})
            dim_name = dim_meta.get("name", f"Dimension {parsed.dimension}")

            if str(parsed.dimension) not in dims and parsed.dimension is not None:
                parsed.warnings.append(f"Dimension {parsed.dimension} is not officially documented for WHO={parsed.who}.")

            if parsed.frame_type == "DIMENSION_REQUEST":
                parsed.explanation = f"Request {dim_name} from {subsystem} at {where_desc}"
            else:
                vals = ", ".join(parsed.dimension_values)
                semantic = self._decode_dimension_values(parsed.who, parsed.dimension, parsed.dimension_values)
                semantic_suffix = f" ({semantic})" if semantic else ""
                if parsed.frame_type == "DIMENSION_WRITING":
                    parsed.explanation = f"Write values [{vals}]{semantic_suffix} to {dim_name} for {subsystem} at {where_desc}"
                else:
                    parsed.explanation = f"{subsystem} reports {dim_name} = [{vals}]{semantic_suffix} for {where_desc}"
            return

        if parsed.frame_type in ("STATUS_EVENT", "COMMAND_TRANSLATION"):
            what_str = str(parsed.what)
            if parsed.what_params:
                what_str += "#" + "#".join(parsed.what_params)

            whats = family.get("what_commands", {})
            what_desc = whats.get(what_str) or whats.get(str(parsed.what))

            # Handle transition speed specifically for WHO 1
            if parsed.who == 1 and parsed.what == 1 and parsed.what_params:
                what_desc = f"Turn ON with transition speed {parsed.what_params[0]}"

            # Handle CEN+ button parameter in WHAT (WHO 25: *25*21#1*12##)
            if parsed.who == 25 and parsed.what_params:
                btn = parsed.what_params[0]
                base_desc = whats.get(str(parsed.what), f"Event {parsed.what}")
                what_desc = f"{base_desc} on pushbutton {btn}"

            if not what_desc and parsed.what is not None:
                parsed.warnings.append(f"WHAT={what_str} is not standard for WHO={parsed.who}.")
                what_desc = f"Action {what_str}"

            prefix = "[Translation] " if parsed.frame_type == "COMMAND_TRANSLATION" else ""
            parsed.explanation = f"{prefix}{subsystem}: {what_desc} at {where_desc}"

    def _decode_dimension_values(self, who: int, dimension: int | None, values: list[str]) -> str:
        """Provide human-readable semantic interpretation of raw dimension value lists."""
        if not values or dimension is None:
            return ""

        # WHO 4: Climate / Thermoregulation
        if who == 4:
            if dimension == 0 and values:
                v = values[0]
                if v.isdigit() and len(v) >= 2:
                    return f"{int(v)/10.0:.1f}°C"
            elif dimension == 14 and values:
                t_str = values[0]
                m_str = values[1] if len(values) > 1 else None
                modes = {"1": "Heating", "2": "Cooling", "3": "Generic"}
                m_desc = modes.get(m_str, f"Mode {m_str}") if m_str else ""
                if t_str.isdigit() and len(t_str) >= 2:
                    t_val = int(t_str) / 10.0
                    return f"Target {t_val:.1f}°C" + (f" in {m_desc} mode" if m_desc else "")
            elif dimension == 11 and values:
                spd = values[0]
                spd_desc = "Auto" if spd == "0" else f"Speed {spd}"
                return f"Fancoil {spd_desc}"
            elif dimension == 22 and values:
                return f"Offset {values[0]}"

        # WHO 18: Energy management
        elif who == 18:
            if dimension == 1 and values:
                return f"{values[0]} W"
            elif dimension == 52 and values:
                return f"{values[0]} Wh"

        # WHO 1: Lighting
        elif who == 1:
            if dimension == 1 and values:
                level = values[0]
                speed = values[1] if len(values) > 1 else None
                return f"{level}% brightness" + (f" with transition speed {speed}" if speed else "")
            elif dimension == 2 and len(values) >= 3:
                return f"RGB({values[0]}, {values[1]}, {values[2]})"
            elif dimension == 3 and values:
                return f"{values[0]} K"

        # WHO 2: Automation / Covers
        elif who == 2:
            if dimension == 10 and values:
                return f"{values[0]}% open"
            elif dimension == 11 and values:
                return f"Slat tilt {values[0]}%"

        # WHO 16: Sound System / Audio
        elif who == 16:
            if dimension == 1 and values:
                val = values[0]
                if val.isdigit():
                    pct = int(val) * 100 // 30
                    return f"Volume {val}/30 ({pct}%)"
                return f"Volume {val}"
            elif dimension == 2 and values:
                val = values[0]
                if val.isdigit() and int(val) > 1000:
                    return f"Tuner {int(val)/1000.0:.1f} MHz ({val} kHz)"
                return f"Tuner {val} kHz"
            elif dimension == 3 and len(values) >= 2:
                return f"Equalizer (Bass {values[0]}, Treble {values[1]})"

        return ""

    def _describe_where(self, where: str | None, where_params: list[str], who: int | None = None) -> str:
        """Provide a readable description for the WHERE address."""
        if where is None:
            return "system-wide"
        if where == "0":
            return "General (all devices)"

        # Special decoding for CEN (WHO 15) pushbuttons: WHERE#B
        if who == 15 and where_params:
            btn = where_params[0]
            desc = f"pushbutton {btn} on CEN interface '{where}'"
            extra = where_params[1:]
            if "4" in extra:
                idx = extra.index("4")
                if idx + 1 < len(extra):
                    bus_id = extra[idx + 1]
                    desc += f" routed to private SCS bus {bus_id}"
            elif extra:
                desc += f" with parameters ({', '.join(extra)})"
            return desc

        # Special decoding for WHO 4 manual setpoints: WHERE#TEMP
        if who == 4 and where_params and where_params[0].isdigit() and len(where_params[0]) >= 2:
            t_val = int(where_params[0]) / 10.0
            desc = f"Zone {where} with target setpoint {t_val:.1f}°C"
            extra = where_params[1:]
            if extra:
                desc += f" (duration {extra[0]} min)"
            return desc

        desc = f"address '{where}'"
        if where_params:
            if "4" in where_params:
                idx = where_params.index("4")
                if idx + 1 < len(where_params):
                    bus_id = where_params[idx + 1]
                    desc += f" routed to private SCS bus {bus_id}"
            else:
                desc += f" with parameters ({', '.join(where_params)})"
        return desc
