"""
IKEA Idåsen / Linak Standing Desk Controller

Protocol reverse-engineered from:
- https://github.com/anson-vandoren/linak-desk-spec
- https://github.com/j5lien/esphome-idasen-desk-controller
"""

import asyncio
import logging
import struct
import warnings
from contextlib import suppress

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

# Suppress bleak's internal asyncio warnings (race condition in CoreBluetooth backend)
warnings.filterwarnings("ignore", message=".*invalid state.*")
logging.getLogger("bleak").setLevel(logging.ERROR)


# === LINAK BLE UUIDS ===
UUID_COMMAND = "99fa0002-338a-1024-8a49-009c0215f78a"
UUID_HEIGHT = "99fa0021-338a-1024-8a49-009c0215f78a"

# Memory preset UUIDs (1-4)
UUID_MEMORY = {
    1: "99fa0031-338a-1024-8a49-009c0215f78a",
    2: "99fa0032-338a-1024-8a49-009c0215f78a",
    3: "99fa0033-338a-1024-8a49-009c0215f78a",
    4: "99fa0034-338a-1024-8a49-009c0215f78a",
}

# === COMMANDS ===
CMD_UP = bytearray([0x47, 0x00])
CMD_DOWN = bytearray([0x46, 0x00])
CMD_STOP = bytearray([0xFF, 0x00])
CMD_WAKEUP = bytearray([0xFE, 0x00])

# === CONSTANTS ===
BASE_HEIGHT_MM = 620
MIN_HEIGHT_MM = 620
MAX_HEIGHT_MM = 1270


class DeskError(Exception):
    """Base exception for desk controller errors."""

    pass


class DeskNotFoundError(DeskError):
    """Raised when desk cannot be found via BLE scan."""

    pass


class DeskConnectionError(DeskError):
    """Raised when connection to desk fails."""

    pass


class DeskCommunicationError(DeskError):
    """Raised when BLE communication fails during operation."""

    pass


