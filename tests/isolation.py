"""One isolation helper for every test file: the path constants of a loaded module (`bin/speak`, a hook) are moved
together into a temporary root, the environment of the process and of every child loses CLAUDE_* and XDG_* and gets a
temporary HOME, and a guard compares the real data folders before and after the battery (path, mtime, size; the
contents are never read)."""
import os
import pwd
import re
import shlex
import subprocess
import sys
import tempfile
from unittest import mock

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, 'lib'))
import speak_paths  # noqa: E402

DATA_PARTS = ('.claude', 'plugins', 'data', 'speak-cc-speaker')  # the data root below HOME when nothing else decides
PATH_VARIABLES = ('CLAUDE_PLUGIN_DATA', 'CLAUDE_SPEAK_DATA', 'CLAUDE_CONFIG_DIR')
PREFIXES = ('CLAUDE_', 'XDG_')
SAFE_PATH = '/usr/bin:/bin'

# What was in the environment when the battery started, before any test patched anything.
START_ENV_LEAK = [name for name in PATH_VARIABLES if os.environ.get(name)]


def real_roots():
    """The folders no test may touch: the data root as the plugin would resolve it, its default place, and the three
    former folders. Computed from the account's real home, not from $HOME."""
    home = pwd.getpwuid(os.getuid()).pw_dir
    roots = {speak_paths.root(os.path.join(PROJECT, 'bin', 'speak')), os.path.join(home, *DATA_PARTS)}
    for _, _, default in speak_paths.OLD_KINDS:
        roots.add(os.path.join(home, *default.split('/'), speak_paths.OLD_NAME))
    return sorted(roots)


def snapshot(roots):
    """{path: (mtime_ns, size)} of each root and everything under it; a root that does not exist adds nothing."""
    seen = {}
    for root in roots:
        if not os.path.lexists(root):
            continue
        todo = [root]
        while todo:
            path = todo.pop()
            try:
                st = os.lstat(path)
            except OSError:
                continue
            seen[path] = (st.st_mtime_ns, st.st_size)
            if os.path.isdir(path) and not os.path.islink(path):
                try:
                    todo.extend(os.path.join(path, name) for name in os.listdir(path))
                except OSError:
                    pass
    return seen


def differences(before, after):
    """Human lines for what was created, changed or deleted between two snapshots."""
    lines = ['criado: %s' % p for p in sorted(after.keys() - before.keys())]
    lines += ['apagado: %s' % p for p in sorted(before.keys() - after.keys())]
    lines += ['mudado: %s' % p for p in sorted(p for p in before.keys() & after.keys() if before[p] != after[p])]
    return lines


# What a real `speak` process (a player, a `say`) that is not ours writes in the real folders while it speaks: the
# queue, its lock, the speech owner and pid, the session files (pruned), the error log, the microphone mark. These
# names count as noise only below a `state` folder (or the former `claude-speak` state folder) and only while such a
# process is alive; everything else (engine, config, install files) is always reported.
SPEECH_NAMES = ('queue', 'queue.lock', 'speech.pid', 'speech.owner', 'sessions', 'error.log', 'mic-seen')
SPEECH_SUBCOMMANDS = ('_play', 'say')


def is_speech_noise(path):
    """True when `path` is something a real speaking process may write (see SPEECH_NAMES), directories above included."""
    parts = path.split(os.sep)
    if parts[-1] == 'state' and len(parts) > 1 and parts[-2] == speak_paths_dirname():
        return True
    if parts[-1] == 'claude-speak' and len(parts) > 1 and parts[-2] == 'state':
        return True
    for i, part in enumerate(parts):
        if i and part in SPEECH_NAMES and parts[i - 1] in ('state', 'claude-speak'):
            return True
    return False


def speak_paths_dirname():
    return DATA_PARTS[-1]


