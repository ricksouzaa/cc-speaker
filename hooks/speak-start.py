#!/usr/bin/env python3
"""SessionStart hook: prints the spoken-reply rule (`speak rule`), which Claude Code puts in the context, plus a notice
when the engine or an audio player is missing. Without the engine it also starts `speak install` in the background,
detached from the session, once at a time (CLAUDE_SPEAK_AUTOINSTALL=0 turns that off). Fail-open: exits 0 in every case."""
import fcntl
import os
import shutil
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')
STATE = os.path.join(os.environ.get('XDG_STATE_HOME') or os.path.join(os.path.expanduser('~'), '.local', 'state'),
                     'claude-speak')
INSTALL_LOG = os.path.join(STATE, 'install.log')
INSTALL_LOCK = os.path.join(STATE, 'install.lock')  # flock'ed by the install itself, for as long as it runs
INSTALL_FAILED = os.path.join(STATE, 'install.failed')  # written by `speak install` when it fails
NOTICE = {
    'installing': 'speak: o motor de voz está sendo instalado em segundo plano (cerca de 350 MB, sem sudo); a voz '
                  'começa sozinha quando terminar. Avise o humano na primeira resposta, em uma frase.',
    'no-uv': 'speak: o motor de voz não está instalado e falta o uv, que o instala. Na primeira resposta, diga ao '
             'humano como instalar o uv (https://docs.astral.sh/uv/); depois, `/speak install`.',
    'failed': 'speak: a última instalação do motor de voz falhou; o registro está em %s. Avise o humano na primeira '
              'resposta; `/speak install` tenta de novo.' % INSTALL_LOG,
    'player': 'speak: nenhum tocador de áudio (pw-play, paplay ou aplay) foi encontrado; sem ele a voz não toca. '
              'Avise o humano na primeira resposta.',
}


def run(*args):
    return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, timeout=10)


def start_install():
    """Starts `speak install` detached from the session, unless one is running, the last one failed or the uv is
    missing. Returns the NOTICE key to tell Claude."""
    if os.environ.get('CLAUDE_SPEAK_AUTOINSTALL') == '0':
        return None
    uv = shutil.which('uv') or os.path.join(os.path.expanduser('~'), '.local', 'bin', 'uv')
    if not os.path.exists(uv):
        return 'no-uv'
    if os.path.exists(INSTALL_FAILED):
        return 'failed'
    os.makedirs(STATE, exist_ok=True)
    lock = open(INSTALL_LOCK, 'a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return 'installing'
    try:
        with open(INSTALL_LOG, 'ab') as log:
            # The child inherits the locked descriptor: the lock lasts as long as the install does.
            subprocess.Popen([sys.executable, '-I', SPEAK, 'install'], stdin=subprocess.DEVNULL, stdout=log,
                             stderr=log, start_new_session=True, close_fds=True, pass_fds=(lock.fileno(),))
    finally:
        lock.close()
    return 'installing'


def main():
    sys.stdin.read()
    out = run('rule').stdout
    if not out.strip():
        return
    missing = run('check').stdout.split()
    notes = []
    if 'engine' in missing:
        why = start_install()
        notes.append(NOTICE[why]) if why else None
    notes += [NOTICE['player']] if 'player' in missing else []
    print('\n'.join([out.rstrip()] + notes))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
