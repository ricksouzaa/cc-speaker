#!/usr/bin/env python3
"""SessionStart hook: prints the spoken-reply rule (`speak rule`), which Claude Code puts in the context, plus a notice
when the engine or an audio player is missing. Fail-open: exits 0 in every case."""
import os
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')
NOTICE = {
    'engine': 'speak: o motor de voz não está instalado. Na sua primeira resposta, ofereça ao humano instalá-lo '
              '(`speak install`, cerca de 350 MB, sem sudo, precisa do uv); não instale sem o sim dele.',
    'player': 'speak: nenhum tocador de áudio (pw-play, paplay ou aplay) foi encontrado; sem ele a voz não toca. '
              'Avise o humano na primeira resposta.',
}


def run(*args):
    return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, timeout=10)


def main():
    sys.stdin.read()
    out = run('rule').stdout
    if not out.strip():
        return
    notes = [NOTICE[w] for w in run('check').stdout.split() if w in NOTICE]
    print('\n'.join([out.rstrip()] + notes))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
