"""
Event bus initialization using asyncio-signal-bus.
Enables decoupled, asynchronous event-driven architecture across the application.
"""

from asyncio_signal_bus import SignalBus

# Global application signal bus
bus = SignalBus()
