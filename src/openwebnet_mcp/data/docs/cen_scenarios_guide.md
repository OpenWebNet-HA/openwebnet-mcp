# CEN & CEN+ Scenario Pushbuttons Guide (WHO = 15, WHO = 25)

CEN and CEN+ scenario pushbuttons are physical wall switches configured to emit control signals rather than directly switching a load. They allow physical keypresses to trigger advanced automations, scenes, and integrations in Home Assistant.

## 🔘 CEN (WHO = 15) vs CEN+ (WHO = 25)

| Feature | CEN (WHO = 15) | CEN+ (WHO = 25) |
|---|---|---|
| Button | WHAT = button `00..31` (leading zero significant) | WHAT parameter `#B`, `0..31` |
| Source (`WHERE`) | Source address; never the button (`#3` riser, `#4#I` local bus) | `2` + virtual Object `0..2047` (`21` = Object 1, `2101` = Object 101) |
| Pressure / short press | `*15*B*WHERE##` (start of *every* press) | `*25*21#B*WHERE##` (whole short press, no release frame) |
| Release after short press | `*15*B#1*WHERE##` | — (CEN+ sends none) |
| Start of long press | first `*15*B#3*WHERE##` (no distinct frame) | `*25*22#B*WHERE##` (no `21` before it) |
| Long press heartbeat (~0.5 s) | repeated `*15*B#3*WHERE##` | `*25*23#B*WHERE##` (zero or more) |
| Release after long press | `*15*B#2*WHERE##` | `*25*24#B*WHERE##` |
| Rotary selector | — | `25` / `26` slow / fast clockwise, `27` / `28` slow / fast counter-clockwise |

Examples from the OpenWebNet Encyclopedia ([CEN](https://github.com/OpenWebNet-HA/OpenWebNet-Encyclopedia/blob/305278651b593a785271c7c4df15d9e802a41ffb/functional/who-15-cen/README.md), [CEN+](https://github.com/OpenWebNet-HA/OpenWebNet-Encyclopedia/blob/c57dcecbc1e3b1c9047aa21875ee3deb1b763010/functional/who-25-transversal/cen-plus.md)):

- A short CEN press is `*15*02*22##` then `*15*02#1*22##`; a long press is `*15*02*22##`, one or more `*15*02#3*22##`, then `*15*02#2*22##`. Other sources: `*15*01*0001##`, `*15*06*36#4#01##`.
- A short CEN+ press is `*25*21#1*21##` alone; a long press is `*25*22#1*21##`, zero or more `*25*23#1*21##`, then `*25*24#1*21##`.

Dry contacts and IR detectors share `WHO 25` but not its fields: `*25*31#1*WHERE##` (ON / detection) and `*25*32#1*WHERE##` (OFF), where `#1` marks an event and `#0` a reply to `*#25*WHERE##`. `WHERE` is `1..201` (automation interfaces) or `A`/`PL` (alarm contacts and IR detectors).

## 🪄 Home Assistant Blueprint Integration

The Home Assistant community maintains the official **MyHome CEN+ Commands Blueprint** (`community.home-assistant.io/t/myhome-cen-commands/260345`).
MyHOME fires `myhome_cen_event` (WHO 15) and `myhome_cenplus_event` (WHO 25) with `object`, `pushbutton`, `event` and `where`. For a CEN toggle, trigger on the short *release*: `pushbutton_short_press` also fires at the start of every long press. For CEN+, `pushbutton_short_press` is the whole short press, and `pushbutton_long_press` currently fires for both `22` and every `23` repeat.
```yaml
trigger:
  - platform: event
    event_type: myhome_cen_event
    event_data:
      object: 22
      pushbutton: 2
      event: "pushbutton_short_release"
action:
  - service: light.toggle
    target:
      entity_id: light.living_room_ceiling
```
