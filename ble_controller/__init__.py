"""
BLE Controller - Bluetooth Low Energy device control library.

This package provides tools for scanning and controlling BLE devices,
with specific support for IKEA Idåsen / Linak standing desks.
"""

from ble_controller.controller import (
    MAX_HEIGHT_MM,
    MIN_HEIGHT_MM,
    DeskCommunicationError,
    DeskConnectionError,
    DeskController,
    DeskError,
    DeskNotFoundError,
)

__all__ = [
    # Controller
    "DeskController",
    "DeskError",
    "DeskNotFoundError",
    "DeskConnectionError",
    "DeskCommunicationError",
    "MIN_HEIGHT_MM",
    "MAX_HEIGHT_MM",
]
