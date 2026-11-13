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
import threading
import time
from unittest import mock

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT, 'lib'))
import speak_paths  # noqa: E402

DATA_PARTS = ('.claude', 'plugins', 'data', 'speak-cc-speaker')  # the data root below HOME when nothing else decides
PATH_VARIABLES = ('CLAUDE_PLUGIN_DATA', 'CLAUDE_SPEAK_DATA', 'CLAUDE_CONFIG_DIR')
PREFIXES = ('CLAUDE_', 'XDG_')
SAFE_PATH = '/usr/bin:/bin'
_POPEN = subprocess.Popen  # kept from the start: a test that patches subprocess.Popen or run must not see the speech watch's `ps`

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
# queue, its lock, the speech owner and pid, the session files (pruned), the error log, the microphone mark and the
# marker of a speech that pauses itself (`soft-<pid>`, made when it starts and dropped when it ends). These names
# count as noise only below a `state` folder (or the former `claude-speak` state folder) and only while such a
# process is alive; everything else (engine, config, install files) is always reported.
SPEECH_NAMES = ('queue', 'queue.lock', 'speech.pid', 'speech.owner', 'speech.json', 'sessions', 'error.log', 'mic-seen')
SOFT_MARKER = re.compile(r'soft-\d+')  # speak.soft_marker(pid): a file directly in the state folder
SPEECH_SUBCOMMANDS = ('_play', 'say')


def is_state_folder(path):
    """True for the `state` folder itself (the one of the data root, or the former `state/claude-speak`)."""
    parts = path.split(os.sep)
    if parts[-1] == 'state' and len(parts) > 1 and parts[-2] == speak_paths_dirname():
        return True
    return parts[-1] == 'claude-speak' and len(parts) > 1 and parts[-2] == 'state'


def is_speech_noise(path):
    """True when `path` is something a real speaking process may write (see SPEECH_NAMES), directories above included."""
    parts = path.split(os.sep)
    if is_state_folder(path):
        return True
    if SOFT_MARKER.fullmatch(parts[-1]) and is_state_folder(os.path.dirname(path)):
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
        with _POPEN(['ps', '-axo', 'pid=,ppid=,command='], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True) as proc:
            out = proc.communicate(timeout=10)[0]
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


def own_claude_pids(procs=None, me=None):
    """Pids of the Claude Code processes above `me` (the battery): the session that launched it. A child `speak` with
    no forced session finds that very key by itself (speak.current_session), so the files of that session (its
    choices, its last reply) are what a leak of the battery would write."""
    procs = processes() if procs is None else procs
    me = os.getpid() if me is None else me
    parent = {pid: ppid for pid, ppid, _ in procs}
    argv = {pid: args for pid, _, args in procs}
    out = set()
    up, hops = parent.get(me, 0), 0
    while up and hops < 200:
        if any(os.path.basename(a) == 'claude' for a in argv.get(up, [])[:2]):
            out.add(up)
        up, hops = parent.get(up, 0), hops + 1
    return out


def _is_live_file(path, folder, claude_pids):
    """True for `state/<folder>` itself or `state/<folder>/<pid>-<start>` when <pid> is a live real Claude Code
    process. Any other name below the folder is not noise."""
    parts = path.split(os.sep)
    if parts[-1] == folder and len(parts) > 1 and parts[-2] == 'state':
        return bool(claude_pids)
    if len(parts) > 2 and parts[-2] == folder and parts[-3] == 'state':
        match = re.fullmatch(r'(\d+)-\d+', parts[-1])
        return bool(match) and int(match.group(1)) in claude_pids
    return False


def is_live_last(path, claude_pids):
    """True for `state/last` itself or `state/last/<pid>-<start>` when <pid> is a live real Claude Code process: the
    last reply of a real session, written by its own hook (`speak say -`). Any other name below it is not noise.
    The caller leaves the session that launched the battery out of `claude_pids` (see own_claude_pids)."""
    return _is_live_file(path, 'last', claude_pids)


def is_live_session(path, claude_pids):
    """True for `state/sessions` itself or `state/sessions/<pid>-<start>` when <pid> is a live real Claude Code
    process: the choices of a real session, written by its own hooks with no speech at all (`speak rule` at the start
    of a conversation and after a compaction, `speak told` at a new message). Any other name below it is not noise.
    The caller leaves the session that launched the battery out of `claude_pids` (see own_claude_pids)."""
    return _is_live_file(path, 'sessions', claude_pids)


def _path(change):
    """The path of a line of `differences`."""
    return change.split(': ', 1)[1]


