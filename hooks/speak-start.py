#!/usr/bin/env python3
"""SessionStart hook: prints the spoken-reply rule (`speak rule`), which Claude Code puts in the context, plus a notice
when the engine or an audio player is missing. Without the engine it also starts `speak install` in the background,
detached from the session, once at a time (CLAUDE_SPEAK_AUTOINSTALL=0 turns that off). Fail-open: exits 0 in every case."""
import sys

try:  # fail-open from the first line: a copy without lib/ (or any failure below) ends the hook with 0
    import json
    import os
    import shlex
    import subprocess

    SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib'))  # -I skips it
    import speak_os  # noqa: E402
    import speak_paths  # noqa: E402

    ROOT = speak_paths.root(SPEAK)
    STATE = os.path.join(ROOT, 'state')
    INSTALL_LOG = os.path.join(STATE, 'install.log')
    NOTICE = {
        'installing': 'speak: o motor de voz está sendo instalado em segundo plano (cerca de 350 MB, sem sudo); a voz '
                      'começa sozinha quando terminar. Avise o humano na primeira resposta, em uma frase.',
        'no-uv': 'speak: o motor de voz não está instalado e falta o uv, que o instala. Na primeira resposta, diga ao '
                 'humano como instalar o uv (%s); depois, `/speak install`.' % speak_os.notice_uv(),
        'failed': 'speak: a última instalação do motor de voz falhou; o registro está em %s. Avise o humano na primeira '
                  'resposta; `/speak install` tenta de novo.' % INSTALL_LOG,
        'player': 'speak: nenhum tocador de áudio (%s) foi encontrado; sem ele a voz não toca. '
                  'Avise o humano na primeira resposta.' % speak_os.player_names(),
    }
    # What the person reads on screen (systemMessage), without depending on Claude to pass it on.
    SCREEN = {
        'installing': 'speak: instalando a voz em segundo plano (cerca de 350 MB, sem sudo). O progresso aparece na linha '
                      'embaixo do campo de texto, em /speak status e no menu do /speak; se falhar, rode /speak install.',
        'no-uv': 'speak: falta o uv, que instala a voz. Instale-o (%s) e rode /speak install.' % speak_os.notice_uv(),
        'failed': 'speak: a última instalação da voz falhou; o registro está em %s. Rode /speak install para tentar '
                  'de novo.' % INSTALL_LOG,
        'player': 'speak: nenhum tocador de áudio (%s) foi encontrado; sem ele a voz não toca.' % speak_os.player_names(),
    }

except Exception:
    sys.exit(0)


def run(*args):
    return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, timeout=10)


def start_install():
    """Asks `speak autoinstall` (the one rule: it starts `speak install` detached, once at a time, unless the last one
    failed in this version, the uv is missing or CLAUDE_SPEAK_AUTOINSTALL=0). Returns the NOTICE key to tell Claude,
    or None when there is nothing to tell (engine ready, switched off, or the call failed)."""
    try:
        word = (run('autoinstall').stdout.split() or [''])[0]
    except (OSError, subprocess.SubprocessError):
        return None
    return word if word in ('installing', 'no-uv', 'failed') else None


def share_root():
    """Appends `export CLAUDE_SPEAK_DATA=<root>` to $CLAUDE_ENV_FILE (once), so the shell commands of the session
    reach the same data root as the hooks."""
    path = os.environ.get('CLAUDE_ENV_FILE')
    if not path:
        return
    line = 'export CLAUDE_SPEAK_DATA=%s\n' % shlex.quote(ROOT)
    try:
        with open(path) as fh:
            if line in fh.read().splitlines(True):
                return
    except (OSError, ValueError):
        pass
    with open(path, 'a') as fh:
        fh.write(line)


def main():
    sys.stdin.read()
    try:
        share_root()
    except (OSError, ValueError):
        pass
    out = run('rule').stdout
    if not out.strip():
        return
    missing = run('check').stdout.split()
    keys = []
    why = start_install()  # also clears a stale install.failed when the engine is there
    if why and 'engine' in missing:
        keys.append(why)
    if 'player' in missing:
        keys.append('player')
    if not keys:
        print(out.rstrip())  # nothing for the person to read: the rules alone, as plain text
        return
    print(json.dumps({'systemMessage': '\n'.join(SCREEN[k] for k in keys),
                      'hookSpecificOutput': {'hookEventName': 'SessionStart',
                                             'additionalContext': '\n'.join([out.rstrip()] + [NOTICE[k] for k in keys])}},
                     ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
