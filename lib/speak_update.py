"""`speak update`: asks the `claude` program for the newest version of this plugin and says what changed. Stdlib only.

Runs `claude plugin marketplace update <catalog>` and then `claude plugin update <plugin>@<catalog>`. Catalog and plugin
come from the script's place (`.../plugins/cache/<catalog>/<plugin>/<version>/...`); outside the cache they are the
fixed `cc-speaker` and `speak`. The scope is left to `claude plugin update` (it detects where the plugin is installed).
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys

DEFAULT_CATALOG = 'cc-speaker'
DEFAULT_PLUGIN = 'speak'
TIMEOUT = 120.0  # seconds for each `claude` command; CLAUDE_SPEAK_UPDATE_TIMEOUT overrides it (tests)


def cache_place(script):
    """(catalog, plugin, folder holding the version folders) when `script` lives in the plugin cache, else None."""
    parts = os.path.abspath(os.path.realpath(script)).split(os.sep)
    for i in range(len(parts) - 4):
        if parts[i] == 'plugins' and parts[i + 1] == 'cache' and all(parts[i + 2:i + 5]):
            return parts[i + 2], parts[i + 3], os.sep.join(parts[:i + 4])
    return None


def identity(script):
    """(catalog, plugin name) of this plugin."""
    place = cache_place(script)
    if place:
        return place[0], place[1]
    return DEFAULT_CATALOG, DEFAULT_PLUGIN


def find_claude():
    """The `claude` program: on PATH, else ~/.local/bin/claude; None when there is none."""
    found = shutil.which('claude')
    if found:
        return found
    local = os.path.join(os.path.expanduser('~'), '.local', 'bin', 'claude')
    return local if os.path.isfile(local) and os.access(local, os.X_OK) else None


def version_key(text):
    return tuple(int(n) for n in re.findall(r'\d+', text))


def newest_cached(script):
    """The highest version among the plugin's folders in the cache ('' when not in the cache or none is readable)."""
    place = cache_place(script)
    if not place:
        return ''
    best = ''
    try:
        names = os.listdir(place[2])
    except OSError:
        return ''
    for name in names:
        try:
            with open(os.path.join(place[2], name, '.claude-plugin', 'plugin.json')) as fh:
                found = str(json.load(fh).get('version', ''))
        except (OSError, ValueError):
            continue
        if found and (not best or version_key(found) > version_key(best)):
            best = found
    return best


def run(argv, timeout):
    """(exit code, output) of the program, stdin closed, stderr joined to stdout; the whole process group is killed on
    the deadline (code None)."""
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, errors='replace', start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # the group this call created
        except OSError:
            pass
        out, _ = proc.communicate()
        return None, out or ''
    return proc.returncode, out or ''


def update(script, before):
    """Does the update; prints the result in Portuguese (errors on stderr) and returns the exit code."""
    claude = find_claude()
    if not claude:
        print('voz: não achei o comando claude (nem no PATH nem em ~/.local/bin/claude); atualize pelo terminal: '
              'claude plugin marketplace update cc-speaker && claude plugin update speak@cc-speaker', file=sys.stderr)
        return 1
    try:
        timeout = float(os.environ.get('CLAUDE_SPEAK_UPDATE_TIMEOUT') or TIMEOUT)
    except ValueError:
        timeout = TIMEOUT
    catalog, plugin = identity(script)
    out = ''
    for args in (['plugin', 'marketplace', 'update', catalog], ['plugin', 'update', '%s@%s' % (plugin, catalog)]):
        code, out = run([claude] + args, timeout)
        shown = 'claude ' + ' '.join(args)
        if code is None:
            print('voz: `%s` passou de %d segundos e foi interrompido' % (shown, timeout), file=sys.stderr)
            return 1
        if code != 0:
            print('voz: `%s` falhou (código %d):\n%s' % (shown, code, out.strip()), file=sys.stderr)
            return code
    asked = re.findall(r'(?:\bto|->|→)\s+v?(\d+\.\d+\.\d+[\w.+-]*)', out)
    after = asked[-1].rstrip('.') if asked else newest_cached(script) or before
    if before and after and version_key(after) > version_key(before):
        print('atualizado de %s para %s; rode /reload-plugins ou abra uma sessão nova para valer' % (before, after))
    else:
        print('já está na versão mais nova (%s)' % (before or after or 'desconhecida'))
    return 0
