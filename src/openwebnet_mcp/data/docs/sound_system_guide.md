# Sound System & Multi-Room Audio Guide (WHO = 16, WHO = 22)

The sound system platform (`media_player.py`) interfaces with BTicino multi-room audio matrices (F441, F441M), amplifier modules (3484), and local speaker controls.

## 🎵 Commands & Dimensions

### Basic Commands
- `*16*1*WHERE##`: Turn ON room amplifier (recalls previous audio source).
- `*16*0*WHERE##`: Turn OFF room amplifier.
- `*16*10*WHERE##`: Step volume UP.
- `*16*11*WHERE##`: Step volume DOWN.
- `*16*100*WHERE##`: Select Source 1 (Tuner).
- `*16*101*WHERE##`: Select Source 2 (Aux In).
- `*16*102*WHERE##`: Select Source 3.
- `*16*103*WHERE##`: Select Source 4.

### Exact Volume Control (Dimension 1)
- Query: `*#16*WHERE*1##`
- Set level: `*#16*WHERE*#1*<LEVEL>##` where LEVEL is an integer between `0` (mute) and `30` (maximum volume).

## 📋 YAML Configuration Example

```yaml
myhome:
  media_players:
    kitchen_audio:
      where: "1"
      name: "Kitchen Audio"
    living_room_audio:
      where: "2"
      name: "Living Room Audio"
```
