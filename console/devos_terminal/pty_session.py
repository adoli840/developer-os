from __future__ import annotations

import errno
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PtySession:
    pid: int
    fd: int
    started_at: float

    @classmethod
    def open(cls, project_path: Path, *, columns: int = 120, rows: int = 32) -> "PtySession":
        import pty

        pid, fd = pty.fork()
        if pid == 0:
            try:
                environment = {
                    "HOME": os.getenv("HOME", "/home/opc"),
                    "LANG": os.getenv("LANG", "C.UTF-8"),
                    "LC_ALL": os.getenv("LC_ALL", "C.UTF-8"),
                    "LOGNAME": os.getenv("LOGNAME", "opc"),
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "SHELL": "/bin/bash",
                    "TERM": "xterm-256color",
                    "COLORTERM": "truecolor",
                    "USER": os.getenv("USER", "opc"),
                }
                os.chdir(project_path)
                os.execve("/bin/bash", ["/bin/bash", "-l"], environment)
            except BaseException as error:
                os.write(2, f"Could not start terminal: {error}\r\n".encode("utf-8", "replace"))
                os._exit(127)

        session = cls(pid=pid, fd=fd, started_at=time.monotonic())
        os.set_blocking(fd, False)
        session.resize(columns, rows)
        return session

    def read(self, size: int = 32768) -> bytes:
        try:
            return os.read(self.fd, size)
        except BlockingIOError:
            return b""
        except OSError as error:
            if error.errno == errno.EIO:
                return b""
            raise

    def write(self, data: bytes) -> None:
        if data:
            os.write(self.fd, data)

    def resize(self, columns: int, rows: int) -> None:
        import fcntl
        import struct
        import termios

        dimensions = struct.pack("HHHH", rows, columns, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, dimensions)

    def alive(self) -> bool:
        try:
            return os.waitpid(self.pid, os.WNOHANG)[0] == 0
        except ChildProcessError:
            return False

    def close(self) -> None:
        try:
            os.kill(self.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if not self.alive():
                break
            time.sleep(0.02)
        else:
            try:
                os.kill(self.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self.pid, 0)
            except ChildProcessError:
                pass

        try:
            os.close(self.fd)
        except OSError:
            pass
