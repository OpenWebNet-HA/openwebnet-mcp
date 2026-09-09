# Technical Design: Software Stepped Dimming & Light Transitions

## 🎯 Architectural Problem Statement

Home Assistant `light.turn_on` and `light.turn_off` service calls allow passing `transition` (fade duration in seconds). In BTicino OpenWebNet:
1. Native hardware speed values (`*1*1#speed*where##`) range only from 1 to 10.
2. Older actuators (e.g. F411 relay, early F418 dimmers, or MH200 gateways) ignore the speed parameter or jump instantly between levels.
3. Multi-bus routed devices (`where#4#bus`) frequently drop or delay speed metadata over F422 couplers.

## 🛠️ Software Emulation Solution

The software stepped dimming solution in `custom_components/myhome`:
- Calculates micro-step increments (e.g. 5% every 250ms).
- Dispatches sequential instant brightness writes `*#1*WHERE*#1*<LEVEL>*0##`.
- Updates Home Assistant's optimistic state during the ramp for immediate UI responsiveness.
- Cancels previous in-flight transitions if a new turn_on/turn_off command arrives.
- Rate-limits SCS traffic to protect the 9600 baud physical bus from packet collisions.
