#!/usr/bin/env python3
"""Stop hook: hands the reply to `speak say -`, which picks what is spoken (the whole prose, or only the 🔊 line) and
speaks it in the background. Waits (at most 4 s) for `speak say -` to return, which is quick because the speech
itself runs detached inside it: `speak` must still find this hook alive to locate its session (the nearest `claude`
ancestor). Fail-open: exits 0 in every case. Always hands the reply over (also with CLAUDE_SPEAK=0): `speak` decides,
per session, whether to speak. Silent when `speak` (../bin/speak, never the PATH) is missing.

Phone output (`speak output` says `phone`): `speak say -` plays nothing and synthesizes an mp3 in the foreground, which
takes minutes (the wait is then 300 s) and prints its path. The hook then asks Claude to continue, with
{"decision": "block", "reason": ...}, so that Claude sends the file to the human (only the model has that tool). On the
turn that follows (stop_hook_active) `speak say -` does nothing, so there is no loop.
"""
import json
import os
import subprocess
import sys

SPEAK = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'bin', 'speak')


REQUEST = ('speak: o áudio desta resposta está em %s. Envie esse arquivo ao humano com a ferramenta SendUserFile '
           '(carregue-a pelo ToolSearch se precisar), sem legenda longa, e termine sem escrever mais nada. Se essa '
           'ferramenta não existir nesta sessão, diga em uma frase que o modo celular só funciona no controle remoto '
           'e sugira `speak mobile off`.')


def phone_output(speak):
    """True when this session's replies go to the phone; False on any doubt."""
    try:
        done = subprocess.run([sys.executable, '-I', speak, 'output'], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=4)
        return done.stdout.decode('utf-8', 'replace').strip() == 'phone'
    except (OSError, subprocess.SubprocessError):
        return False


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
    speak = SPEAK
    if not os.path.exists(speak):
        return
    data = json.load(sys.stdin)
    message = last_message(data)
    if not message.strip():
        return
    phone = phone_output(speak)
    env = {**os.environ, 'CLAUDE_SPEAK_STOP_ACTIVE': '1' if data.get('stop_hook_active') else '0'}
    done = subprocess.run([sys.executable, '-I', speak, 'say', '-'], input=message.encode('utf-8'), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=300 if phone else 4)
    path = done.stdout.decode('utf-8', 'replace').strip()
    if phone and not data.get('stop_hook_active') and path and os.path.isfile(path):
        print(json.dumps({'decision': 'block', 'reason': REQUEST % path}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