def raw_to_mm(raw: int) -> int:
    """Convert raw units to millimeters (includes base offset)."""
    return (raw // 10) + BASE_HEIGHT_MM


def parse_height_data(data: bytes) -> tuple[int, int]:
    """Parse height characteristic data. Returns (height_mm, speed)."""
    if len(data) >= 4:
        raw_height = struct.unpack("<H", data[0:2])[0]
        speed = struct.unpack("<h", data[2:4])[0]
        return raw_to_mm(raw_height), speed
    return 0, 0


class DeskController:
    """Controller for IKEA Idåsen / Linak standing desk."""

    def __init__(self, name: str = "Desk", quiet: bool = False):
        self.name = name
        self.quiet = quiet
        self.device = None
        self.client = None
        self.current_height = 0
        self.current_speed = 0
        self._connected = False
        self._disconnecting = False  # Track intentional disconnect

    def _log(self, msg: str):
        """Print message unless in quiet mode."""
        if not self.quiet:
            print(msg)

    async def connect(self, timeout: float = 30.0, retries: int = 2) -> bool:
        """
        Find and connect to the desk.

        Args:
            timeout: Connection timeout in seconds
            retries: Number of connection attempts

        Raises:
            DeskNotFoundError: If desk cannot be found
            DeskConnectionError: If connection fails after retries
        """
        self._log(f"🔍 Searching for {self.name}...")

        # Scan for device
        try:
            devices = await BleakScanner.discover(timeout=10.0)
        except BleakError as e:
            raise DeskConnectionError(f"BLE scan failed: {e}") from e

        for d in devices:
            if d.name and self.name.lower() in d.name.lower():
                self.device = d
                break

        if not self.device:
            raise DeskNotFoundError(f"Desk '{self.name}' not found. Is it powered on?")

        self._log(f"✅ Found: {self.device.name}")

        # Try to connect with retries
        last_error = None
        for attempt in range(retries + 1):
            try:
                self._log(f"🔌 Connecting{f' (attempt {attempt + 1})' if attempt > 0 else ''}...")

                self.client = BleakClient(
                    self.device,
                    timeout=timeout,
                    disconnected_callback=self._on_disconnect,
                )
                await self.client.connect()

                if self.client.is_connected:
                    self._connected = True
                    self._log("🔗 Connected!")

                    # Wake up and initialize
                    await self._safe_write(CMD_WAKEUP)
                    await self._safe_start_notify()
                    await self._read_height()
                    return True

            except asyncio.TimeoutError:
                last_error = DeskConnectionError("Connection timed out")
            except BleakError as e:
                last_error = DeskConnectionError(f"BLE error: {e}")

            if attempt < retries:
                self._log("   ⚠️  Retrying...")
                await asyncio.sleep(1)

        raise last_error or DeskConnectionError("Connection failed")

    def _on_disconnect(self, client: BleakClient):
        """Handle unexpected disconnection."""
        was_connected = self._connected
        self._connected = False
        # Only warn if this was truly unexpected
        if was_connected and not self._disconnecting and not self.quiet:
            print("⚠️  Disconnected unexpectedly")

    async def _safe_write(self, cmd: bytearray) -> bool:
        """Safely write command, handling errors gracefully."""
        if not self._connected or not self.client:
            return False
        try:
            await self.client.write_gatt_char(UUID_COMMAND, cmd)
            return True
        except BleakError:
            return False

    async def _safe_start_notify(self):
        """Start notifications with error handling."""
        try:
            await self.client.start_notify(UUID_HEIGHT, self._height_callback)
        except BleakError:
            pass  # Non-critical, we can poll instead

    def _height_callback(self, sender, data: bytearray):
        """Callback for height notifications (handles race conditions)."""
        with suppress(Exception):
            self.current_height, self.current_speed = parse_height_data(data)

    async def _read_height(self) -> int:
        """Read current height with error handling."""
        if not self._connected or not self.client:
            raise DeskCommunicationError("Not connected")
        try:
            data = await self.client.read_gatt_char(UUID_HEIGHT)
            self.current_height, self.current_speed = parse_height_data(data)
            return self.current_height
        except BleakError as e:
            raise DeskCommunicationError(f"Failed to read height: {e}") from e

    async def disconnect(self):
        """Disconnect from the desk gracefully."""
        self._disconnecting = True
        if self.client:
            with suppress(BleakError):
                if self._connected:
                    await self.client.stop_notify(UUID_HEIGHT)
                await self.client.disconnect()
            self._connected = False
            self._log("👋 Disconnected")

    async def get_height(self) -> int:
        """Get current desk height in mm."""
        return await self._read_height()

    async def stop(self):
        """Emergency stop desk movement."""
        await self._safe_write(CMD_STOP)
        self._log("🛑 Stopped")

    async def move_to_height(self, target_mm: int, tolerance_mm: int = 5) -> tuple[int, bool]:
        """
        Move desk to target height in mm with precision control and collision detection.

        Args:
            target_mm: Target height in millimeters
            tolerance_mm: Acceptable error margin

        Returns:
            Tuple of (final_height_mm, collision_detected)

        Raises:
            DeskCommunicationError: If communication fails during movement
        """
        # Clamp target to valid range
        target_mm = max(MIN_HEIGHT_MM, min(MAX_HEIGHT_MM, target_mm))

        try:
            current = await self.get_height()
        except DeskCommunicationError:
            raise

        distance = abs(target_mm - current)
        if distance <= tolerance_mm:
            return current, False  # Already at target

        direction = "up" if target_mm > current else "down"
        cmd = CMD_UP if direction == "up" else CMD_DOWN

        # Stopping distance accounts for momentum (gravity assists downward)
        stopping_distance = 10 if direction == "down" else 8

        self._log(f"📏 {current}mm → {target_mm}mm ({direction})")

        # Collision detection state
        stall_count = 0
        last_height = current
        collision_detected = False

        try:
            while self._connected:
                current = await self._read_height()
                remaining = target_mm - current if direction == "up" else current - target_mm

                # Check if we've reached target
                if remaining <= stopping_distance:
                    break

                # Collision detection: height not changing
                if current == last_height:
                    stall_count += 1
                    if stall_count >= 3:  # 300ms of no movement = collision
                        collision_detected = True
                        self._log(f"⚠️  Collision detected at {current}mm (blocked)")
                        break
                else:
                    stall_count = 0
                    last_height = current

                if not await self._safe_write(cmd):
                    raise DeskCommunicationError("Lost connection during movement")

                await asyncio.sleep(0.1)

            # Stop and settle
            await self._safe_write(CMD_STOP)
            await asyncio.sleep(0.3)

            final = await self._read_height()
            error = abs(final - target_mm)

            if collision_detected:
                self._log(f"🛑 Stopped: {final}mm (collision, {error}mm short)")
            else:
                self._log(f"✅ Done: {final}mm (error: {error}mm)")

            return final, collision_detected

        except DeskCommunicationError:
            # Try to stop before re-raising
            await self._safe_write(CMD_STOP)
            raise

    async def move_by_inches(self, inches: float) -> tuple[int, bool]:
        """
        Move desk by specified inches (positive=up, negative=down).

        Returns:
            Tuple of (final_height_mm, collision_detected)
        """
        current = await self.get_height()
        delta_mm = int(inches * 25.4)
        target = current + delta_mm

        direction = "up" if inches > 0 else "down"
        self._log(f'{"⬆️" if inches > 0 else "⬇️"}  Moving {abs(inches):.1f}" {direction}...')

        return await self.move_to_height(target)

    async def go_to_preset(self, preset: int = 1) -> int:
        """
        Move to a memory preset position (1-4).

        Args:
            preset: Preset number (1-4)

        Returns:
            Final height in mm after movement completes

        Raises:
            ValueError: If preset is not 1-4
            DeskCommunicationError: If communication fails
        """
        if preset not in UUID_MEMORY:
            raise ValueError(f"Preset must be 1-4, got {preset}")

        self._log(f"📍 Moving to preset {preset}...")
        try:
            # Reading the preset characteristic triggers movement
            await self.client.read_gatt_char(UUID_MEMORY[preset])
            # Wait for movement to complete (desk moves autonomously)
            await asyncio.sleep(0.5)
            # Poll until movement stops
            last_height = 0
            stable_count = 0
            while stable_count < 3:
                height = await self._read_height()
                if height == last_height:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_height = height
                await asyncio.sleep(0.3)
            final = await self._read_height()
            self._log(f'✅ At preset {preset}: {final}mm ({final / 25.4:.1f}")')
            return final
        except BleakError as e:
            raise DeskCommunicationError(f"Failed to trigger preset: {e}") from e

    async def save_preset(self, preset: int = 1) -> int:
        """
        Save current height to a memory preset (1-4).

        Args:
            preset: Preset number (1-4)

        Returns:
            Height that was saved in mm

        Raises:
            ValueError: If preset is not 1-4
            DeskCommunicationError: If communication fails
        """
        if preset not in UUID_MEMORY:
            raise ValueError(f"Preset must be 1-4, got {preset}")

        height = await self._read_height()
        self._log(f'💾 Saving preset {preset} at {height}mm ({height / 25.4:.1f}")...')
        try:
            # Writing to the preset characteristic saves current position
            # The desk expects a dummy write (any value)
            await self.client.write_gatt_char(UUID_MEMORY[preset], bytearray([0x00]))
            self._log(f"✅ Preset {preset} saved!")
            return height
        except BleakError as e:
            raise DeskCommunicationError(f"Failed to save preset: {e}") from e
