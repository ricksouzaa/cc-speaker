"""Where `speak` keeps its files, and the one-time move from the former folders. Stdlib only.

Everything lives in one data root, which `claude plugin uninstall` removes with the plugin (unless --keep-data):
  1. $CLAUDE_SPEAK_DATA, when set (the session hook exports it to the shell commands of the session, so another
     plugin's CLAUDE_PLUGIN_DATA in that shell does not win), else $CLAUDE_PLUGIN_DATA (hooks receive it);
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
    given = os.environ.get('CLAUDE_SPEAK_DATA') or os.environ.get('CLAUDE_PLUGIN_DATA')
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
    """Moves folder `src` to `dst`, which must not exist. True when it moved. Never leaves half a destination and never
    deletes a `dst` it did not create: another session may have moved its own in meanwhile (the lock is not held)."""
    if os.path.lexists(dst):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.rename(src, dst)
        return True
    except OSError:
        pass
    if not os.path.isdir(src) or os.path.lexists(dst):
        return False  # src gone or dst appeared: the other process won; delete nothing
    # Another disk: copy into a temporary sibling that only this process owns, rename it into place on success.
    part = '%s.part-%d' % (dst, os.getpid())
    try:
        shutil.copytree(src, part, symlinks=True)
        if os.path.lexists(dst):
            raise OSError('destino apareceu')
        os.rename(part, dst)
    except (OSError, shutil.Error):
        return False
    finally:
        shutil.rmtree(part, ignore_errors=True)  # whatever stopped the copy (even an unexpected error): no half copy stays
    shutil.rmtree(src, ignore_errors=True)
    return True


def migrate_old(base):
    """Moves each former folder (engine, config, state) into the data root `base`, independently: a kind moves only
    when its destination does not exist yet (the new one wins and the old folder stays untouched), so a kind that failed
    once is retried. Drops the leftover `state/phone` of the removed phone mode. Returns the names that moved."""
    moved = []
    for kind, _, _ in OLD_KINDS:
        old = old_folder(kind)
        if old and move_dir(old, os.path.join(base, kind)):
            moved.append(kind)
    if 'state' in moved:
        shutil.rmtree(os.path.join(base, 'state', 'phone'), ignore_errors=True)
    return moved


def plugin_version(script):
    """The version in the `.claude-plugin/plugin.json` beside the plugin script at path `script` ('' when unreadable)."""
    import json
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(script))), '.claude-plugin',
                               'plugin.json')) as fh:
            return str(json.load(fh).get('version', ''))
    except (OSError, ValueError):
        return ''
