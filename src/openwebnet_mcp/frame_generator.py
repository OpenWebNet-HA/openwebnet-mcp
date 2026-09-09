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
        gateway: str = "f454",
        mac: str = "00:03:50:xx:xx:xx",
        **kwargs: Any,
    ) -> str:
        """Generate Home Assistant configuration YAML block (both modern myhome.yaml and legacy)."""
        plat = platform.lower().strip()
        slug = self._slugify(name)
        lines = [
            f"# ==========================================================",
            f"# Home Assistant MyHOME Configuration for '{name}'",
            f"# ==========================================================",
            f"#",
            f"# Option A: Modern MyHOME (v0.9+) -> Add to /config/myhome.yaml",
            f"# ----------------------------------------------------------",
            f"{gateway}:",
            f"  mac: '{mac}'  # Gateway MAC address (mandatory in modern integration)",
        ]

        if plat in ("light", "lights"):
            dim = kwargs.get("dimmable", False)
            lines.append("  light:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            lines.append(f"      dimmable: {str(dim).lower()}")
            if "transition" in kwargs:
                lines.append(f"      transition: {kwargs['transition']}")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  lights:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
                f"      dimmable: {str(dim).lower()}",
            ])
            if "transition" in kwargs:
                lines.append(f"      transition: {kwargs['transition']}")

        elif plat in ("cover", "covers"):
            lines.append("  cover:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            if "run_time" in kwargs:
                lines.append(f"      run_time: {kwargs['run_time']}")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  covers:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
            ])
            if "run_time" in kwargs:
                lines.append(f"      run_time: {kwargs['run_time']}")

        elif plat in ("climate", "climates"):
            heat_val = str(kwargs.get("heat", kwargs.get("heat_support", True))).lower()
            cool_val = str(kwargs.get("cool", kwargs.get("cool_support", False))).lower()
            lines.append("  climate:")
            lines.append(f"    {slug}:")
            lines.append(f"      zone: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            lines.append(f"      heat: {heat_val}")
            lines.append(f"      cool: {cool_val}")
            lines.append("      standalone: false")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  climates:",
                f"    {slug}:",
                f"      zone: {where}",
                f"      name: \"{name}\"",
                f"      heat_support: {heat_val}",
                f"      cool_support: {cool_val}",
            ])

        elif plat in ("sensor", "sensors", "energy"):
            s_type = kwargs.get("type", "power")
            lines.append("  sensor:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            lines.append(f"      type: \"{s_type}\"")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  sensors:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
                f"      type: \"{s_type}\"",
            ])

        elif plat in ("switch", "switches"):
            lines.append("  switch:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  switches:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
            ])

        elif plat in ("media_player", "sound"):
            lines.append("  media_player:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  media_players:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
            ])

        elif plat in ("binary_sensor", "binary_sensors", "contact", "motion"):
            dev_class = kwargs.get("class", kwargs.get("device_class", "opening"))
            who_val = str(kwargs.get("who", "25"))
            lines.append("  binary_sensor:")
            lines.append(f"    {slug}:")
            lines.append(f"      where: \"{where}\"")
            lines.append(f"      name: \"{name}\"")
            lines.append(f"      class: {dev_class}")
            if who_val != "25":
                lines.append(f"      who: \"{who_val}\"")

            lines.extend([
                "",
                "# Option B: Legacy MyHOME (pre-v0.9) -> configuration.yaml",
                "# ----------------------------------------------------------",
                "myhome:",
                "  binary_sensors:",
                f"    {slug}:",
                f"      where: \"{where}\"",
                f"      name: \"{name}\"",
                f"      class: {dev_class}",
            ])
            if who_val != "25":
                lines.append(f"      who: \"{who_val}\"")

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
