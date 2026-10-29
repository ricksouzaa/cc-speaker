"""The part of `speak` that differs by operating system: processes and sessions (Linux reads /proc, macOS runs `ps`),
the audio player and the microphone check (Linux: pw-play/paplay/aplay and pw-dump; macOS: afplay and CoreAudio).
The rest of the plugin never asks which system it runs on. Stdlib only. Every function returns None, False or []
when the system cannot answer; none raises.

A process start time is kept as text (`started`) so it can sit inside a session key '<pid>-<start>' that matches
[A-Za-z0-9_-]+: Linux gives clock ticks since boot, macOS gives integer epoch seconds. `start_epoch` turns that text
back into epoch seconds from the text alone, without asking the live process (a reused pid does not change it).
"""
import json
import os
import shutil
import subprocess
import sys
import time

SYSTEM = 'mac' if sys.platform == 'darwin' else 'linux'

RATE = 24000  # Kokoro's output, mono float32
PLAYERS = (['pw-play', '--raw', '--format', 'f32', '--rate', str(RATE), '--channels', '1', '-'],
           ['paplay', '--raw', '--format=float32le', '--rate=%d' % RATE, '--channels=1'],
           ['aplay', '-q', '-f', 'FLOAT_LE', '-r', str(RATE), '-c', '1'])


def _ps(pid, fields):
    """Output of `ps -o <fields> -p <pid>` (stripped), or None when ps is absent, fails or prints nothing."""
    try:
        out = subprocess.run(['ps', '-o', fields, '-p', str(pid)], capture_output=True, text=True, timeout=5,
                             env={**os.environ, 'LC_ALL': 'C'})
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


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


def node(pid):
    """(parent pid, executable base name) of `pid`, or None. On Mac this is one `ps` call, so walking up the
    chain costs one call per level."""
    if SYSTEM == 'mac':
        found = _mac_ppid_comm(pid)
        return (found[0], os.path.basename(found[1]) or None) if found else None
    up, label = parent(pid), name(pid)
    return (up, label) if up is not None and label else None


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
        found = node(pid)
        up, label = (found[0], found[1] or '?') if found else (None, '?')
        chain.append((pid, label))
        if up is None or up == pid:
            break
        pid = up
    return chain


# --- sound and microphone ---------------------------------------------------------------------------------------

