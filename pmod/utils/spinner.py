"""Animated terminal spinner with stall watchdog.

Writes to stderr so structured log lines on stdout scroll above it cleanly.
Call ``beat()`` to reset the watchdog timer and optionally update the message;
if the code goes silent for longer than ``timeout_s``, a warning is printed.
"""
from __future__ import annotations

import itertools
import sys
import threading
import time
from contextlib import contextmanager
from typing import Generator

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_CLEAR_WIDTH = 88


class Spinner:
    """Threaded terminal spinner with a built-in stall watchdog.

    Usage (manual)::

        sp = Spinner("Fetching data…").start()
        for ticker in tickers:
            sp.beat(f"Scoring {ticker} [{i}/{n}]")
            process(ticker)
        sp.stop()

    Usage (context manager via :func:`spinning`)::

        with spinning("Fetching data…", timeout_s=30) as sp:
            for ticker in tickers:
                sp.beat(f"Scoring {ticker}")
                process(ticker)
    """

    def __init__(self, message: str = "Working…", timeout_s: float = 20.0) -> None:
        self._msg = message
        self._timeout_s = timeout_s
        self._stop_evt = threading.Event()
        self._heartbeat = time.monotonic()
        self._warned = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    # ── public API ────────────────────────────────────────────────────────

    def beat(self, message: str | None = None) -> None:
        """Reset the stall watchdog; optionally update the displayed message."""
        with self._lock:
            self._heartbeat = time.monotonic()
            self._warned = False
            if message is not None:
                self._msg = message

    def start(self) -> "Spinner":
        self._heartbeat = time.monotonic()
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop_evt.set()
        self._thread.join(timeout=1.0)
        sys.stderr.write(f"\r{' ' * _CLEAR_WIDTH}\r")
        sys.stderr.flush()

    # ── context manager support ───────────────────────────────────────────

    def __enter__(self) -> "Spinner":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ── internal ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        for frame in itertools.cycle(FRAMES):
            if self._stop_evt.is_set():
                break

            with self._lock:
                msg = self._msg
                elapsed = time.monotonic() - self._heartbeat
                already_warned = self._warned

            sys.stderr.write(f"\r  {frame} {msg}  ")
            sys.stderr.flush()

            if elapsed > self._timeout_s and not already_warned:
                with self._lock:
                    self._warned = True
                sys.stderr.write(
                    f"\n  ⚠  no output for {int(elapsed)}s — still waiting…\n"
                )
                sys.stderr.flush()

            time.sleep(0.1)


@contextmanager
def spinning(
    message: str = "Working…",
    timeout_s: float = 20.0,
) -> Generator[Spinner, None, None]:
    """Context manager: show an animated spinner while the block runs.

    Yields the :class:`Spinner` so callers can call ``beat()`` to reset the
    watchdog and update the displayed message mid-block.
    """
    sp = Spinner(message=message, timeout_s=timeout_s)
    sp.start()
    try:
        yield sp
    finally:
        sp.stop()
