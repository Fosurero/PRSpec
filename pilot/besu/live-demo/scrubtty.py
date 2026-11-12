#!/usr/bin/env python3
"""Run a command on a pseudo-terminal, redact secret values and tee a transcript.

The live demo shows real output on a recorded screen. Everything the command
prints passes through here first, so an API key can never reach the video or the
transcript even if a library error were to echo one. The transcript is the exact
byte stream shown on screen (after redaction) and is secret-scanned again before
publishing. Usage: scrubtty.py TRANSCRIPT -- command [args...]
"""
import fcntl
import os
import pty
import select
import sys
import termios

SECRET_ENV = ("GEMINI_API_KEY", "MODEL_API_KEY", "GH_TOKEN", "GITHUB_TOKEN")
MASK = b"[REDACTED]"


def _held_tail(buf: bytes, secrets) -> int:
    """Length of the longest buffer suffix that could be the start of a secret."""
    hold = 0
    for s in secrets:
        for k in range(min(len(s) - 1, len(buf)), hold, -1):
            if buf.endswith(s[:k]):
                hold = k
                break
    return hold


def main() -> int:
    sep = sys.argv.index("--")
    transcript, cmd = sys.argv[1], sys.argv[sep + 1:]
    secrets = [os.environ[n].encode() for n in SECRET_ENV if len(os.environ.get(n, "")) >= 8]
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(cmd[0], cmd)
    try:
        size = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        pass
    pending = b""
    with open(transcript, "ab") as log:
        def emit(data: bytes) -> None:
            os.write(sys.stdout.fileno(), data)
            log.write(data)
            log.flush()

        while True:
            ready, _, _ = select.select([fd], [], [], 0.25)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            pending += chunk
            for s in secrets:
                pending = pending.replace(s, MASK)
            hold = _held_tail(pending, secrets)
            out, pending = (pending[:-hold], pending[-hold:]) if hold else (pending, b"")
            if out:
                emit(out)
        for s in secrets:
            pending = pending.replace(s, MASK)
        if pending:
            emit(pending)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