def _player_usable(command):
    """True when the player is on PATH and takes raw samples: `pw-play --raw` came with PipeWire 1.1, so an older
    pw-play (1.0.x, Ubuntu 24.04) says 'unrecognized option' and is skipped in favour of paplay or aplay."""
    if not shutil.which(command[0]):
        return False
    if command[0] != 'pw-play':
        return True
    try:
        r = subprocess.run([command[0], '--help'], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return '--raw' in r.stdout + r.stderr


def player():
    """Command line of the audio player to use, or None. Linux: the first of pw-play, paplay, aplay that is usable
    (they read raw samples from stdin). Mac: `['afplay']` (it plays a file, which the caller appends)."""
    if SYSTEM == 'mac':
        return ['afplay'] if shutil.which('afplay') else None
    return next((p for p in PLAYERS if _player_usable(p)), None)


def streams():
    """True when the player reads samples from its stdin (Linux); False when it plays one file at a time (Mac)."""
    return SYSTEM != 'mac'


def recordings(dump):
    """Ids of the audio streams recording from a microphone, in pw-dump's JSON; None when it cannot be read."""
    try:
        nodes = json.loads(dump)
    except ValueError:
        return None
    return {n.get('id') for n in nodes if isinstance(n, dict)
            and ((n.get('info') or {}).get('props') or {}).get('media.class') == 'Stream/Input/Audio'}


def _fourcc(text):
    return int.from_bytes(text.encode('ascii'), 'big')


class _CoreAudio:
    """The few CoreAudio calls needed, through ctypes (the one place that touches the framework). Every method
    raises OSError when CoreAudio answers with an error status."""

    SYSTEM_OBJECT = 1  # kAudioObjectSystemObject
    DEVICES = _fourcc('dev#')  # kAudioHardwarePropertyDevices
    DEFAULT_OUTPUTS = (_fourcc('dOut'), _fourcc('sOut'))  # ...DefaultOutputDevice, ...DefaultSystemOutputDevice
    STREAM_CONFIG = _fourcc('slay')  # kAudioDevicePropertyStreamConfiguration
    RUNNING_SOMEWHERE = _fourcc('gone')  # kAudioDevicePropertyDeviceIsRunningSomewhere
    GLOBAL, INPUT = _fourcc('glob'), _fourcc('inpt')  # kAudioObjectPropertyScopeGlobal, ...ScopeInput
    MAIN = 0  # kAudioObjectPropertyElementMain (Master on older systems: the same value)

    def __init__(self, lib):
        import ctypes
        self.ctypes = ctypes
        self.lib = lib

        class Address(ctypes.Structure):
            _fields_ = [('selector', ctypes.c_uint32), ('scope', ctypes.c_uint32), ('element', ctypes.c_uint32)]
        self.Address = Address

    def _read(self, obj, selector, scope):
        """Raw bytes of a property of an audio object."""
        c = self.ctypes
        addr = self.Address(selector, scope, self.MAIN)
        size = c.c_uint32(0)
        if self.lib.AudioObjectGetPropertyDataSize(obj, c.byref(addr), 0, None, c.byref(size)) != 0:
            raise OSError('AudioObjectGetPropertyDataSize')
        buf = c.create_string_buffer(size.value)
        if self.lib.AudioObjectGetPropertyData(obj, c.byref(addr), 0, None, c.byref(size), buf) != 0:
            raise OSError('AudioObjectGetPropertyData')
        return buf.raw[:size.value]

    def devices(self):
        raw = self._read(self.SYSTEM_OBJECT, self.DEVICES, self.GLOBAL)
        return [int.from_bytes(raw[i:i + 4], sys.byteorder) for i in range(0, len(raw) - 3, 4)]

    def default_outputs(self):
        """Ids of the default output device and of the default system output device."""
        return [int.from_bytes(self._read(self.SYSTEM_OBJECT, selector, self.GLOBAL)[:4], sys.byteorder)
                for selector in self.DEFAULT_OUTPUTS]

    def input_channels(self, dev):
        """Channels of the input scope, summed over the AudioBufferList (a UInt32 count, padded to 8 bytes, then
        16-byte AudioBuffers whose first field is the channel count)."""
        raw = self._read(dev, self.STREAM_CONFIG, self.INPUT)
        count = int.from_bytes(raw[:4], sys.byteorder)
        return sum(int.from_bytes(raw[8 + 16 * i:12 + 16 * i], sys.byteorder) for i in range(count))

    def running(self, dev):
        return int.from_bytes(self._read(dev, self.RUNNING_SOMEWHERE, self.GLOBAL)[:4], sys.byteorder) != 0


_core = None  # the loaded CoreAudio wrapper (the CDLL and the Address class), made once


def _coreaudio():
    """The CoreAudio wrapper, or None when this is not a Mac or the framework does not load. Never attempted on
    another system."""
    global _core
    if sys.platform != 'darwin':
        return None
    if _core is None:
        try:
            import ctypes
            lib = ctypes.CDLL('/System/Library/Frameworks/CoreAudio.framework/CoreAudio')
            for fn in (lib.AudioObjectGetPropertyDataSize, lib.AudioObjectGetPropertyData):
                fn.restype = ctypes.c_int32  # OSStatus
            _core = _CoreAudio(lib)
        except (OSError, AttributeError, ImportError):
            return None
    return _core


def _mac_mic_busy():
    """True when an input device is running, False when none is, None when it cannot be told.

    `DeviceIsRunningSomewhere` is true for the whole device, so on a headset, AirPods or a monitor with a microphone
    (input and output in one device) our own `afplay` would make it look like a recording. The default output
    devices are therefore left out. Known limit: dictating into the microphone of the same device the voice plays
    on does not cut the speech on the Mac. A device that errors (aggregate or virtual) is skipped."""
    try:
        core = _coreaudio()
        if core is None:
            return None
        ours = set(core.default_outputs())
        busy = False
        for dev in core.devices():
            if dev in ours:
                continue
            try:
                busy = busy or (core.input_channels(dev) > 0 and core.running(dev))
            except Exception:
                continue
        return busy
    except Exception:  # whatever CoreAudio or the wrapper does, the answer is "cannot tell"
        return None


def notice_uv():
    """How to get the uv, in words for this system."""
    if SYSTEM == 'mac':
        return 'brew install uv, ou o instalador de https://docs.astral.sh/uv/'
    return 'https://docs.astral.sh/uv/'


def player_names():
    """The audio players this system looks for, for a message."""
    return 'afplay' if SYSTEM == 'mac' else 'pw-play, paplay ou aplay'


def recordings_now():
    """Linux: ids of the streams recording right now (from `pw-dump`), or None when it cannot be read. Mac: the set
    {'input'} when an input device is running, an empty set when none is, None when it cannot be read."""
    if SYSTEM == 'mac':
        busy = _mac_mic_busy()
        return None if busy is None else ({'input'} if busy else set())
    try:
        return recordings(subprocess.run(['pw-dump'], capture_output=True, timeout=2).stdout)
    except (OSError, subprocess.SubprocessError):
        return None


def mic_busy():
    """True when something is recording from a microphone, False when nothing is, None when it cannot be told."""
    found = recordings_now()
    return None if found is None else bool(found)
