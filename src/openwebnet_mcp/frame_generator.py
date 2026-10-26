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
            # WHO_2.pdf p. 20: the only level write is the dimension 11
            # GoToLevel `*#2*WHERE*#11#<PRIORITY>*<LEVEL>##` (LEVEL 0..100);
            # dimension 10 is the read-only status (p. 19), it has no write.
            if position_pct is None:
                raise ValueError("cover action 'position' needs position_pct (0..100)")
            pos = int(position_pct)
            if not 0 <= pos <= 100:
                raise ValueError(f"position_pct must be 0..100 (WHO_2.pdf p. 6 <shutterLevel>), got {position_pct}")
            return f"*#2*{where}*#11#001*{pos}##"
        raise ValueError(f"Unknown cover action '{action}'. Use 'up', 'down', 'stop', or 'position'.")

    # WHO_4.pdf mode-only commands on a zone: OFF is WHAT 303 (p. 10),
    # anti-freeze 102 (p. 10), thermal protection 202 (p. 11), automatic
    # (weekly program) 311 (p. 9). Manual heating / conditioning / generic is
    # the dimension 14 write with M = 1 / 2 / 3 (pp. 8, 23); WHATs 100 / 101 /
    # 110 and 301 do not exist as commands in the document.
    _CLIMATE_MODE_WHATS = {
        "off": 303,
        "antifreeze": 102,
        "protection": 202,
        "auto": 311,
    }
    _CLIMATE_SETPOINT_MODES = {"heat": 1, "cool": 2, "generic": 3}
    _CLIMATE_MODE_ALIASES = {
        "anti-freeze": "antifreeze",
        "anti_freeze": "antifreeze",
        "thermal_protection": "protection",
        "automatic": "auto",
        "program": "auto",
        "heating": "heat",
        "cooling": "cool",
        "conditioning": "cool",
    }

    def generate_climate(
        self,
        zone: int | str,
        target_temp: float | None = None,
        mode: str | None = None,
        standalone: bool = False,
    ) -> str:
        """Generate a WHO 4 set-point write or mode command for one zone.

        OpenWebNet thermoregulation comes in two plant types, and the zone is
        addressed differently on each:

        * ``standalone=False`` (default): a plant with a central unit (3550,
          4695). The document addresses the zone *through the central unit*
          as ``#Z`` for both the mode commands (``*4*303*#Z##``, p. 10) and
          the set-point write (``*#4*#Z*#14*T*M##``, p. 8). ``zone=0`` is the
          central unit itself (``#0``: ``*4*303*#0##`` p. 24, ``*4*102*#0##``
          p. 27, ``*4*202*#0##`` p. 26, ``*#4*#0*#14*T*M##`` p. 23). Five of
          the twelve firmware-oracle gateways (F453, F453AV, H4684, MH200,
          MH200N) NACK a bare-zone set-point write on such a plant.
        * ``standalone=True``: thermostats without a central unit (4691 on
          the live F461 plant, the MyHomeServer1 plant of issue 466). They
          take the bare zone ``Z`` for both (``*4*303*Z##``,
          ``*#4*Z*#14*T*M##``); the ``#Z`` forms are silently ignored there.
          The bare-zone forms are not in the Legrand document (it lists
          ``*4*303*Z##`` etc. as monitor frames only).

        ``mode`` is one of ``off``, ``antifreeze``, ``protection``, ``auto``
        (mode-only commands, no ``target_temp``), or ``heat``, ``cool``,
        ``generic`` (manual set point, ``target_temp`` required). With no
        ``mode`` a ``target_temp`` is written in heating mode. The set point
        must be 5.0..40.0 °C in 0.5 °C steps (``0050``..``0400``, pp. 8, 23).
        A leading ``#`` on ``zone`` is stripped (the addressing form is chosen
        by ``standalone``, not by the caller).
        """
        zone_str = str(zone).strip()
        if zone_str.startswith("#"):
            zone_str = zone_str[1:]
        if not zone_str.isdigit() or not 0 <= int(zone_str) <= 99:
            raise ValueError(f"zone must be 0 (central unit) or 1..99, got {zone!r}")
        zone_num = int(zone_str)
        if zone_num == 0 and standalone:
            raise ValueError("zone 0 is the central unit (#0); a standalone plant has none")
        target = str(zone_num) if standalone else f"#{zone_num}"

        mode_name: str | None = None
        if mode is not None:
            key = mode.strip().lower().replace(" ", "_")
            mode_name = self._CLIMATE_MODE_ALIASES.get(key, key)
            if mode_name not in self._CLIMATE_MODE_WHATS and mode_name not in self._CLIMATE_SETPOINT_MODES:
                known = sorted([*self._CLIMATE_MODE_WHATS, *self._CLIMATE_SETPOINT_MODES])
                raise ValueError(f"Unknown climate mode {mode!r}; use one of {', '.join(known)}")

        if mode_name in self._CLIMATE_MODE_WHATS:
            if target_temp is not None:
                raise ValueError(
                    f"mode='{mode_name}' is a mode-only command (WHAT {self._CLIMATE_MODE_WHATS[mode_name]}); "
                    "it carries no set point. Use mode='heat', 'cool' or 'generic' with target_temp."
                )
            if mode_name == "auto" and zone_num == 0:
                raise ValueError(
                    "*4*311*#0## is not in WHO_4.pdf (automatic is a zone command, p. 9; the central unit "
                    "runs its programs with WHAT 1101..1103 / 2101..2103 / 3101..3103) and H4684 / MH200 NACK it"
                )
            return f"*4*{self._CLIMATE_MODE_WHATS[mode_name]}*{target}##"

        if target_temp is None:
            raise ValueError(
                "a manual heating / cooling / generic mode needs target_temp: the document sets it "
                "with the dimension 14 write (*#4*#Z*#14*T*M##, p. 8); use mode='off', "
                "'antifreeze', 'protection' or 'auto' for a mode-only command"
            )
        mode_code = self._CLIMATE_SETPOINT_MODES[mode_name or "heat"]
        exact_tenths = float(target_temp) * 10
        tenths = int(round(exact_tenths))
        # Validate the value as given, not its rounding: 20.04 is not 20.0.
        if abs(exact_tenths - tenths) > 1e-6 or not 50 <= tenths <= 400 or tenths % 5:
            raise ValueError(
                f"target_temp must be 5.0..40.0 °C in 0.5 °C steps (WHO_4.pdf pp. 8, 23: T = 0050..0400 "
                f"by 0.5° step), got {target_temp}"
            )
        return f"*#4*{target}*#14*{tenths:04d}*{mode_code}##"

    def generate_cen(
        self,
        where: str,
        button: int,
        press_type: str = "short",
        is_cen_plus: bool = False,
    ) -> str:
        """Generate CEN or CEN+ button event frame."""
        p_type = press_type.lower()
        if not 0 <= int(button) <= 31:
            raise ValueError(f"{'CEN+' if is_cen_plus else 'CEN'} button must be between 0 and 31")
        # Release is matched first so "long_release" is not taken for a long press.
        if is_cen_plus:
            # WHO=25: *25*WHAT#PUSHBUTTON*WHERE##, WHERE = "2" + Object.
            # A short press is one "short" frame (no release follows); a long
            # press is "start_long", zero or more "held", then "release".
            if "short_release" in p_type:
                raise ValueError("CEN+ has no short-release frame: WHAT 21 is the whole short press")
            if "release" in p_type:
                return f"*25*24#{int(button)}*{where}##"
            if "held" in p_type or "repeat" in p_type:
                return f"*25*23#{int(button)}*{where}##"
            if "start" in p_type or "long" in p_type:
                return f"*25*22#{int(button)}*{where}##"
            return f"*25*21#{int(button)}*{where}##"
        else:
            # WHO=15: *15*BUTTON[#PHASE]*WHERE##, button 00..31 in WHAT.
            # A short press is "short" then "short_release"; a long press is
            # "short", one or more "start_long", then "release".
            btn = f"{int(button):02d}"
            if "short_release" in p_type:
                return f"*15*{btn}#1*{where}##"
            if "release" in p_type:
                return f"*15*{btn}#2*{where}##"
            if "start" in p_type or "long" in p_type or "held" in p_type or "repeat" in p_type:
                return f"*15*{btn}#3*{where}##"
            return f"*15*{btn}*{where}##"

    def generate_sound_source_selection(
        self,
        amplifier: str,
        source: int,
        base_band: bool = False,
    ) -> list[str]:
        """Build the pair of frames that routes an amplifier's room to a source.

        WHO=16 has no documented "select source" command: the specification
        defines source cycling only. Installations perform directed selection
        with a routing pseudo address, ``1`` + environment + source, where the
        environment is the first digit of a two-digit amplifier address. That
        form is established from captures on two F441M installations.

        Because the matrix switches per output and an output serves a whole
        environment, every amplifier in that environment follows the change.

        Args:
            amplifier: Amplifier address (``"23"``) or a bare environment digit.
            source: Source device number, 1-9.
            base_band: Use the base-band WHAT (0) instead of stereo channel (3).
                Every captured installation uses the stereo channel.

        Returns:
            ``[activate_source, route_environment]`` in the order the wall
            controls send them.

        Raises:
            ValueError: If the source is out of range or the address is not numeric.
        """
        address = str(amplifier).strip()
        if not address.isdigit():
            raise ValueError(f"amplifier address must be numeric, got {amplifier!r}")
        if not 1 <= int(source) <= 9:
            raise ValueError(f"source must be between 1 and 9, got {source!r}")

        environment = address[0] if len(address) > 1 else address
        what = 0 if base_band else 3
        return [
            f"*16*{what}*{100 + int(source)}##",
            f"*16*{what}*1{environment}{int(source)}##",
        ]

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
