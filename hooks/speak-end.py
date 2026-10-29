#!/usr/bin/env python3
"""SessionEnd hook: leaving the session cuts the speech of that session (the one playing and the ones waiting in the
queue); the speeches of other sessions go on. The hook input (session_id, reason) is not used: the Claude Code
`session_id` is not the key `speak` uses for a session (that key is '<pid>-<start>' of the nearest `claude` ancestor),
and this hook runs inside the same Claude Code process as the message hooks, so `speak stop here` finds the session
the same way they do. Quick (the SessionEnd hooks share a 1.5 s budget): the call has a 1 s limit. Fail-open: exits 0
in every case, also with `speak` missing (../bin/speak, never the PATH).
"""
import os
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')


def main():
    sys.stdin.read()
    if not os.path.exists(SPEAK):
        return
    subprocess.run([sys.executable, '-I', SPEAK, 'stop', 'here'], stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