class SpeechWatch:
    """Remembers every real speech process seen while the battery runs. A speech of another session that starts and
    ends in the middle of the battery is alive neither at its start nor at its end, but it writes the queue, the lock
    and the speech files all the same; looking only at the two ends misses it. A look every `every` seconds in a daemon
    thread (named `speech-watch`, ignored by the thread checks) gathers the pids; a speech shorter than the interval
    can still slip through, which only leaves the old behaviour for it."""

    def __init__(self, finder=None, every=0.5):
        self.finder = finder or real_speech_pids
        self.every = every
        self.seen = set()
        self.stopping = threading.Event()
        self.thread = None

    def look(self):
        """One look: adds the pids alive now; returns the set seen so far."""
        self.seen |= set(self.finder())
        return self.seen

    def start(self):
        self.look()
        self.thread = threading.Thread(target=self._loop, name='speech-watch', daemon=True)
        self.thread.start()
        return self

    def _loop(self):
        while not self.stopping.wait(self.every):
            try:
                self.look()
            except Exception:
                pass  # a failing look is only a missed look

    def stop(self):
        self.stopping.set()


ROOTS = real_roots()
BEFORE = snapshot(ROOTS)
SPEECH_BEFORE = real_speech_pids()  # alive when the battery started, so surely not started by it
WATCH = SpeechWatch().start()  # every real speech seen from now on, to the end of the battery


def assert_untouched(case, speech_after=None, speech_before=None, claude_pids=None, speech_seen=None, own_pids=None):
    """No change under the real folders, except the noise of a real speaking process that was alive at the start, at
    any look of the watch during the battery, or at the end (checked here); with none, every change is reported. The
    last reply (`state/last/<key>`) and the choices (`state/sessions/<key>`) of a live real Claude Code session are
    always noise, except those of the session that launched the battery; with a file of those created or changed,
    the `state` folder it lives in is noise too: the hooks of that session write both through a temporary file in
    `state` (speak.write_atomic), which changes the folder even when no speech process was seen (voice off or quiet
    in that session).
    Why a real leak is still caught: the noise is only the speech names (queue, lock, speech files, session files,
    error log, microphone mark) below a `state` folder; whatever else the battery touches (engine, config, install
    files, the `all` mark, anything outside those names) is reported even while a real speech is playing, and the
    names themselves are reported on every run where no real speech was seen at all, except the two files named
    after a live real Claude Code session. The two files of the session that launched the battery are what a child
    `speak` with no forced session would write (`speak say -` saves the last reply even with the voice off or
    quiet), so they are never forgiven that way: the last reply of that session is reported even while a real speech
    plays. The price: when that very session ends a turn, takes a new message or compacts while the battery runs
    (in the background, or run by an agent of that session), the guard reports its files; run the battery again."""
    after = real_speech_pids() if speech_after is None else speech_after
    before = SPEECH_BEFORE if speech_before is None else speech_before
    seen = WATCH.look() if speech_seen is None else speech_seen
    changes = differences(BEFORE, snapshot(ROOTS))
    if before or after or seen:
        changes = [c for c in changes if not is_speech_noise(_path(c))]
    if changes:
        pids = real_claude_pids() if claude_pids is None else claude_pids
        others = set(pids) - set(own_claude_pids() if own_pids is None else own_pids)
        noise = [c for c in changes if is_live_last(_path(c), others) or is_live_session(_path(c), others)]
        # Only a file of a live session, created or changed (not the `last` or `sessions` folder alone, nor a file that
        # only went away), explains a change of the `state` folder it lives in: its temporary file was there.
        written = {os.path.dirname(os.path.dirname(_path(c))) for c in noise
                   if not c.startswith('apagado: ') and os.path.basename(os.path.dirname(_path(c))) in ('last', 'sessions')}
        changes = [c for c in changes if c not in noise
                   and not (c.startswith('mudado: ') and _path(c) in written and is_state_folder(_path(c)))]
    case.assertEqual(changes, [], 'a bateria mexeu na pasta real:\n' + '\n'.join(changes))


# Daemon threads the code under test starts and ends by itself: a test must leave none of them alive.
WORKERS = ('synthesize_ahead.<locals>.work', 'StreamPlayer.bounded.<locals>.work')


def live_workers():
    """The alive threads that run one of WORKERS."""
    import threading
    return [th for th in threading.enumerate()
            if th.is_alive() and getattr(getattr(th, '_target', None), '__qualname__', '') in WORKERS]


def assert_no_workers(case, wait=3.0):
    """Fails `case` if a worker thread is still alive after `wait` seconds (they end as soon as their call returns)."""
    import time
    end = time.monotonic() + wait
    while live_workers() and time.monotonic() < end:
        time.sleep(0.01)
    case.assertEqual([th.name for th in live_workers()], [], 'a worker thread outlived its test')


def guard_workers(case):
    """Checks at the test's cleanup (add it first in setUp: cleanups run last-in first-out) that no worker is alive."""
    case.addCleanup(assert_no_workers, case)


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
