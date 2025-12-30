"""
CLI interface for desk control.

Provides command-line tools for scanning BLE devices and controlling the desk.
"""

import asyncio
import sys

from ble_controller.controller import (
    DeskCommunicationError,
    DeskConnectionError,
    DeskController,
    DeskNotFoundError,
)
from ble_controller.scanner import print_devices, scan_devices


async def run_scan():
    """Scan for BLE devices."""
    print("🔍 Scanning for BLE devices (10 seconds)...\n")
    devices = await scan_devices(timeout=10.0)
    print_devices(devices)

    # Highlight any desks found
    desks = [d for d in devices if d.is_desk]
    if desks:
        print(f"\n✅ Found {len(desks)} desk(s):")
        for desk in desks:
            print(f"   • {desk.name} ({desk.address})")
    else:
        print("\n⚠️  No desks found. Make sure your desk is powered on.")


async def run_control(args: list[str]):
    """Run a desk command."""
    desk = DeskController("Desk")

    try:
        await desk.connect()

        if not args:
            # Just show height
            print(f'📏 Height: {desk.current_height}mm ({desk.current_height / 25.4:.1f}")')

        elif args[0] == "height":
            print(f"{desk.current_height}mm")

        elif args[0] == "up":
            inches = float(args[1]) if len(args) > 1 else 1.0
            _, collision = await desk.move_by_inches(inches)
            if collision:
                sys.exit(2)  # Exit code 2 = collision

        elif args[0] == "down":
            inches = float(args[1]) if len(args) > 1 else 1.0
            _, collision = await desk.move_by_inches(-inches)
            if collision:
                sys.exit(2)

        elif args[0] == "goto":
            if len(args) < 2:
                print("Usage: goto <height_mm>")
            else:
                _, collision = await desk.move_to_height(int(args[1]))
                if collision:
                    sys.exit(2)

        elif args[0] == "preset":
            preset = int(args[1]) if len(args) > 1 else 1
            await desk.go_to_preset(preset)

        elif args[0] == "save":
            preset = int(args[1]) if len(args) > 1 else 1
            await desk.save_preset(preset)

        else:
            print(f"Unknown command: {args[0]}")
            print_control_help()

    except DeskNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except DeskConnectionError as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)
    except DeskCommunicationError as e:
        print(f"❌ Communication error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
        await desk.stop()
    finally:
        await desk.disconnect()


def print_control_help():
    """Print help for desk control commands."""
    print(
        """
Usage: desk-control [command] [args]

Commands:
  (no command)     Show current height
  height           Show current height in mm
  up [inches]      Move up by inches (default: 1)
  down [inches]    Move down by inches (default: 1)
  goto <mm>        Move to specific height in mm
  preset [1-4]     Move to preset position
  save [1-4]       Save current position to preset

Examples:
  desk-control                  # Show current height
  desk-control up 3             # Move up 3 inches
  desk-control goto 900         # Move to 900mm
  desk-control preset 1         # Go to preset 1
"""
    )


def main_scan():
    """Entry point for desk-scan command."""
    asyncio.run(run_scan())


def main_control():
    """Entry point for desk-control command."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print_control_help()
        return
    asyncio.run(run_control(sys.argv[1:]))


if __name__ == "__main__":
    main_control()