def processes():
    """[(pid, ppid, argv)] of every process, from `ps` (the same on Linux and macOS); [] when `ps` is not usable."""
    try:
        out = subprocess.run(['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        bits = line.split(None, 2)
        if len(bits) == 3 and bits[0].isdigit() and bits[1].isdigit():
            try:
                argv = shlex.split(bits[2])
            except ValueError:
                argv = bits[2].split()
            found.append((int(bits[0]), int(bits[1]), argv))
    return found


def _home_of(pid):
    """HOME in the process's environment; None when it cannot be read (then the process is not trusted as real)."""
    try:
        with open('/proc/%d/environ' % pid, 'rb') as fh:
            for item in fh.read().split(b'\0'):
                if item.startswith(b'HOME='):
                    return item[5:].decode(errors='replace')
    except OSError:
        pass
    return None


def real_speech_pids(procs=None, me=None, home_of=_home_of):
    """Pids of real `speak _play`/`speak say` processes: not descendants of `me` (the battery) and with the account's
    real HOME (a child of a test has a temporary one, even when orphaned). Where /proc does not exist (macOS) the HOME
    check cannot be made and the process counts when it is not a descendant."""
    procs = processes() if procs is None else procs
    me = os.getpid() if me is None else me
    parent = {pid: ppid for pid, ppid, _ in procs}
    real_home = pwd.getpwuid(os.getuid()).pw_dir
    out = set()
    for pid, _, argv in procs:
        if not any(os.path.basename(a) == 'speak' and i + 1 < len(argv) and argv[i + 1] in SPEECH_SUBCOMMANDS
                   for i, a in enumerate(argv)):
            continue
        up, hops = pid, 0
        while up and hops < 200 and up != me:
            up, hops = parent.get(up, 0), hops + 1
        if up == me:
            continue
        if os.path.isdir('/proc/self') and home_of(pid) != real_home:
            continue
        out.add(pid)
    return out


def real_claude_pids(procs=None, me=None):
    """Pids of Claude Code processes (`claude` in the first two words of the command line) that are not descendants of
    `me` (the battery): real sessions, whose end-of-reply hook writes `state/last/<key>` while the battery runs."""
    procs = processes() if procs is None else procs
    me = os.getpid() if me is None else me
    parent = {pid: ppid for pid, ppid, _ in procs}
    out = set()
    for pid, _, argv in procs:
        if not any(os.path.basename(a) == 'claude' for a in argv[:2]):
            continue
        up, hops = pid, 0
        while up and hops < 200 and up != me:
            up, hops = parent.get(up, 0), hops + 1
        if up != me:
            out.add(pid)
    return out


def is_live_last(path, claude_pids):
    """True for `state/last` itself or `state/last/<pid>-<start>` when <pid> is a live real Claude Code process: the
    last reply of a real session, written by its own hook (`speak say -`). Any other name below it is not noise."""
    parts = path.split(os.sep)
    if parts[-1] == 'last' and len(parts) > 1 and parts[-2] == 'state':
        return bool(claude_pids)
    if len(parts) > 2 and parts[-2] == 'last' and parts[-3] == 'state':
        match = re.fullmatch(r'(\d+)-\d+', parts[-1])
        return bool(match) and int(match.group(1)) in claude_pids
    return False


ROOTS = real_roots()
BEFORE = snapshot(ROOTS)
SPEECH_BEFORE = real_speech_pids()  # alive when the battery started, so surely not started by it


def assert_untouched(case, speech_after=None, speech_before=None, claude_pids=None):
    """No change under the real folders, except the noise of a real speaking process that was alive at the start or is
    alive at the end of the battery (checked here); with none alive, every change is reported. The last reply of a
    live real Claude Code session (`state/last/<key>`) is always noise."""
    after = real_speech_pids() if speech_after is None else speech_after
    before = SPEECH_BEFORE if speech_before is None else speech_before
    changes = differences(BEFORE, snapshot(ROOTS))
    if before or after:
        changes = [c for c in changes if not is_speech_noise(c.split(': ', 1)[1])]
    if changes:
        pids = real_claude_pids() if claude_pids is None else claude_pids
        changes = [c for c in changes if not is_live_last(c.split(': ', 1)[1], pids)]
    case.assertEqual(changes, [], 'a bateria mexeu na pasta real:\n' + '\n'.join(changes))


def clean_env(home, **extra):
    """The environment for a child process: temporary HOME, a minimal PATH, no CLAUDE_* and no XDG_*."""
    env = {'HOME': home, 'PATH': SAFE_PATH}
    env.update(extra)
    return env


def scrub_environ(case, home):
    """Pins HOME to `home` and drops CLAUDE_* and XDG_* from os.environ until the test's cleanup, so that the code in
    process and every child that inherits the environment can only look inside `home`."""
    patch = mock.patch.dict(os.environ, {'HOME': home})
    patch.start()
    case.addCleanup(patch.stop)
    for name in [n for n in os.environ if n.startswith(PREFIXES)]:
        del os.environ[name]


def data_dir(home, *sub):
    """A path inside the plugin's data root below `home` (sub: 'engine', 'config' or 'state', then names)."""
    return os.path.join(home, *DATA_PARTS, *sub)


_ORIGINAL = {}  # module name -> ({kind: original folder}, {constant: original value}), taken when first seen
KINDS = {'DATA': ('engine',), 'CONF': ('config',), 'STATE': ('state',), 'ROOT': ()}  # constant -> path below the root


def _under(value, prefix):
    return value == prefix or value.startswith(prefix + os.sep)


def _original(module):
    if module.__name__ not in _ORIGINAL:
        bases = {name: getattr(module, name) for name in KINDS if hasattr(module, name)}
        consts = {name: value for name, value in vars(module).items()
                  if name.isupper() and isinstance(value, str) and name not in bases
                  and any(_under(value, base) for base in bases.values())}
        _ORIGINAL[module.__name__] = (bases, {**bases, **consts})
    return _ORIGINAL[module.__name__]


def _moved(module, root):
    """{constant: new value} for every path constant of `module` that lives under one of its folders, plus HOME."""
    bases, consts = _original(module)
    new = {name: data_dir(root, *KINDS[name]) for name in bases}
    out = {}
    for name, value in consts.items():
        for base_name, base in bases.items():
            if _under(value, base):
                out[name] = new[base_name] + value[len(base):]
                break
    if hasattr(module, 'HOME'):
        out['HOME'] = root
    return out


def pin_module(module, root):
    """Moves the module's path constants into `root` for good (the caller removes `root` at the end of the module).
    Threads that outlive a test then read the temporary folder, never the real one."""
    for name, value in _moved(module, root).items():
        setattr(module, name, value)


def isolate(case, module, root):
    """For one test: HOME and the environment as `scrub_environ` says, and every path constant of `module` moved
    into `root`, all undone at the test's cleanup. Returns {constant: new value}."""
    scrub_environ(case, root)
    moved = _moved(module, root)
    for name, value in moved.items():
        patcher = mock.patch.object(module, name, value)
        patcher.start()
        case.addCleanup(patcher.stop)
    return moved


def module_root():
    """A temporary root for the whole test module; returns (path, remover)."""
    tmp = tempfile.TemporaryDirectory()
    return tmp.name, tmp.cleanup
