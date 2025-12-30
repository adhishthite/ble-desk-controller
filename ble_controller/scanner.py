"""
BLE Device Scanner

Scans for nearby Bluetooth Low Energy devices and displays their information.
"""

import asyncio
from dataclasses import dataclass

from bleak import BleakScanner


@dataclass
class ScannedDevice:
    """Information about a discovered BLE device."""

    name: str | None
    address: str
    rssi: int
    manufacturer_id: int | None = None
    service_uuids: list[str] | None = None

    @property
    def is_desk(self) -> bool:
        """Check if this device appears to be a Linak desk."""
        if self.name and "desk" in self.name.lower():
            return True
        # Check for Linak service UUID
        if self.service_uuids:
            return any("99fa" in uuid.lower() for uuid in self.service_uuids)
        return False


async def scan_devices(
    timeout: float = 10.0,
    filter_desks: bool = False,
) -> list[ScannedDevice]:
    """
    Scan for BLE devices.

    Args:
        timeout: Scan duration in seconds
        filter_desks: If True, only return devices that appear to be desks

    Returns:
        List of discovered devices, sorted by signal strength (strongest first)
    """
    devices: list[ScannedDevice] = []

    discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)

    for address, (device, adv_data) in discovered.items():
        # Extract manufacturer ID if present
        manufacturer_id = None
        if adv_data.manufacturer_data:
            manufacturer_id = list(adv_data.manufacturer_data.keys())[0]

        scanned = ScannedDevice(
            name=device.name,
            address=address,
            rssi=adv_data.rssi,
            manufacturer_id=manufacturer_id,
            service_uuids=adv_data.service_uuids or None,
        )

        if filter_desks and not scanned.is_desk:
            continue

        devices.append(scanned)

    # Sort by signal strength (strongest first)
    devices.sort(key=lambda d: d.rssi, reverse=True)

    return devices


async def find_desk(name_pattern: str = "Desk", timeout: float = 10.0) -> ScannedDevice | None:
    """
    Find a desk by name pattern.

    Args:
        name_pattern: Substring to match in device name (case-insensitive)
        timeout: Scan duration in seconds

    Returns:
        The matching device with strongest signal, or None if not found
    """
    devices = await scan_devices(timeout=timeout)

    for device in devices:
        if device.name and name_pattern.lower() in device.name.lower():
            return device

    return None


def print_devices(devices: list[ScannedDevice]) -> None:
    """Print a formatted table of discovered devices."""
    if not devices:
        print("No devices found.")
        return

    print(f"\n{'Name':<25} | {'Address':<17} | {'RSSI':>8} | Notes")
    print("-" * 70)

    for device in devices:
        name = device.name or "(unknown)"
        if len(name) > 24:
            name = name[:21] + "..."

        notes = []
        if device.is_desk:
            notes.append("DESK")
        if device.manufacturer_id:
            notes.append(f"MFG:0x{device.manufacturer_id:04X}")

        print(f"{name:<25} | {device.address:<17} | {device.rssi:>5} dBm | {', '.join(notes)}")


async def main():
    """Run a BLE scan and display results."""
    print("🔍 Scanning for BLE devices (10 seconds)...\n")

    devices = await scan_devices(timeout=10.0)
    print_devices(devices)

    # Highlight any desks found
    desks = [d for d in devices if d.is_desk]
    if desks:
        print(f"\n✅ Found {len(desks)} desk(s):")
        for desk in desks:
            print(f"   • {desk.name} ({desk.address})")


if __name__ == "__main__":
    asyncio.run(main())
