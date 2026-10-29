#!/usr/bin/env python3
"""UserPromptSubmit hook: a new message from the human cuts nothing; a speech playing goes on, and a new speech
waits its turn in the queue (only dictation cuts the one playing). When this session will not speak (`speak silent`,
or `speak` missing), or reads the whole reply (`mode full`), it prints a note that Claude reads with the message:
leave out the 🔊 line. The rule is injected once, at the start, so the hook remembers (`speak told`) which mode the
model was last told; when the mode goes back to summary it says once to write the line again. Each message also
runs `speak _mictick`: with the microphone choice on `auto`, that is where the end of the meeting (microphone busy,
now free) sends the choice back to `wait` when no speech is playing to see it. The note says why the
session is silent (`speak silent` prints it): voice off, engine being installed, or engine missing. Fail-open: exits 0."""
import json
import os
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')
NOTE = 'speak: a voz está desligada nesta sessão; não termine esta resposta com a linha 🔊.'
NOTE_MISSING = 'speak: o motor de voz não está instalado (rode /speak install); não termine esta resposta com a linha 🔊.'
NOTE_FULL = 'speak: a leitura é da resposta inteira; não termine esta resposta com a linha 🔊.'
NOTE_BACK = 'speak: a leitura voltou a ser só o resumo; termine esta resposta com a linha 🔊.'


def speak(*args):
    return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, timeout=10).stdout


def silent_note(why):
    """The note for the reason `speak silent` printed."""
    word, _, percent = why.partition(' ')
    if word == 'installing':
        pct = ' (%s%%)' % percent if percent.isdigit() else ''
        return 'speak: o motor de voz ainda está sendo instalado%s; não termine esta resposta com a linha 🔊.' % pct
    if word == 'missing':
        return NOTE_MISSING
    return NOTE


def mode_note():
    """The note for the mode in force: full says to leave the line out at every message; the return to summary says
    to write it again, once, if the model was last told full."""
    mode = json.loads(speak('status', '--json')).get('mode')
    told = speak('told').strip()
    if mode == 'full':
        speak('told', 'full')
        return NOTE_FULL
    if mode == 'summary':
        if told != 'summary':
            speak('told', 'summary')
        if told == 'full':
            return NOTE_BACK
    return None


def main():
    sys.stdin.read()
    if not os.path.exists(SPEAK):
        print(NOTE)
        return
    try:
        speak('_mictick')
    except Exception:
        pass  # fail-open: the note below does not depend on it
    r = subprocess.run([sys.executable, '-I', SPEAK, 'silent'], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        print(silent_note(r.stdout.strip()))
    else:
        note = mode_note()
        if note:
            print(note)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
