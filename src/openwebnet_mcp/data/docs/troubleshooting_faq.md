# Troubleshooting & OpenWebNet Diagnostics FAQ

## ❓ Common Issues & Solutions

### 1. Gateway returns NACK (`*#*0##`)
- **Cause 1**: The requested device address does not exist or is powered down.
- **Cause 2**: Syntax error in WHAT or DIMENSION fields.
- **Cause 3**: OpenWebNet password incorrect or session timed out.
- **Cause 4**: Gateway buffer overrun (too many frames dispatched too quickly).

### 2. Connection drops or timeouts
- BTicino gateways (F454, MH200) support a limited number of concurrent TCP sessions (typically 4 to 8 client connections).
- Ensure only one integration or debugging script holds open a command session at a time, or configure session re-use.

### 3. Actuators don't report state changes
- Verify whether the event session (`*99*1##`) is established. Without an active event session, the gateway will not push asynchronous SCS bus frames to Home Assistant.
