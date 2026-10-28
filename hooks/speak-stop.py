#!/usr/bin/env python3
"""Stop hook: hands the reply to `speak say -`, which picks what is spoken (the whole prose, or only the 🔊 line) and
speaks it in the background. Waits (at most 4 s) for `speak say -` to return, which is quick because the speech
itself runs detached inside it: `speak` must still find this hook alive to locate its session (the nearest `claude`
ancestor). Fail-open: prints nothing and exits 0 in every case. Always hands the reply over (also with
CLAUDE_SPEAK=0): `speak` decides, per session, whether to speak. Silent only when `speak` is not installed.
"""
import json
import os
import shutil
import subprocess
import sys


def last_message(data):
    """last_assistant_message from the hook input; else the last assistant text in the transcript."""
    message = data.get('last_assistant_message')
    if isinstance(message, str) and message:
        return message
    path = data.get('transcript_path')
    if not path or not os.path.exists(path):
        return ''
    found = ''
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if entry.get('type') != 'assistant':
                continue
            content = (entry.get('message') or {}).get('content')
            texts = [c.get('text', '') for c in content or [] if isinstance(c, dict) and c.get('type') == 'text']
            if any(t.strip() for t in texts):
                found = '\n'.join(texts)
    return found


def main():
    speak = shutil.which('speak') or os.path.expanduser('~/.local/bin/speak')
    if not os.path.exists(speak):
        return
    message = last_message(json.load(sys.stdin))
    if message.strip():
        subprocess.run([sys.executable, '-I', speak, 'say', '-'], input=message.encode('utf-8'),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
