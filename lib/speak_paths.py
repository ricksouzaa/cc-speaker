"""Where `speak` keeps its files, and the one-time move from the former folders. Stdlib only.

Everything lives in one data root, which `claude plugin uninstall` removes with the plugin (unless --keep-data):
  1. $CLAUDE_PLUGIN_DATA, when set (hooks receive it);
  2. else derived from where the script is: `.../plugins/cache/<catalog>/<plugin>/<version>/...` gives
     `.../plugins/data/<plugin>-<catalog>`;
  3. else `${CLAUDE_CONFIG_DIR:-~/.claude}/plugins/data/speak-cc-speaker`.
Inside: `engine/` (Python environment `.venv`, model, voices), `config/` (choices) and `state/` (sessions, queue).
The XDG variables are read only to find the former folders (`~/.local/share/claude-speak` and the like).
"""
import os
import shutil

FALLBACK_NAME = 'speak-cc-speaker'
OLD_NAME = 'claude-speak'
# (new subfolder, XDG variable, default below HOME) of each former folder
OLD_KINDS = (('engine', 'XDG_DATA_HOME', '.local/share'),
             ('config', 'XDG_CONFIG_HOME', '.config'),
             ('state', 'XDG_STATE_HOME', '.local/state'))


def root(script):
    """The data root for the plugin script at path `script` (see the module text for the order)."""
    given = os.environ.get('CLAUDE_PLUGIN_DATA')
    if given:
        return given
    parts = os.path.abspath(script).split(os.sep)
    for i in range(len(parts) - 4):
        if parts[i] == 'plugins' and parts[i + 1] == 'cache' and all(parts[i + 2:i + 5]):
            catalog, plugin = parts[i + 2], parts[i + 3]
            return os.sep.join(parts[:i] + ['plugins', 'data', '%s-%s' % (plugin, catalog)])
    base = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')
    return os.path.join(base, 'plugins', 'data', FALLBACK_NAME)


def paths(script):
    """(engine, config, state) folders of the plugin script at path `script`."""
    base = root(script)
    return tuple(os.path.join(base, name) for name in ('engine', 'config', 'state'))


def old_folder(kind, name=OLD_NAME):
    """The former folder of `kind` ('engine', 'config' or 'state') named `name`, as XDG or the default places it;
    None when neither exists."""
    for sub, var, default in OLD_KINDS:
        if sub == kind:
            bases = [os.environ.get(var), os.path.join(os.path.expanduser('~'), *default.split('/'))]
            for base in bases:
                if base and os.path.isdir(os.path.join(base, name)):
                    return os.path.join(base, name)
    return None


def move_dir(src, dst):
    """Moves folder `src` to `dst`, which must not exist. True when it moved. Never leaves half a destination."""
    if os.path.lexists(dst):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.rename(src, dst)
        return True
    except OSError:
        pass
    # Another disk: copy, then remove the source. A copy that fails midway leaves a partial `dst`, which this call
    # created (it did not exist above); remove it and keep `src`, or the partial folder would win next time.
    try:
        shutil.copytree(src, dst, symlinks=True)
    except (OSError, shutil.Error):
        shutil.rmtree(dst, ignore_errors=True)
        return False
    shutil.rmtree(src, ignore_errors=True)
    return True


def migrate_old(base):
    """Moves the former folders into the data root `base`, once: only when `base/engine` does not exist yet, and a
    destination that already exists wins. Drops the leftover `state/phone` of the removed phone mode. Returns the
    names ('engine', 'config', 'state') that moved."""
    moved = []
    if os.path.lexists(os.path.join(base, 'engine')):
        return moved
    for kind, _, _ in OLD_KINDS:
        old = old_folder(kind)
        if old and move_dir(old, os.path.join(base, kind)):
            moved.append(kind)
    if 'state' in moved:
        shutil.rmtree(os.path.join(base, 'state', 'phone'), ignore_errors=True)
    return moved
