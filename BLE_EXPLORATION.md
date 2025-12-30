# BLE Exploration: Technical Reference

A deep dive into Bluetooth Low Energy (BLE) protocol exploration, focusing on macOS CoreBluetooth challenges, IKEA Idåsen standing desk protocol reverse engineering, and wearable device discovery.

---

## Table of Contents

1. [BLE Fundamentals Discovered](#ble-fundamentals-discovered)
2. [IKEA Idåsen / Linak Desk Protocol](#ikea-idåsen--linak-desk-protocol)
3. [Manufacturer IDs and Advertisement Data](#manufacturer-ids-and-advertisement-data)
4. [The Ultrahuman Ring Discovery](#the-ultrahuman-ring-discovery)
5. [Security Implications](#security-implications)

---

## BLE Fundamentals Discovered

### macOS Bluetooth Permission Model

#### The Crash We Hit

When first attempting to scan for BLE devices on macOS, applications would immediately crash with no clear error message. This is a **critical security feature** of macOS's privacy framework, not a bug.

**Key Discovery**: macOS requires explicit Bluetooth permissions to be granted before any BLE operations. The crash occurs because:

1. CoreBluetooth framework enforces strict entitlement checks
2. Applications without proper permissions cannot even initialize `CBCentralManager`
3. The system doesn't provide a graceful error - it terminates the process

#### blueutil Revelation

The `blueutil` command-line tool revealed the underlying issue:

```text
Bluetooth: Permission denied (missing entitlement)
```

This error message exposed that:

- macOS uses **entitlements** to control Bluetooth access
- Python scripts running via terminal inherit terminal's permissions
- Terminal.app itself needs Bluetooth access granted in System Preferences → Privacy & Security → Bluetooth

**Resolution Path**:

1. Grant Terminal.app Bluetooth permission in System Preferences
2. Restart terminal session
3. BLE operations now work without crashes

### CoreBluetooth vs bleak

#### Why bleak Crashed

`bleak` is a cross-platform BLE library that wraps platform-specific APIs:

- On macOS: Uses CoreBluetooth via PyObjC bindings
- On Linux: Uses BlueZ D-Bus API
- On Windows: Uses WinRT APIs

The crash occurred because:

1. bleak initializes CoreBluetooth's `CBCentralManager`
2. Without permissions, this initialization triggers immediate termination
3. Python's exception handling can't catch system-level permission failures
4. The process exits before Python can report an error

#### Native CoreBluetooth Also Crashed

Using PyObjC to call CoreBluetooth directly showed the **same behavior**:

```python
from CoreBluetooth import CBCentralManager
manager = CBCentralManager.alloc().initWithDelegate_queue_(delegate, None)
# Process terminated: no error, no exception, just crash
```

This confirmed the issue was **not with bleak**, but with macOS's security model.

#### The Permission Model

macOS enforces a three-tier permission system for Bluetooth:

1. **Entitlements** (compile-time): Apps must declare Bluetooth usage in Info.plist
2. **Privacy Database** (user consent): User must grant permission in System Preferences
3. **Runtime State**: CoreBluetooth reports state via `CBCentralManagerState` enum

States:

- `0` = Unknown
- `1` = Resetting
- `2` = Unsupported (no Bluetooth hardware)
- `3` = **Unauthorized** (permission denied)
- `4` = PoweredOff
- `5` = PoweredOn (ready)

**Critical Insight**: State 3 (Unauthorized) is only observable if the app doesn't crash first. For terminal-based scripts, getting past state 0 requires terminal permissions.

### BLE vs Classic Bluetooth

#### Why the Ultrahuman Ring Wasn't in Paired Devices

Classic Bluetooth (BR/EDR) and Bluetooth Low Energy (BLE) are **fundamentally different protocols**:

**Classic Bluetooth (BR/EDR)**:

- Designed for continuous streaming (audio, file transfer)
- Requires pairing with PIN codes or passkeys
- Shows up in System Preferences → Bluetooth as "paired devices"
- Higher power consumption
- Examples: Headphones, keyboards, mice

**Bluetooth Low Energy (BLE)**:

- Designed for sporadic, small data transfers
- **No pairing required** for many operations
- Can operate entirely via GATT (Generic Attribute Protocol) without bonding
- Much lower power consumption
- Devices only visible during active scanning

**The Ultrahuman Ring Discovery**:

- Uses BLE exclusively, not classic Bluetooth
- Never appears in "Bluetooth Devices" list in System Preferences
- Only visible when actively advertising (broadcasting presence)
- Communicates exclusively with its companion app
- Uses GATT services for data access (heart rate, temperature, sleep data)

**Why This Matters**:

- You cannot "pair" with a BLE device the way you pair headphones
- BLE devices are invisible unless you actively scan for them
- Connection is ephemeral - devices can be connected to without persistent pairing
- Many BLE devices only advertise when their app is open or on a schedule

---

## IKEA Idåsen / Linak Desk Protocol

The IKEA Idåsen standing desk uses a Linak controller with a well-defined BLE GATT profile. This protocol was reverse-engineered by examining GATT services and experimenting with characteristic writes.

### GATT Service Structure

The desk exposes several proprietary GATT services under the vendor UUID namespace `99faXXXX-338a-1024-8a49-009c0215f78a`:

#### Service 1: Control Service (0x0001)

**Service UUID**: `99fa0001-338a-1024-8a49-009c0215f78a`

Contains characteristics for sending commands and reading responses:

##### **Characteristic: Command (0x0002)**

- UUID: `99fa0002-338a-1024-8a49-009c0215f78a`
- Properties: `WRITE`, `WRITE_NO_RESP`
- Purpose: Send movement commands to desk
- Format: 2-byte commands

##### **Characteristic: Reference (0x0003)**

- UUID: `99fa0003-338a-1024-8a49-009c0215f78a`
- Properties: `READ`
- Purpose: Read command responses (rarely used)

#### Service 2: Unknown Service (0x0010)

**Service UUID**: `99fa0010-338a-1024-8a49-009c0215f78a`

##### **Characteristic (0x0011)**

- UUID: `99fa0011-338a-1024-8a49-009c0215f78a`
- Properties: `READ`, `WRITE`
- Observed value: `0x1f` (31 decimal)
- Purpose: **Unknown** - possibly configuration or status flags

#### Service 3: Position Service (0x0020)

**Service UUID**: `99fa0020-338a-1024-8a49-009c0215f78a`

##### **Characteristic: Height (0x0021)**

- UUID: `99fa0021-338a-1024-8a49-009c0215f78a`
- Properties: `READ`, `NOTIFY`
- Purpose: Current desk height and movement speed
- Format: 4 bytes (little-endian)
  - Bytes 0-1: Height (unsigned 16-bit integer)
  - Bytes 2-3: Speed (signed 16-bit integer)

**Height Encoding**:

```python
raw_value = bytes[0:2] as uint16_le
height_mm = (raw_value / 10) + 620
```

- Raw units represent 0.1mm increments
- Base offset: 620mm (minimum desk height)
- Example: Raw value `0x0000` = 620mm, `0x0190` (400 decimal) = 660mm

**Speed Encoding**:

- Positive values: Moving up
- Negative values: Moving down
- Zero: Stationary
- Units: Unknown, but relative to movement direction

#### Service 4: Memory Positions (0x0030)

**Service UUID**: `99fa0030-338a-1024-8a49-009c0215f78a`

##### **Characteristic: Memory Position 1 (0x0031)**

- UUID: `99fa0031-338a-1024-8a49-009c0215f78a`
- Properties: `READ`, `WRITE`
- Purpose: Store/recall preset height position 1

**Additional Memory Positions**:

- Position 2: `99fa0032-...`
- Position 3: `99fa0033-...`
- Position 4: `99fa0034-...`

**Behavior**:

- **Reading** the characteristic triggers movement to stored position
- **Writing** stores current height as preset

### Command Bytes

Commands are 2-byte sequences written to the Command characteristic (0x0002):

| Command | Hex Bytes   | Effect                     |
| ------- | ----------- | -------------------------- |
| UP      | `0x47 0x00` | Move desk upward           |
| DOWN    | `0x46 0x00` | Move desk downward         |
| STOP    | `0xFF 0x00` | Stop all movement          |
| WAKEUP  | `0xFE 0x00` | Wake controller from sleep |

### Movement Behavior

#### Continuous Command Requirement

**Critical Discovery**: The desk requires **continuous command transmission** to maintain movement.

- Sending `UP` or `DOWN` once only moves for ~1 second
- Movement stops automatically if no new command received
- To move for 5 seconds: Send command, wait, send STOP
- **Safety Feature**: Prevents runaway movement if connection drops

**Implementation Pattern**:

```text
1. Send WAKEUP command
2. Send UP/DOWN command
3. Wait desired duration
4. Send STOP command
5. Read height to confirm new position
```

#### Movement Speed

The desk moves at approximately **38mm per second** based on empirical testing.

**Height Range**:

- Minimum: 620mm (~24.4 inches)
- Maximum: 1270mm (~50 inches)
- Range: 650mm (~25.6 inches)
- Full travel time: ~17 seconds

### Protocol Quirks

1. **No Acknowledgment**: Commands don't return success/failure - you must monitor height notifications
2. **Sleep Mode**: Desk enters low-power mode after inactivity, requiring WAKEUP before commands
3. **Concurrent Control**: Multiple BLE clients can send commands simultaneously (last command wins)
4. **Height Notifications**: Can be enabled via `start_notify()` for real-time position updates

### Collision Detection & Safety Features

The desk has built-in **anti-collision protection** that immediately stops movement when:

- **Physical obstacles** are detected (objects on/under desk)
- **Unexpected resistance** occurs (load changes, friction)
- **Cable tension** pulls against movement direction
- **Motor strain** exceeds safe thresholds

**Behavior**: The desk stops silently — no error is returned via BLE. From the protocol's perspective, the desk simply stops responding to movement commands. The only way to detect this is to monitor the height characteristic and notice it stopped changing before reaching the target.

**Implication for Software Control**: When implementing precision movement, you must:

1. Monitor actual height during movement
2. Detect when desk stops unexpectedly (height stable but not at target)
3. Handle this gracefully — retrying won't help if obstruction remains

### Precision Movement Control

Moving to an exact height requires accounting for **momentum and deceleration**:

**The Problem**: Sending STOP doesn't instantly halt the desk. It takes ~200ms to fully stop, during which the desk travels an additional 8-10mm depending on direction.

**Empirical Findings**:

| Direction | Stopping Distance | Reason                        |
| --------- | ----------------- | ----------------------------- |
| Down      | ~10mm             | Gravity assists momentum      |
| Up        | ~8mm              | Gravity resists, slows faster |

**Solution**: Implement "early stopping" — send STOP command when the desk is within the stopping distance of the target, allowing momentum to carry it the rest of the way.

**Control Loop Pattern**:

```text
1. Calculate target height
2. Determine direction and stopping distance (8mm up, 10mm down)
3. Send movement command every 100ms
4. Read height between commands
5. When (remaining distance ≤ stopping distance): send STOP
6. Wait 300ms for desk to settle
7. Read final height and calculate error
```

**Achievable Precision**: With proper early stopping, errors of **0-2mm** are typical (well under 0.1 inch).

---

## Manufacturer IDs and Advertisement Data

BLE devices broadcast **advertisement packets** containing:

- Device name (optional)
- Service UUIDs (optional)
- Manufacturer-specific data
- Transmission power
- Flags

### Manufacturer Data Format

Manufacturer data is a binary payload with a 2-byte **Company ID** assigned by Bluetooth SIG.

**Structure**:

```text
Byte 0-1: Company ID (little-endian)
Byte 2+:  Manufacturer-specific data
```

### Manufacturer IDs Encountered

| ID (Hex) | Company             | Typical Devices                         |
| -------- | ------------------- | --------------------------------------- |
| `0x004C` | Apple Inc.          | iPhones, AirPods, Apple Watch, AirTags  |
| `0x7500` | Samsung Electronics | Galaxy phones, Galaxy Buds, SmartThings |
| `0x0157` | Ultrahuman          | Ultrahuman Ring (confirmed)             |

### Decoding Manufacturer Data

#### **Example: Apple Device Advertisement**

```text
Manufacturer ID: 0x004C
Data: 0x10050318c0a8f4
```

Breakdown:

- `0x10`: Apple advertisement type (proximity pairing)
- `0x05`: Payload length
- `0x03`: Subtype
- `0x18c0a8f4`: Device-specific identifier

**Samsung Device**:

```text
Manufacturer ID: 0x7500
Data: 0x42...
```

- Samsung uses custom protocols for Galaxy device features

**Practical Use**:

- Filter scans by manufacturer ID to find specific device types
- Decode Apple's iBeacon format for proximity detection
- Identify device capabilities before connecting

---

## The Ultrahuman Ring Discovery

### Why It Wasn't Showing with an Obvious Name

Several factors made the Ultrahuman Ring difficult to discover:

#### 1. BLE-Only Design

- No classic Bluetooth stack
- Never appears in system Bluetooth settings
- Only visible during active BLE scanning

#### 2. Advertisement Strategy

- **Not continuously advertising**: Devices may only advertise when:
  - Companion app is open
  - User interacts with device (button press, tap)
  - On a scheduled sync interval (e.g., every 15 minutes)
- Power-saving measure to extend battery life

#### 3. Name Obfuscation

- May advertise with:
  - Generic name (e.g., "BLE Device", "Sensor")
  - MAC address only (no name)
  - Manufacturer code in name (e.g., "UH-XXXX")
- Privacy consideration: Prevents passive tracking by name

#### 4. Service UUID Filtering

- Companion app likely scans for specific service UUIDs
- Generic scanners won't recognize proprietary services
- Device may not advertise service UUIDs in broadcast (only during connection)

### UltraSignal Developer Platform

**Official API Access**:

- Ultrahuman provides **UltraSignal** developer API
- Requires:
  - User authorization via companion app
  - API token for backend access
  - HTTPS REST endpoints for data retrieval

**Data Available**:

- Heart rate variability (HRV)
- Sleep stages and quality scores
- Body temperature trends
- Movement index
- Recovery metrics

**Why Direct BLE Access is Limited**:

- **Authentication**: Proprietary pairing between ring and app
- **Encryption**: GATT data likely encrypted with session keys
- **Firmware**: Ring firmware only responds to authenticated commands
- **Medical Device Considerations**: Data access controlled for regulatory compliance

### Discovery Strategy

To find BLE-only wearables like the Ultrahuman Ring:

1. **Scan while interacting**: Open companion app during scan
2. **Extended scan duration**: Scan for 30+ seconds to catch infrequent advertisements
3. **Monitor manufacturer data**: Filter by known manufacturer IDs
4. **RSSI-based proximity**: Strongest signal often indicates device on your body
5. **Service UUID hints**: Look for health-related UUIDs (Heart Rate: 0x180D, etc.)

---

## Security Implications

### IKEA Idåsen Desk: Zero Authentication

**Critical Security Flaw**: The desk has **no authentication or authorization**.

**Attack Vector**:

1. Scan for devices named "Desk" or with service UUID `99fa0001-...`
2. Connect to device (no pairing required)
3. Write commands to characteristic `99fa0002`
4. Desk responds to commands from **any BLE client**

**Real-World Implications**:

- Anyone within BLE range (~10-30 meters) can control desk
- Office environments with multiple desks are vulnerable
- Pranksters could raise/lower desks remotely
- Safety risk: Unexpected movement could cause injury

**Why This Design**:

- Simplicity: No pairing UI on desk controller
- Convenience: Easy to connect from multiple devices/apps
- Legacy: Protocol designed before IoT security best practices

**Mitigation Strategies**:

- Physical security: Control access to workspace
- BLE jamming: Block unauthorized connections (not practical)
- Firmware update: Linak would need to add authentication (unlikely for existing units)

### BLE Security Lessons

1. **Advertising is Public**: Anyone can see advertisement data
2. **GATT Without Pairing**: Many devices allow connections without bonding
3. **Service Discovery**: GATT structure is fully enumerable by any client
4. **Write Operations**: Without authentication, anyone can write to characteristics
5. **Privacy**: Device names and manufacturer data leak identity

**Best Practices for BLE Devices**:

- Implement pairing/bonding for sensitive operations
- Use encrypted characteristics for private data
- Require authentication before accepting write commands
- Randomize MAC addresses to prevent tracking
- Limit advertisement data to necessary information

---

## Conclusion

This exploration revealed:

1. **macOS CoreBluetooth** requires explicit permissions and crashes ungracefully without them
2. **BLE vs Classic Bluetooth** are separate protocols - BLE devices won't show in traditional pairing lists
3. **IKEA Idåsen desks** use an open, unauthenticated protocol with well-defined GATT services
4. **Manufacturer IDs** help identify device vendors from advertisement data
5. **Wearables like Ultrahuman Ring** use BLE exclusively and may not advertise continuously

The desk protocol demonstrates both the **power and danger** of BLE: easy to reverse-engineer and control, but with zero security. The Ultrahuman Ring shows the opposite: BLE used carefully with app-controlled access and encrypted data channels.

**Key Takeaway**: BLE's low power and simplicity come at the cost of security. Always assume BLE traffic is observable and exploitable without proper authentication layers.
