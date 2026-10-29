#!/usr/bin/env python3
"""UserPromptSubmit hook: a new message from the human cuts nothing; a speech playing goes on, and a new speech
waits its turn in the queue (only dictation cuts the one playing). When this session will not speak (`speak silent`,
or `speak` missing), it prints a note that Claude reads with the message: leave out the 🔊 line. Fail-open: exits 0 in every case."""
import os
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')
NOTE = 'speak: a voz está desligada nesta sessão; não termine esta resposta com a linha 🔊.'


def main():
    sys.stdin.read()
    if not os.path.exists(SPEAK) or subprocess.run([sys.executable, '-I', SPEAK, 'silent'], capture_output=True,
                                                   timeout=10).returncode == 0:
        print(NOTE)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
