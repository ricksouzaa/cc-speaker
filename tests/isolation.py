"""One isolation helper for every test file: the path constants of a loaded module (`bin/speak`, a hook) are moved
together into a temporary root, the environment of the process and of every child loses CLAUDE_* and XDG_* and gets a
temporary HOME, and a guard compares the real data folders before and after the battery (path, mtime, size; the
contents are never read)."""
import os
import pwd
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


ROOTS = real_roots()
BEFORE = snapshot(ROOTS)


def assert_untouched(case):
    changes = differences(BEFORE, snapshot(ROOTS))
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
