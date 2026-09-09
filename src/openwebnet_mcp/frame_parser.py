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
        where_desc = self._describe_where(parsed.where, parsed.where_params)

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
            elif parsed.frame_type == "DIMENSION_WRITING":
                vals = ", ".join(parsed.dimension_values)
                parsed.explanation = f"Write values [{vals}] to {dim_name} for {subsystem} at {where_desc}"
            else:
                vals = ", ".join(parsed.dimension_values)
                parsed.explanation = f"{subsystem} reports {dim_name} = [{vals}] for {where_desc}"
            return

        if parsed.frame_type in ("STATUS_EVENT", "COMMAND_TRANSLATION"):
            what_str = str(parsed.what)
            if parsed.what_params:
                what_str += "#" + "#".join(parsed.what_params)

            whats = family.get("what_commands", {})
            what_desc = whats.get(what_str) or whats.get(str(parsed.what))

            # Handle transition speed specifically
            if parsed.who == 1 and parsed.what == 1 and parsed.what_params:
                what_desc = f"Turn ON with transition speed {parsed.what_params[0]}"

            if not what_desc and parsed.what is not None:
                parsed.warnings.append(f"WHAT={what_str} is not standard for WHO={parsed.who}.")
                what_desc = f"Action {what_str}"

            prefix = "[Translation] " if parsed.frame_type == "COMMAND_TRANSLATION" else ""
            parsed.explanation = f"{prefix}{subsystem}: {what_desc} at {where_desc}"

    def _describe_where(self, where: str | None, where_params: list[str]) -> str:
        """Provide a readable description for the WHERE address."""
        if where is None:
            return "system-wide"
        if where == "0":
            return "General (all devices)"
        
        desc = f"address '{where}'"
        if where_params:
            if "4" in where_params:
                # Bus routing: where#4#bus
                idx = where_params.index("4")
                if idx + 1 < len(where_params):
                    bus_id = where_params[idx + 1]
                    desc += f" routed to private SCS bus {bus_id}"
            else:
                desc += f" with parameters ({', '.join(where_params)})"
        return desc
