"""Generators for OpenWebNet frames and Home Assistant configuration."""

from __future__ import annotations

from typing import Any

from openwebnet_mcp.frame_parser import FrameParser, ParsedFrame


class FrameGenerator:
    """Generates syntactically correct OpenWebNet frames and HA configuration."""

    def __init__(self, parser: FrameParser | None = None) -> None:
        self.parser = parser or FrameParser()

    def build_frame(
        self,
        who: int,
        command_type: str,
        where: str,
        what: int | str | None = None,
        dimension: int | None = None,
        values: list[str | int] | None = None,
    ) -> tuple[str, ParsedFrame]:
        """Construct an OpenWebNet frame string and return it with parse validation."""
        cmd_type = command_type.strip().lower()

        if cmd_type in ("status_event", "command", "event"):
            if what is None:
                raise ValueError("Parameter 'what' is required for command/status frames.")
            frame = f"*{who}*{what}*{where}##"

        elif cmd_type in ("status_request", "request"):
            frame = f"*#{who}*{where}##"

        elif cmd_type in ("dimension_request", "dim_req"):
            if dimension is None:
                raise ValueError("Parameter 'dimension' is required for dimension requests.")
            frame = f"*#{who}*{where}*{dimension}##"

        elif cmd_type in ("dimension_writing", "dim_write"):
            if dimension is None:
                raise ValueError("Parameter 'dimension' is required for dimension writing.")
            val_str = "*".join(str(v) for v in (values or []))
            if val_str:
                val_str = "*" + val_str
            frame = f"*#{who}*{where}*#{dimension}{val_str}##"

        else:
            raise ValueError(
                f"Unknown command_type '{command_type}'. Must be 'command', 'status_request', "
                "'dimension_request', or 'dimension_writing'."
            )

        parsed = self.parser.parse(frame)
        return frame, parsed

    def generate_lighting(
        self,
        where: str,
        action: str,
        brightness_pct: int | None = None,
        transition_speed: int | None = None,
    ) -> str:
        """Generate lighting frame."""
        act = action.lower().strip()
        if act == "off":
            return f"*1*0*{where}##"
        if act == "on":
            if transition_speed is not None:
                speed = max(1, min(10, int(transition_speed)))
                return f"*1*1#{speed}*{where}##"
            return f"*1*1*{where}##"
        if act == "dim" or brightness_pct is not None:
            pct = max(1, min(100, int(brightness_pct or 100)))
            speed = max(0, min(10, int(transition_speed or 0)))
            return f"*#1*{where}*#1*{pct}*{speed}##"
        if act == "toggle":
            return f"*1*13*{where}##"
        raise ValueError(f"Unknown lighting action '{action}'. Use 'on', 'off', 'dim', or 'toggle'.")

    def generate_cover(
        self,
        where: str,
        action: str,
        position_pct: int | None = None,
    ) -> str:
        """Generate automation/cover frame."""
        act = action.lower().strip()
        if act in ("up", "open"):
            return f"*2*1*{where}##"
        if act in ("down", "close"):
            return f"*2*2*{where}##"
        if act == "stop":
            return f"*2*0*{where}##"
        if act == "position" or position_pct is not None:
            pos = max(0, min(100, int(position_pct or 0)))
            return f"*#2*{where}*#10*{pos}##"
        raise ValueError(f"Unknown cover action '{action}'. Use 'up', 'down', 'stop', or 'position'.")

    def generate_climate(
        self,
        zone: int,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> str:
        """Generate climate temperature setpoint or mode frame."""
        # Modes: 1 = heating, 2 = cooling, 3 = generic
        mode_code = 1
        if mode:
            m = mode.lower()
            if "cool" in m:
                mode_code = 2
            elif "off" in m:
                return f"*4*100*{zone}##"
            elif "antifreeze" in m:
                return f"*4*110*{zone}##"

        if target_temp is not None:
            tenths = int(round(target_temp * 10))
            temp_str = f"{tenths:04d}"
            return f"*#4*{zone}*#14*{temp_str}*{mode_code}##"

        return f"*4*10{mode_code}*{zone}##"

    def generate_cen(
        self,
        where: str,
        button: int,
        press_type: str = "short",
        is_cen_plus: bool = False,
    ) -> str:
        """Generate CEN or CEN+ button event frame."""
        p_type = press_type.lower()
        if is_cen_plus:
            # WHO=25
            if "start" in p_type or "long" in p_type:
                return f"*25*22#{button}*{where}##"
            if "release" in p_type:
                return f"*25*24#{button}*{where}##"
            return f"*25*21#{button}*{where}##"
        else:
            # WHO=15
            if "start" in p_type or "long" in p_type:
                return f"*15*0*{where}#{button}##"
            if "release" in p_type:
                return f"*15*2*{where}#{button}##"
            return f"*15*1*{where}#{button}##"

    def generate_ha_yaml(
        self,
        platform: str,
        name: str,
        where: str,
        **kwargs: Any,
    ) -> str:
        """Generate Home Assistant configuration YAML block."""
        plat = platform.lower().strip()
        lines = [f"# Home Assistant MyHOME Configuration for {name}"]

        if plat in ("light", "lights"):
            lines.append("myhome:")
            lines.append("  lights:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            dim = kwargs.get("dimmable", False)
            lines.append(f"      dimmable: {str(dim).lower()}")
            if "transition" in kwargs:
                lines.append(f"      transition: {kwargs['transition']}")

        elif plat in ("cover", "covers"):
            lines.append("myhome:")
            lines.append("  covers:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            if "run_time" in kwargs:
                lines.append(f"      run_time: {kwargs['run_time']}")

        elif plat in ("climate", "climates"):
            lines.append("myhome:")
            lines.append("  climates:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      zone: {where}")
            lines.append(f"      name: \"{name}\"")
            lines.append(f"      heat_support: {str(kwargs.get('heat_support', True)).lower()}")
            lines.append(f"      cool_support: {str(kwargs.get('cool_support', False)).lower()}")

        elif plat in ("sensor", "sensors", "energy"):
            lines.append("myhome:")
            lines.append("  sensors:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            s_type = kwargs.get("type", "power")
            lines.append(f"      type: \"{s_type}\"")

        elif plat in ("switch", "switches"):
            lines.append("myhome:")
            lines.append("  switches:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")

        elif plat in ("media_player", "sound"):
            lines.append("myhome:")
            lines.append("  media_players:")
            lines.append(f"    {self._slugify(name)}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")

        else:
            lines.append(f"# Custom entity for platform '{plat}'")
            lines.append(f"# Address WHERE: {where}")
            for k, v in kwargs.items():
                lines.append(f"# {k}: {v}")

        return "\n".join(lines)

    def _slugify(self, text: str) -> str:
        s = text.lower().strip()
        s = "".join(c if c.isalnum() else "_" for c in s)
        while "__" in s:
            s = s.replace("__", "_")
        return s.strip("_") or "entity"
