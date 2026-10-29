"""The part of `speak` that differs by operating system: processes and sessions (Linux reads /proc, macOS runs `ps`).
The rest of the plugin never asks which system it runs on. Stdlib only. Every function returns None, False or []
when the system cannot answer; none raises.

A process start time is kept as text (`started`) so it can sit inside a session key '<pid>-<start>' that matches
[A-Za-z0-9_-]+: Linux gives clock ticks since boot, macOS gives integer epoch seconds. `start_epoch` turns that text
back into epoch seconds from the text alone, without asking the live process (a reused pid does not change it).
"""
import os
import subprocess
import sys
import time

SYSTEM = 'mac' if sys.platform == 'darwin' else 'linux'


def _ps(pid, fields):
    """Output of `ps -o <fields> -p <pid>` (stripped), or None when ps is absent, fails or prints nothing."""
    try:
        out = subprocess.run(['ps', '-o', fields, '-p', str(pid)], capture_output=True, text=True, timeout=5,
                             env={**os.environ, 'LC_ALL': 'C'})
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    text = out.stdout.strip("\n") if out.returncode == 0 else ''
    return text.strip() or None


def _mac_ppid_comm(pid):
    """(ppid, comm) from one `ps -o ppid=,comm=` call; None when unreadable."""
    text = _ps(pid, 'ppid=,comm=')
    if not text:
        return None
    head, _, comm = text.partition(' ')
    try:
        return int(head), comm.strip()
    except ValueError:
        return None


def _stat_fields(pid):
    """Linux: fields of /proc/<pid>/stat after the process name (which may hold spaces and parentheses): field 3 on."""
    try:
        with open('/proc/%d/stat' % pid) as fh:
            return fh.read().rpartition(')')[2].split()
    except (OSError, ValueError):
        return None


def parent(pid):
    """Parent pid of `pid`, or None."""
    if SYSTEM == 'mac':
        found = _mac_ppid_comm(pid)
        return found[0] if found else None
    fields = _stat_fields(pid)
    try:
        return int(fields[1]) if fields else None
    except (ValueError, IndexError):
        return None


def name(pid):
    """Base name of the executable of `pid`, or None."""
    if SYSTEM == 'mac':
        found = _mac_ppid_comm(pid)
        return os.path.basename(found[1]) or None if found else None
    try:
        with open('/proc/%d/comm' % pid) as fh:
            return fh.read().strip() or None
    except (OSError, ValueError):
        return None


def started(pid):
    """Stable text of when `pid` started (Linux: clock ticks since boot; Mac: integer epoch seconds), or None."""
    if SYSTEM == 'mac':
        text = _ps(pid, 'lstart=')
        try:
            return str(int(time.mktime(time.strptime(text, '%a %b %d %H:%M:%S %Y')))) if text else None
        except (ValueError, OverflowError):
            return None
    fields = _stat_fields(pid)
    return fields[19] if fields and len(fields) > 19 else None


def start_epoch(start):
    """Epoch seconds of a start text made by `started`, computed from the text alone; None if it cannot be."""
    try:
        if SYSTEM == 'mac':
            return float(int(start))
        with open('/proc/stat') as fh:
            btime = next(int(line.split()[1]) for line in fh if line.startswith('btime '))
        return btime + int(start) / os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, TypeError, StopIteration):
        return None


def started_at(pid):
    """Seconds since the epoch at which `pid` started, or None."""
    text = started(pid)
    return start_epoch(text) if text is not None else None


def alive(pid):
    """True if a process with this pid exists."""
    if pid <= 0:
        return False
    if SYSTEM == 'mac':
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except (OSError, OverflowError):
            return False
        return True
    return os.path.exists('/proc/%d' % pid)


def argv(pid):
    """Command line of `pid` as a list, or None. Linux splits exactly (NUL separated); Mac only has `ps -o command=`
    text, split on spaces, so an argument holding a space comes apart (a known limit)."""
    if SYSTEM == 'mac':
        text = _ps(pid, 'command=')
        return text.split() if text else None
    try:
        with open('/proc/%d/cmdline' % pid, 'rb') as fh:
            parts = fh.read().split(b'\0')
    except (OSError, ValueError):
        return None
    if parts and parts[-1] == b'':
        parts.pop()
    return [part.decode('utf-8', 'replace') for part in parts] or None


def ancestors(pid):
    """[(pid, name), ...] from `pid` upward to (excluding) pid 1, for `speak check`. A name that cannot be read is
    '?'; when even the parent cannot be read the chain ends there (so a failing `ps` gives [(pid, '?')])."""
    chain = []
    while pid and pid > 1 and len(chain) < 64:
        if SYSTEM == 'mac':
            found = _mac_ppid_comm(pid)
            label, up = (os.path.basename(found[1]) or '?', found[0]) if found else ('?', None)
        else:
            label, up = name(pid) or '?', parent(pid)
        chain.append((pid, label))
        if up is None or up == pid:
            break
        pid = up
    return chain
