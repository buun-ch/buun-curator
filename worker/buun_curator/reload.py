"""
Hot reload support for Temporal Worker.

Uses watchfiles (Rust-based) to detect file changes and restarts
the worker subprocess. Based on uvicorn's ChangeReload supervisor.

This module is derived from uvicorn (https://github.com/encode/uvicorn),
which is licensed under the BSD 3-Clause License:

    Copyright © 2017-present, Encode OSS Ltd. All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.
    3. Neither the name of the copyright holder nor the names of its contributors
       may be used to endorse or promote products derived from this software
       without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
    LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.
"""

import logging
import multiprocessing
import os
import signal
import sys
from collections.abc import Callable
from multiprocessing.context import SpawnProcess
from pathlib import Path
from types import FrameType

from watchfiles import watch

logger = logging.getLogger("buun-curator")

# Signals to handle for graceful shutdown
HANDLED_SIGNALS = (signal.SIGINT, signal.SIGTERM)

# Spawn context for creating subprocesses
spawn = multiprocessing.get_context("spawn")


class ChangeReload:
    """
    File change watcher that restarts worker subprocess on changes.

    Based on uvicorn's ChangeReload but simplified for Temporal Worker.
    Uses watchfiles for efficient file system monitoring.
    """

    def __init__(
        self,
        target: Callable[[], None],
        reload_dirs: list[str | Path],
        reload_includes: list[str] | None = None,
        reload_excludes: list[str] | None = None,
        reload_delay: float = 0.25,
    ) -> None:
        """
        Initialize the change reloader.

        Parameters
        ----------
        target : Callable[[], None]
            Function to run in subprocess (the worker).
        reload_dirs : list[str | Path]
            Directories to watch for changes.
        reload_includes : list[str] | None, optional
            Glob patterns to include (default: ["*.py"]).
        reload_excludes : list[str] | None, optional
            Glob patterns to exclude (default: [".*", ".py[cod]", "__pycache__"]).
        reload_delay : float, optional
            Debounce delay in seconds (default: 0.25).
        """
        self.target = target
        self.reload_dirs = [Path(d) for d in reload_dirs]
        self.reload_includes = reload_includes or ["*.py"]
        self.reload_excludes = reload_excludes or [".*", ".py[cod]", "__pycache__", ".venv"]
        self.reload_delay = reload_delay
        self.process: SpawnProcess | None = None
        self.should_exit = False

    @property
    def pid(self) -> int:
        """Get current process ID."""
        return os.getpid()

    def signal_handler(self, _sig: int, _frame: FrameType | None) -> None:
        """Handle shutdown signals."""
        self.should_exit = True

    def run(self) -> None:
        """Run the reloader main loop."""
        self.startup()
        self.watch_loop()
        self.shutdown()

    def startup(self) -> None:
        """Start the reloader and initial worker subprocess."""
        dirs_str = ", ".join(str(d) for d in self.reload_dirs)
        logger.info(f"Started reloader process [{self.pid}] watching: {dirs_str}")

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        self.process = _get_subprocess(self.target)
        self.process.start()

    def watch_loop(self) -> None:
        """Watch for file changes and restart worker when detected."""

        def watch_filter(_change_type: object, path: str) -> bool:
            return _should_watch_path(path, self.reload_includes, self.reload_excludes)

        for changes in watch(
            *self.reload_dirs,
            watch_filter=watch_filter,
            debounce=int(self.reload_delay * 1000),
            stop_event=None,
            yield_on_timeout=True,
        ):
            if self.should_exit:
                break

            if changes:
                for _change_type, path in changes:
                    logger.info(f"Detected change: {path}")

                self.restart()

    def restart(self) -> None:
        """Restart the worker subprocess."""
        logger.info("Restarting worker...")

        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()

        self.process = _get_subprocess(self.target)
        self.process.start()
        logger.info(f"Worker restarted [{self.process.pid}]")

    def shutdown(self) -> None:
        """Shutdown the reloader and worker subprocess."""
        logger.info(f"Stopping reloader process [{self.pid}]")

        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.kill()
                self.process.join()


def _should_watch_path(
    path: str,
    includes: list[str],
    excludes: list[str],
) -> bool:
    """
    Check if a file path should trigger a reload.

    Parameters
    ----------
    path : str
        File path to check.
    includes : list[str]
        Glob patterns to include (e.g., ["*.py"]).
    excludes : list[str]
        Glob patterns to exclude (e.g., [".*", "__pycache__"]).

    Returns
    -------
    bool
        True if the file should trigger a reload.
    """
    p = Path(path)
    name = p.name

    for pattern in excludes:
        if p.match(pattern) or name.startswith("."):
            return False

    return any(p.match(pattern) for pattern in includes)


def _get_subprocess(target: Callable[[], None]) -> SpawnProcess:
    """
    Create a new subprocess for the worker.

    Parameters
    ----------
    target : Callable[[], None]
        Function to run in subprocess.

    Returns
    -------
    SpawnProcess
        New subprocess ready to start.
    """
    return spawn.Process(target=_subprocess_started, args=(target,))


def _subprocess_started(target: Callable[[], None]) -> None:
    """
    Entry point for worker subprocess.

    Parameters
    ----------
    target : Callable[[], None]
        Function to run.
    """
    # Re-open stdin if available
    try:
        stdin_fileno = sys.stdin.fileno()
        sys.stdin = os.fdopen(stdin_fileno)
    except OSError:
        pass

    target()
