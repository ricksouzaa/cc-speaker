"""The spoken reply: `speak` picks what is heard (whole prose, or the 🔊 line), turns on and off without the engine,
and the Stop hook only hands the reply over."""
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, 'hooks', 'speak-stop.py')
START = os.path.join(ROOT, 'hooks', 'speak-start.py')
CUT = os.path.join(ROOT, 'hooks', 'speak-cut.py')
SPEAK = os.path.join(ROOT, 'bin', 'speak')


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


speak = load('speak', SPEAK)
speak_stop = load('speak_stop', HOOK)


def isolate(case, root):
    """Points every path constant of the in-process `speak` module into `root`, so that no test touches the real
    ~/.config, ~/.local/share or ~/.local/state (main() runs migrate()). Undone at the test's cleanup."""
    from unittest import mock
    data = os.path.join(root, '.local', 'share', 'claude-speak')
    conf = os.path.join(root, '.config', 'claude-speak')
    state = os.path.join(root, '.local', 'state', 'claude-speak')
    paths = {'DATA': data, 'CONF': conf, 'STATE': state,
             'OFF_FLAG': os.path.join(conf, 'off'), 'MODE_FILE': os.path.join(conf, 'mode'),
             'SIZE_FILE': os.path.join(conf, 'size'), 'VOICE_FILE': os.path.join(conf, 'voice'),
             'ALL_MARK': os.path.join(state, 'all'), 'SESSIONS': os.path.join(state, 'sessions'),
             'PID': os.path.join(state, 'speech.pid'), 'OWNER': os.path.join(state, 'speech.owner'),
             'QUEUE': os.path.join(state, 'queue'), 'LOCK': os.path.join(state, 'queue.lock'),
             'LOG': os.path.join(state, 'error.log'), 'VENV_PY': os.path.join(data, '.venv', 'bin', 'python'),
             'MODEL': os.path.join(data, 'kokoro-v1.0.onnx'), 'VOICES': os.path.join(data, 'voices-v1.0.bin')}
    for name, value in paths.items():
        patcher = mock.patch.object(speak, name, value)
        patcher.start()
        case.addCleanup(patcher.stop)
    return paths

REPLY = """## O que mudou

Fiz a mudança em `bin/speak` e no [painel](https://x.y/z).

```python
print("não leia isto")
```

| O quê | Onde |
|---|---|
| Comando `speak off` | `~/.local/bin/speak` |

- Rode `speak mode summary` para voltar ao resumo
- O log fica em ~/.local/state/claude-speak/error.log e no speak-stop.py

🔊 Terminei a voz; falta você testar."""


class Summary(unittest.TestCase):
    def test_only_the_marked_line_is_spoken(self):
        self.assertEqual(speak.to_speak(REPLY, 'summary'), 'Terminei a voz; falta você testar.')

    def test_no_marked_line_no_sound(self):
        self.assertEqual(speak.to_speak('Saída:\n```\nok\n```', 'summary'), '')
        self.assertEqual(speak.spoken_line(None), '')

    def test_last_marked_line_wins_and_markdown_goes(self):
        msg = '🔊 antiga\ntexto\n> **🔊 Veja o [painel](https://x.y/z) e o `arquivo`.**'
        self.assertEqual(speak.to_speak(msg, 'summary'), 'Veja o painel e o arquivo.')

    def test_long_line_is_cut(self):
        self.assertLessEqual(len(speak.to_speak('🔊 ' + 'a' * 1000, 'summary', 'medium')), 600)

    def test_limit_follows_the_size(self):
        text = '🔊 ' + 'Uma frase curta aqui. ' * 100
        for size, limit in (('small', 300), ('medium', 600), ('large', 1200)):
            said = speak.to_speak(text, 'summary', size)
            self.assertLessEqual(len(said), limit)
            self.assertGreater(len(said), limit - 40)


class Full(unittest.TestCase):
    def setUp(self):
        self.said = speak.to_speak(REPLY, 'full')

    def test_prose_and_tables_are_read(self):
        for part in ('O que mudou.', 'Fiz a mudança em e no painel.', 'O quê, Onde.', 'Comando speak off.',
                     'Rode speak mode summary para voltar ao resumo.'):
            self.assertIn(part, self.said)

    def test_code_paths_links_files_and_the_summary_line_go(self):
        for gone in ('print', 'não leia', 'https', '~/', 'error.log', 'speak-stop', '|', '---', '🔊', 'Terminei', '`'):
            self.assertNotIn(gone, self.said)

    def test_unclosed_fence_hides_the_rest(self):
        self.assertEqual(speak.to_speak('Antes.\n```\ncódigo\nmais', 'full'), 'Antes.')

    def test_long_reply_is_cut_at_a_sentence_end(self):
        said = speak.to_speak('Uma frase curta aqui. ' * 600, 'full')
        self.assertLessEqual(len(said), speak.LIMIT['full'])
        self.assertTrue(said.endswith('.'))

    def test_pieces_start_short_and_keep_every_word(self):
        text = speak.to_speak('Frase número um, um pouco longa para encher. ' * 40, 'full')
        parts = speak.pieces(text)
        self.assertLessEqual(len(parts[0]), speak.PIECES[0])
        self.assertTrue(all(len(p) <= speak.PIECES[-1] for p in parts))
        self.assertEqual(' '.join(parts), text)

    def test_pieces_grow_gradually(self):
        text = speak.to_speak('Frase número um, um pouco longa para encher. ' * 40, 'full')
        parts = speak.pieces(text)
        self.assertGreaterEqual(len(parts), 5)
        for i, part in enumerate(parts):
            self.assertLessEqual(len(part), speak.PIECES[min(i, len(speak.PIECES) - 1)])
        for i, part in enumerate(parts[:-1]):
            first = re.split(r'(?<=[.!?;:])\s+', parts[i + 1])[0]
            self.assertGreater(len(part + ' ' + first), speak.PIECES[min(i, len(speak.PIECES) - 1)])
        self.assertEqual(' '.join(parts), text)


class Ahead(unittest.TestCase):
    """The next piece is synthesized while the current one plays, so no silence falls between pieces."""

    def test_next_piece_is_synthesized_while_the_current_one_plays(self):
        import threading
        playing_first = threading.Event()
        second_started = threading.Event()

        def synth(piece):
            if piece == 'dois':
                second_started.set()
            return piece.upper()

        played = []
        for samples in speak.synthesize_ahead(['um', 'dois', 'três'], synth):
            if samples == 'UM':
                playing_first.set()
                # the player is busy with the first piece: the second must already be on its way
                self.assertTrue(second_started.wait(2), 'second piece waited for the first to finish playing')
            played.append(samples)
        self.assertTrue(playing_first.is_set())
        self.assertEqual(played, ['UM', 'DOIS', 'TRÊS'])

    def test_a_synthesis_error_reaches_the_player(self):
        def synth(piece):
            if piece == 'b':
                raise ValueError('motor falhou')
            return piece

        got = []
        with self.assertRaises(ValueError):
            for samples in speak.synthesize_ahead(['a', 'b', 'c'], synth):
                got.append(samples)
        self.assertEqual(got, ['a'])

    def test_stopping_early_does_not_hang(self):
        gen = speak.synthesize_ahead(['p%d' % i for i in range(50)], lambda p: p)
        self.assertEqual(next(gen), 'p0')
        gen.close()  # the player was cut: the background synthesis must not keep the program alive


class Microphone(unittest.TestCase):
    def test_recordings_are_the_input_streams_only(self):
        dump = json.dumps([
            {'id': 93, 'info': {'props': {'media.class': 'Stream/Input/Audio', 'application.name': 'Discord'}}},
            {'id': 120, 'info': {'props': {'media.class': 'Stream/Output/Audio'}}},
            {'id': 7, 'info': {'props': {'media.class': 'Audio/Source'}}},
            {'id': 130, 'info': {'props': {'media.class': 'Stream/Input/Audio', 'application.name': 'PipeWire ALSA'}}},
            {'id': 5, 'info': None}, 'junk'])
        self.assertEqual(speak.recordings(dump), {93, 130})
        self.assertIsNone(speak.recordings(b'not json'))

    def test_mic_busy(self):
        self.assertFalse(speak.mic_busy(None))
        self.assertFalse(speak.mic_busy(set()))
        self.assertTrue(speak.mic_busy({42}))

    def test_turn_waits_while_recording_and_then_comes(self):
        from unittest import mock
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        isolate(self, root)
        seen = [{7}, {7}, set()]
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', side_effect=lambda: seen.pop(0)):
            self.assertTrue(speak.wait_turn(None, True))
        self.assertEqual(seen, [])  # looked three times: two busy, then free
        with open(speak.PID) as fh:
            self.assertEqual(fh.read(), str(os.getpid()))
        self.assertEqual(os.listdir(speak.QUEUE), [])

    def test_watch_cuts_on_any_recording(self):
        import threading
        from unittest import mock
        done = threading.Event()
        player = object()
        with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', return_value={7}), \
                mock.patch.object(speak, 'cut_by_microphone', side_effect=lambda p: done.set()) as cut:
            speak.watch_microphone(player)
            self.assertTrue(done.wait(2))
        cut.assert_called_with(player)


class Migration(unittest.TestCase):
    """The folders of the former name (`claude-voz`) move to `claude-speak` on the first call."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.env = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def put(self, path, text=''):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(text)

    def speak(self, *args, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True,
                              env={**self.env, **env})

    def test_old_folders_move_and_keep_choices(self):
        self.put(self.path('.local', 'share', 'claude-voz', 'kokoro-v1.0.onnx'), 'model')
        self.put(self.path('.config', 'claude-voz', 'desligado'))
        self.put(self.path('.config', 'claude-voz', 'modo'), 'resumo\n')
        self.put(self.path('.local', 'state', 'claude-voz', 'sessoes', '1-2'), 'mudo')
        out = self.speak('status').stdout
        self.assertIn('voz: desligada', out)
        self.assertIn('modo: summary', out)
        self.assertTrue(os.path.exists(self.path('.local', 'share', 'claude-speak', 'kokoro-v1.0.onnx')))
        self.assertTrue(os.path.exists(self.path('.config', 'claude-speak', 'off')))
        with open(self.path('.config', 'claude-speak', 'mode')) as fh:
            self.assertEqual(fh.read().strip(), 'summary')
        for old in ('.local/share', '.config', '.local/state'):
            self.assertFalse(os.path.exists(self.path(old, 'claude-voz')), old)
        self.assertFalse(os.path.exists(self.path('.local', 'state', 'claude-speak', 'sessoes')))

    def test_old_state_marker_and_leftovers(self):
        for name in ('tudo', 'fala.pid', 'fala.dono', 'erro.log', 'fala-123.wav', 'fala-9.wav'):
            self.put(self.path('.local', 'state', 'claude-voz', name), 'x')
        self.speak('status')
        folder = self.path('.local', 'state', 'claude-speak')
        self.assertTrue(os.path.exists(os.path.join(folder, 'all')))
        for name in ('tudo', 'fala.pid', 'fala.dono', 'erro.log', 'fala-123.wav', 'fala-9.wav'):
            self.assertFalse(os.path.exists(os.path.join(folder, name)), name)

    def test_old_mode_completo_becomes_full(self):
        self.put(self.path('.config', 'claude-voz', 'modo'), 'completo\n')
        self.assertIn('modo: full', self.speak('status').stdout)
        with open(self.path('.config', 'claude-speak', 'mode')) as fh:
            self.assertEqual(fh.read().strip(), 'full')
        self.assertFalse(os.path.exists(self.path('.config', 'claude-speak', 'modo')))

    def test_new_folder_wins_and_old_is_left(self):
        self.put(self.path('.config', 'claude-voz', 'desligado'))
        os.makedirs(self.path('.config', 'claude-speak'))
        self.assertIn('voz: ligada', self.speak('status').stdout)
        self.assertTrue(os.path.exists(self.path('.config', 'claude-voz', 'desligado')))

    def test_old_env_names_do_nothing(self):
        self.assertIn('voz: ligada', self.speak('status', CLAUDE_VOZ='0').stdout)
        self.assertIn('voz: desligada', self.speak('status', CLAUDE_SPEAK='0').stdout)


class Toggle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def speak(self, *args, stdin=None, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, input=stdin,
                              env={**self.env, **env})

    def test_off_then_on(self):
        self.assertIn('voz: ligada', self.speak('status').stdout)
        self.assertIn('voz: desligada', self.speak('off').stdout)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'off')))
        self.assertIn('voz: ligada', self.speak('on').stdout)

    def test_session_switch(self):
        out = self.speak('status', CLAUDE_SPEAK='0').stdout
        self.assertIn('voz: desligada', out)
        self.assertIn('CLAUDE_SPEAK=0', out)

    def test_mode_defaults_to_full_and_is_kept(self):
        self.assertIn('modo: full', self.speak('status').stdout)
        self.assertIn('modo: summary', self.speak('mode', 'summary').stdout)
        self.assertIn('modo: summary', self.speak('status').stdout)
        self.assertIn('modo: full', self.speak('status', CLAUDE_SPEAK_MODE='full').stdout)
        self.assertEqual(self.speak('mode', 'outro').returncode, 2)

    def test_without_engine_speaking_is_silent_and_test_says_why(self):
        self.assertIn('não instalado', self.speak('status').stdout)
        self.assertEqual(self.speak('say', 'oi').returncode, 0)
        self.assertEqual(self.speak('stop').returncode, 0)
        self.assertEqual(self.speak('say', '-', stdin=REPLY).returncode, 0)
        r = self.speak('test')
        self.assertEqual(r.returncode, 1)
        self.assertIn('speak install', r.stderr)


def speak_stat_start():
    return speak._stat_fields(os.getpid())[19]


def speak_read(folder, key):
    from unittest import mock
    with mock.patch.object(speak, 'SESSIONS', folder):
        return speak.read_session(key)


class Session(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin'}
        self.state = isolate(self, self.tmp.name)['SESSIONS']
        self.sleep = subprocess.Popen(['sleep', '60'])
        self.addCleanup(self.sleep.wait)
        self.addCleanup(self.sleep.kill)
        self.me = speak.session_key(os.getpid())
        self.other = speak.session_key(self.sleep.pid)

    def speak(self, *args, session, input=None, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, input=input,
                              env={**self.env, 'CLAUDE_SPEAK_SESSION': session, **env})

    def test_off_mutes_only_this_session(self):
        self.speak('off', session=self.me)
        mine = self.speak('status', session=self.me).stdout
        self.assertIn('voz: desligada', mine)
        self.assertIn('esta sessão: muda', mine)
        other = self.speak('status', session=self.other).stdout
        self.assertIn('voz: ligada', other)
        self.assertIn('segue a geral', other)

    def test_on_after_off_all_turns_on_only_this_one(self):
        self.speak('off', 'all', session=self.me)
        self.speak('on', session=self.me)
        self.assertIn('voz: ligada', self.speak('status', session=self.me).stdout)
        self.assertIn('voz: desligada', self.speak('status', session=self.other).stdout)

    def test_on_all_clears_choices(self):
        self.speak('off', session=self.me)
        self.speak('off', session=self.other)
        self.speak('on', 'all', session=self.me)
        self.assertIn('voz: ligada', self.speak('status', session=self.me).stdout)
        self.assertIn('voz: ligada', self.speak('status', session=self.other).stdout)

    def test_env_mute_is_a_seed_that_a_later_request_beats(self):
        self.assertIn('voz: desligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)
        self.speak('on', 'all', session=self.me)
        self.assertIn('voz: ligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)

    def test_all_request_after_opening_beats_the_seed(self):
        self.speak('on', 'all', session=self.me)
        self.assertIn('voz: ligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)

    def test_all_request_before_opening_keeps_the_seed(self):
        self.speak('on', 'all', session=self.me)
        mark = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak', 'all')
        before = speak.session_started(self.other) - 3600
        os.utime(mark, (before, before))
        self.assertIn('voz: desligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)

    def test_mode_here_does_not_touch_other_sessions(self):
        self.speak('mode', 'summary', session=self.me)
        mine = self.speak('status', session=self.me).stdout
        self.assertIn('modo summary', mine)
        self.assertIn('modo: full', mine)
        other = self.speak('status', session=self.other).stdout
        self.assertIn('modo: full', other)
        self.assertIn('esta sessão: segue a geral, modo segue o geral', other)

    def test_mode_all_sets_every_session_and_the_general(self):
        self.speak('mode', 'summary', session=self.other)
        self.speak('mode', 'full', 'all', session=self.me)
        self.assertIn('modo full', self.speak('status', session=self.other).stdout)  # its own choice was overwritten
        self.assertIn('modo: full', self.speak('status', session=self.me).stdout)
        self.assertEqual(open(os.path.join(self.tmp.name, '.config', 'claude-speak', 'mode')).read().strip(), 'full')

    def test_mode_outside_a_session_is_general(self):
        self.speak('mode', 'summary', session='-')
        self.assertIn('modo: summary', self.speak('status', session=self.me).stdout)

    def test_say_uses_the_session_mode(self):
        from unittest import mock
        heard = []
        with mock.patch.dict(os.environ), \
                mock.patch.object(speak, 'speak_background', lambda text, session: heard.append(text) or 0), \
                mock.patch.object(speak.sys, 'stdin', io.StringIO(REPLY)):
            for name in ('CLAUDE_SPEAK', 'CLAUDE_SPEAK_MODE'):
                os.environ.pop(name, None)
            os.environ['CLAUDE_SPEAK_SESSION'] = self.me
            speak.set_session(self.me, mode='summary')
            speak.main(['say', '-'])
        self.assertEqual(heard, ['Terminei a voz; falta você testar.'])

    def test_on_off_keep_the_session_mode(self):
        self.speak('mode', 'summary', session=self.me)
        self.speak('off', session=self.me)
        with open(os.path.join(self.state, self.me)) as fh:
            self.assertEqual(json.load(fh), {'voice': 'muted', 'mode': 'summary'})

    def put_session(self, key, content):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, key), 'wb') as fh:
            fh.write(content)

    def test_env_mode_beats_the_session_mode(self):
        from unittest import mock
        with mock.patch.dict(os.environ), mock.patch.object(speak, 'SESSIONS', self.state), \
                mock.patch.object(speak, 'MODE_FILE', os.path.join(self.tmp.name, 'mode')):
            os.environ['CLAUDE_SPEAK_MODE'] = 'full'
            self.put_session(self.me, b'{"mode": "summary"}')
            self.assertEqual(speak.mode(self.me), 'full')
            del os.environ['CLAUDE_SPEAK_MODE']
            self.assertEqual(speak.mode(self.me), 'summary')

    def test_legacy_and_corrupt_session_files_are_tolerated(self):
        self.put_session(self.me, b'muted')
        self.put_session(self.other, b'{')
        mine = self.speak('status', session=self.me).stdout
        self.assertIn('voz: desligada', mine)
        self.assertIn('esta sessão: muda', mine)
        other = self.speak('status', session=self.other).stdout
        self.assertIn('esta sessão: segue a geral, modo segue o geral', other)
        for key in (self.me, self.other):
            self.assertEqual(self.speak('say', '-', session=key, input=REPLY).returncode, 0)

    def test_non_utf8_session_file_is_tolerated(self):
        self.put_session(self.me, b'\xff\xfe')
        self.assertIn('segue a geral', self.speak('status', session=self.me).stdout)
        self.assertEqual(speak_read(self.state, self.me), {})

    def test_set_session_over_a_legacy_file_keeps_the_voice(self):
        self.put_session(self.me, b'muted')
        self.speak('mode', 'summary', session=self.me)
        with open(os.path.join(self.state, self.me)) as fh:
            self.assertEqual(json.load(fh), {'voice': 'muted', 'mode': 'summary'})

    def test_bad_mode_is_refused(self):
        r = self.speak('mode', 'resumo', session=self.me)
        self.assertEqual(r.returncode, 2)
        self.assertIn('speak mode full', r.stderr)
        self.assertIn('speak mode summary', r.stderr)

    def test_forced_key_with_slash_is_no_session(self):
        self.assertIn('fora de uma sessão do Claude Code', self.speak('status', session='../x').stdout)
        self.speak('off', session='../x')
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'off')))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, '.local', 'state', 'claude-speak', 'x')))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, '.local', 'state', 'x')))
        self.assertEqual(os.listdir(self.state) if os.path.isdir(self.state) else [], [])

    def test_status_has_no_contradiction(self):
        self.speak('on', session=self.me, CLAUDE_SPEAK='0')
        out = self.speak('status', session=self.me, CLAUDE_SPEAK='0').stdout
        self.assertIn('esta sessão: falando', out)
        self.assertNotIn('CLAUDE_SPEAK=0', out)

    def test_seed_survives_a_read_only_state(self):
        os.makedirs(self.state)
        os.chmod(self.state, 0o500)
        self.addCleanup(os.chmod, self.state, 0o700)
        r = self.speak('status', session=self.other, CLAUDE_SPEAK='0')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('voz: desligada', r.stdout)

    def test_dead_session_is_pruned(self):
        self.speak('off', session=self.other)
        self.assertIn(self.other, os.listdir(self.state))
        self.sleep.kill()
        self.sleep.wait()
        self.speak('on', session=self.me)
        self.assertNotIn(self.other, os.listdir(self.state))
        self.assertFalse(speak.session_alive(self.other))

    def test_unknown_scope_is_refused(self):
        r = self.speak('off', 'todas', session=self.me)
        self.assertEqual(r.returncode, 2)
        self.assertIn('use "speak off"', r.stderr)
        self.assertIn('voz: ligada', self.speak('status', session=self.me).stdout)

    def test_session_found_through_shells(self):
        bindir = os.path.join(self.tmp.name, 'bin')
        os.makedirs(bindir)
        fake = os.path.join(bindir, 'claude')
        os.symlink(sys.executable, fake)

        def run(cmd):
            code = 'import subprocess,sys; print(subprocess.run(["sh","-c",sys.argv[1]],capture_output=True,text=True).stdout)'
            inner = '%s -I %s %s' % (sys.executable, SPEAK, cmd)
            return subprocess.run([fake, '-I', '-c', code, inner], capture_output=True, text=True,
                                  env=self.env).stdout

        status = run('status')
        self.assertIn('voz: ', status)
        self.assertNotIn('fora de uma sessão', status)
        run('off')
        self.assertTrue(any(n.split('-')[0].isdigit() for n in os.listdir(self.state)))

    def test_session_found_through_shells_pid(self):
        """The session file is named after the fake claude's own pid."""
        bindir = os.path.join(self.tmp.name, 'bin')
        os.makedirs(bindir)
        fake = os.path.join(bindir, 'claude')
        os.symlink(sys.executable, fake)
        code = ('import subprocess,sys,os; print(os.getpid()); sys.stdout.flush();'
                'subprocess.run(["sh","-c",sys.argv[1]],capture_output=True,text=True)')
        inner = '%s -I %s off' % (sys.executable, SPEAK)
        out = subprocess.run([fake, '-I', '-c', code, inner], capture_output=True, text=True, env=self.env).stdout
        pid = out.split()[0]
        self.assertEqual([n.split('-')[0] for n in os.listdir(self.state)], [pid])

    def test_real_hook_reaches_speak_inside_the_session(self):
        """Through the real hook, `speak say -` still finds the session (the hook must outlive it)."""
        plugin = os.path.join(self.tmp.name, 'plugin')
        os.makedirs(os.path.join(plugin, 'bin'))
        os.makedirs(os.path.join(plugin, 'hooks'))
        hook = os.path.join(plugin, 'hooks', 'speak-stop.py')
        shutil.copy(HOOK, hook)
        recorded = os.path.join(self.tmp.name, 'sessao.txt')
        with open(os.path.join(plugin, 'bin', 'speak'), 'w') as fh:
            fh.write('import importlib.machinery, importlib.util\n'
                     'l = importlib.machinery.SourceFileLoader("speak_real", %r)\n'
                     's = importlib.util.spec_from_loader("speak_real", l)\n'
                     'm = importlib.util.module_from_spec(s); l.exec_module(m)\n'
                     'open(%r, "w").write(str(m.current_session()))\n' % (SPEAK, recorded))
        fake = os.path.join(self.tmp.name, 'claude')
        os.symlink(sys.executable, fake)
        code = ('import subprocess,sys,os,json; print(os.getpid()); sys.stdout.flush();'
                'subprocess.run(["sh","-c",sys.argv[1]],input=sys.argv[2].encode(),capture_output=True)')
        hook_cmd = '%s -I %s' % (sys.executable, hook)
        event = json.dumps({'last_assistant_message': 'Olá, tudo bem.'})
        out = subprocess.run([fake, '-I', '-c', code, hook_cmd, event], capture_output=True, text=True,
                             env=self.env, timeout=30).stdout
        pid = out.split()[0]
        for _ in range(60):
            if os.path.exists(recorded) and open(recorded).read():
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(recorded), 'fake speak never ran')
        self.assertTrue(open(recorded).read().startswith(pid + '-'), open(recorded).read())

    def test_outside_a_session_off_is_global(self):
        self.speak('off', session='-')
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'off')))
        self.assertIn('voz: desligada', self.speak('status', session=self.me).stdout)


    def speech(self, owner):
        """A fake speech playing (a process with the `_play` argument) in its own process group, with speech.pid and
        speech.owner in the temp state."""
        script = os.path.join(tempfile.mkdtemp(dir=self.tmp.name), 'speak')
        with open(script, 'w') as fh:
            fh.write('import time\ntime.sleep(60)\n')
        proc = subprocess.Popen([sys.executable, '-I', script, '_play'], start_new_session=True)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        folder = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'speech.pid'), 'w') as fh:
            fh.write(str(proc.pid))
        with open(os.path.join(folder, 'speech.owner'), 'w') as fh:
            fh.write(owner)
        return proc

    def ends(self, proc, seconds=2):
        try:
            proc.wait(timeout=seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def test_off_here_cuts_only_my_speech(self):
        speech = self.speech(self.other)
        self.speak('off', session=self.me)
        self.assertFalse(self.ends(speech, 0.5))
        speech = self.speech(self.me)
        self.speak('off', session=self.me)
        self.assertTrue(self.ends(speech))

    def test_muted_session_neither_speaks_nor_cuts(self):
        from unittest import mock
        speech = self.speech(self.other)
        folder = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak')
        popen = mock.Mock()
        with mock.patch.dict(os.environ), \
                mock.patch.object(speak, 'ALL_MARK', os.path.join(self.tmp.name, 'all')), \
                mock.patch.object(speak, 'STATE', folder), \
                mock.patch.object(speak, 'SESSIONS', self.state), \
                mock.patch.object(speak, 'PID', os.path.join(folder, 'speech.pid')), \
                mock.patch.object(speak, 'OWNER', os.path.join(folder, 'speech.owner')), \
                mock.patch.object(speak, 'OFF_FLAG', os.path.join(self.tmp.name, 'off')), \
                mock.patch.object(speak, 'engine_ready', lambda: True), \
                mock.patch.object(speak.subprocess, 'Popen', popen):
            for name in ('CLAUDE_SPEAK', 'CLAUDE_SPEAK_SESSION', 'CLAUDE_SPEAK_MODE'):
                os.environ.pop(name, None)
            speak.set_session(self.me, voice='muted')
            speak.speak_background('oi', self.me)
        popen.assert_not_called()
        self.assertFalse(self.ends(speech, 0.5))

    def test_stop_spares_a_process_that_is_not_a_speech(self):
        other = subprocess.Popen(['sleep', '60'], start_new_session=True)
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        folder = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'speech.pid'), 'w') as fh:
            fh.write(str(other.pid))
        self.speak('stop', session=self.me)
        self.assertFalse(self.ends(other, 0.5))

    def test_stop_spares_a_process_with_play_in_another_position(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', '_play'],
                                 start_new_session=True)
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        folder = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'speech.pid'), 'w') as fh:
            fh.write(str(other.pid))
        self.speak('stop', session=self.me)
        self.assertFalse(self.ends(other, 0.5))

    def test_stop_without_argument_cuts_any_speech(self):
        speech = self.speech(self.other)
        self.speak('stop', session=self.me)
        self.assertTrue(self.ends(speech))

    def test_stop_mine_is_gone(self):
        speech = self.speech(self.me)
        r = self.speak('stop', '--mine', session=self.me)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(self.ends(speech, 0.5))

    def test_stop_with_bad_argument_is_refused(self):
        speech = self.speech(self.me)
        r = self.speak('stop', '--all-wrong', session=self.me)
        self.assertEqual(r.returncode, 2)
        self.assertIn('speak stop', r.stderr)
        self.assertNotIn('--mine', r.stderr)
        self.assertFalse(self.ends(speech, 0.5))

    def test_speech_files_go_when_it_ends(self):
        from unittest import mock
        pid, owner = (os.path.join(self.tmp.name, n) for n in ('speech.pid', 'speech.owner'))
        with mock.patch.object(speak, 'PID', pid), mock.patch.object(speak, 'OWNER', owner):
            for number, gone in ((os.getpid(), True), (os.getpid() + 1, False)):
                for path, text in ((pid, str(number)), (owner, 'x')):
                    with open(path, 'w') as fh:
                        fh.write(text)
                speak.clear_speech(os.getpid())
                self.assertEqual((os.path.exists(pid), os.path.exists(owner)), (not gone, not gone))

    def test_new_speech_does_not_cut_or_write_the_files_and_carries_its_session(self):
        from unittest import mock
        speech = self.speech(self.other)
        folder = self.folder()
        calls = []
        with mock.patch.dict(os.environ), mock.patch.object(speak, 'engine_ready', lambda: True), \
                mock.patch.object(speak.subprocess, 'Popen', lambda *a, **k: calls.append(k)):
            for name in ('CLAUDE_SPEAK', 'CLAUDE_SPEAK_SESSION', 'CLAUDE_SPEAK_MODE'):
                os.environ.pop(name, None)
            speak.speak_background('oi', self.me)
            speak.speak_background('oi', None)
        self.assertEqual([c['env']['CLAUDE_SPEAK_SESSION'] for c in calls], [self.me, '-'])
        self.assertFalse(self.ends(speech, 0.5))
        with open(os.path.join(folder, 'speech.owner')) as fh:
            self.assertEqual(fh.read(), self.other)  # still the speech playing
        with open(os.path.join(folder, 'speech.pid')) as fh:
            self.assertEqual(fh.read(), str(speech.pid))

    def folder(self):
        return os.path.join(self.tmp.name, '.local', 'state', 'claude-speak')

    def wait_gone(self, *paths, seconds=2):
        end = time.time() + seconds
        while time.time() < end and any(os.path.exists(p) for p in paths):
            time.sleep(0.05)

    def test_stop_clears_the_speech_files(self):
        speech = self.speech(self.me)
        self.speak('stop', session=self.me)
        self.assertTrue(self.ends(speech))
        files = [os.path.join(self.folder(), n) for n in ('speech.pid', 'speech.owner')]
        self.wait_gone(*files)
        self.assertEqual([os.path.exists(p) for p in files], [False, False])

    def test_off_of_another_session_keeps_its_files(self):
        speech = self.speech(self.other)
        self.speak('off', session=self.me)
        self.assertFalse(self.ends(speech, 0.5))
        for name in ('speech.pid', 'speech.owner'):
            self.assertTrue(os.path.exists(os.path.join(self.folder(), name)))

    def test_stop_of_a_non_speech_touches_nothing(self):
        other = subprocess.Popen(['sleep', '60'])
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        os.makedirs(self.folder(), exist_ok=True)
        pid = os.path.join(self.folder(), 'speech.pid')
        with open(pid, 'w') as fh:
            fh.write(str(other.pid))
        self.speak('stop', session=self.me)
        self.assertIsNone(other.poll())
        self.assertTrue(os.path.exists(pid))

    def test_microphone_cut_clears_the_files(self):
        from unittest import mock
        folder = self.folder()
        os.makedirs(folder)
        pid, owner = os.path.join(folder, 'speech.pid'), os.path.join(folder, 'speech.owner')
        with open(pid, 'w') as fh:
            fh.write(str(os.getpid()))
        with open(owner, 'w') as fh:
            fh.write(self.me)
        player = mock.Mock()
        with mock.patch.object(speak, 'PID', pid), mock.patch.object(speak, 'OWNER', owner), \
                mock.patch.object(speak.os, '_exit', side_effect=SystemExit):
            with self.assertRaises(SystemExit):
                speak.cut_by_microphone(player)
        player.kill.assert_called_once()
        self.assertEqual((os.path.exists(pid), os.path.exists(owner)), (False, False))

    # --- the queue: real processes that run speak's own wait_turn / play, with a fake pw-dump ------------------------

    DRIVER = (
        'import importlib.machinery, importlib.util, os, sys, time\n'
        'loader = importlib.machinery.SourceFileLoader("speak", os.environ["REAL_SPEAK"])\n'
        'm = importlib.util.module_from_spec(importlib.util.spec_from_loader("speak", loader)); loader.exec_module(m)\n'
        'name = sys.argv[2]\n'
        'if os.environ.get("DRIVER") == "play":\n'
        '    sys.exit(m.main(["_play", name]))\n'
        'if not m.wait_turn(m.current_session(), bool(m.shutil.which("pw-dump"))):\n'
        '    sys.exit(3)\n'
        'with open(os.environ["LOG_FILE"], "a") as fh:\n'
        '    fh.write(name + "\\n")\n'
        'if os.environ.get("WATCH"):\n'
        '    m.watch_microphone(type("P", (), {"kill": lambda self: None})())\n'
        'while not os.path.exists(os.path.join(os.environ["RELEASE"], name)):\n'
        '    time.sleep(0.02)\n'
        'm.clear_speech(os.getpid())\n')

    def queue_setup(self):
        """Folders for real waiting processes: HOME in the temp dir, a fake pw-dump busy while `busy` exists."""
        root = self.tmp.name
        self.driver_dir = tempfile.mkdtemp(dir=root)
        self.driver = os.path.join(self.driver_dir, 'speak')
        with open(self.driver, 'w') as fh:
            fh.write(self.DRIVER)
        self.release = os.path.join(root, 'release')
        os.makedirs(self.release)
        self.logfile = os.path.join(root, 'started.log')
        open(self.logfile, 'w').close()
        self.busy = os.path.join(root, 'busy')
        fakebin = os.path.join(root, 'fakebin')
        os.makedirs(fakebin)
        dump = os.path.join(fakebin, 'pw-dump')
        with open(dump, 'w') as fh:
            fh.write('#!/bin/sh\nif [ -e %s ]; then echo \'[{"id":9,"info":{"props":{"media.class":'
                     '"Stream/Input/Audio"}}}]\'; else echo \'[]\'; fi\n' % self.busy)
        os.chmod(dump, 0o755)
        self.env = {'HOME': root, 'PATH': fakebin + ':/usr/bin:/bin', 'REAL_SPEAK': SPEAK,
                    'LOG_FILE': self.logfile, 'RELEASE': self.release}

    def waiter(self, name, session, kind='hold', **extra):
        proc = subprocess.Popen([sys.executable, '-I', self.driver, '_play', name], start_new_session=True,
                                env={**self.env, 'CLAUDE_SPEAK_SESSION': session, 'DRIVER': kind, **extra},
                                stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        self.addCleanup(proc.stderr.close)
        return proc

    def started(self):
        with open(self.logfile) as fh:
            return fh.read().split()

    def until(self, condition, seconds=5):
        end = time.time() + seconds
        while time.time() < end:
            if condition():
                return True
            time.sleep(0.05)
        return condition()

    def tickets(self):
        try:
            return sorted(os.listdir(os.path.join(self.folder(), 'queue')))
        except OSError:
            return []

    def let_go(self, name):
        open(os.path.join(self.release, name), 'w').close()

    def test_second_speech_waits_and_starts_after_the_first_in_arrival_order(self):
        self.queue_setup()
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        third = self.waiter('c', self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 2))
        time.sleep(0.6)
        self.assertEqual(self.started(), ['a'])  # neither b nor c cut or overtook a
        self.assertIsNone(first.poll())
        self.let_go('a')
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        time.sleep(0.4)
        self.assertEqual(self.started(), ['a', 'b'])  # c waits for b
        self.let_go('b')
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b', 'c']))
        self.let_go('c')
        for proc in (first, second, third):
            self.assertEqual(proc.wait(timeout=5), 0)
        self.assertEqual(self.tickets(), [])

    def test_stop_empties_the_queue(self):
        self.queue_setup()
        playing = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        waiting = [self.waiter('b', self.other), self.waiter('c', self.me)]
        self.assertTrue(self.until(lambda: len(self.tickets()) == 2))
        self.speak('stop', session=self.me, **{k: v for k, v in self.env.items() if k != 'HOME'})
        for proc in [playing] + waiting:
            self.assertTrue(self.ends(proc, 5))
        self.assertEqual(self.tickets(), [])
        self.assertEqual(self.started(), ['a'])

    def test_off_in_a_session_drops_only_its_speeches(self):
        self.queue_setup()
        playing = self.waiter('a', self.other)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        mine = self.waiter('b', self.me)
        theirs = self.waiter('c', self.other)
        later = self.waiter('d', self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 3))
        self.speak('off', session=self.me, **{k: v for k, v in self.env.items() if k != 'HOME'})
        self.assertTrue(self.ends(mine, 5))
        self.assertTrue(self.ends(later, 5))
        self.assertEqual(len(self.tickets()), 1)
        self.assertIsNone(playing.poll())
        self.assertIsNone(theirs.poll())
        self.let_go('a')
        self.assertTrue(self.until(lambda: self.started() == ['a', 'c']))
        self.let_go('c')
        self.assertEqual(theirs.wait(timeout=5), 0)

    def test_off_in_the_session_of_the_speech_playing_cuts_it_and_the_next_goes(self):
        self.queue_setup()
        playing = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        nxt = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        self.speak('off', session=self.me, **{k: v for k, v in self.env.items() if k != 'HOME'})
        self.assertTrue(self.ends(playing, 5))
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.let_go('b')
        self.assertEqual(nxt.wait(timeout=5), 0)

    def test_session_turned_off_while_waiting_leaves_without_speaking(self):
        self.queue_setup()
        playing = self.waiter('a', self.other)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        # the waiter is the real play(): it must leave in silence once its session is muted, before any engine
        waiting = self.waiter('w', self.me, kind='play')
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        speak.set_session(self.me, voice='muted')  # file only: the speech is not stopped by this
        self.let_go('a')
        self.assertEqual(waiting.wait(timeout=5), 0)
        self.assertEqual(waiting.stderr.read(), '')  # no ImportError of the engine: it never got to speak
        self.assertEqual(playing.wait(timeout=5), 0)
        self.assertEqual(self.tickets(), [])

    def test_waiting_turn_with_microphone_busy(self):
        self.queue_setup()
        open(self.busy, 'w').close()
        proc = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        time.sleep(0.8)
        self.assertEqual(self.started(), [])  # kept waiting, not dropped
        self.assertIsNone(proc.poll())
        os.remove(self.busy)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.let_go('a')
        self.assertEqual(proc.wait(timeout=5), 0)

    def test_dead_ticket_is_dropped_and_does_not_block(self):
        self.queue_setup()
        gone = subprocess.Popen(['true'])
        gone.wait()
        queue = os.path.join(self.folder(), 'queue')
        os.makedirs(queue)
        dead = os.path.join(queue, '%d-%d' % (time.time_ns() - 10 ** 9, gone.pid))
        notspeech = subprocess.Popen(['sleep', '60'])
        self.addCleanup(notspeech.wait)
        self.addCleanup(notspeech.kill)
        alive = os.path.join(queue, '%d-%d' % (time.time_ns() - 10 ** 9, notspeech.pid))
        for path in (dead, alive):
            with open(path, 'w') as fh:
                fh.write(self.other)
        proc = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.assertEqual([os.path.exists(dead), os.path.exists(alive)], [False, False])
        self.assertIsNone(notspeech.poll())  # only the ticket goes; the process is left alone
        self.let_go('a')
        self.assertEqual(proc.wait(timeout=5), 0)

    def test_speeches_entering_together_never_have_two_owners(self):
        self.queue_setup()
        procs = [self.waiter(n, self.me) for n in 'abcd']
        owners = []
        for _ in procs:
            self.assertTrue(self.until(lambda: len(self.started()) > len(owners)))
            time.sleep(0.4)  # nobody is released: a second owner would show up now
            self.assertEqual(len(self.started()), len(owners) + 1, self.started())
            with open(os.path.join(self.folder(), 'speech.pid')) as fh:
                holder = int(fh.read())
            owners.append(self.started()[-1])
            self.assertIn(holder, [p.pid for p in procs])
            self.let_go(owners[-1])
        for proc in procs:
            self.assertEqual(proc.wait(timeout=5), 0)
        self.assertEqual(sorted(owners), list('abcd'))
        self.assertEqual(self.tickets(), [])

    def test_dictation_cuts_the_speech_playing_and_the_waiting_ones_follow(self):
        self.queue_setup()
        playing = self.waiter('a', self.me, WATCH='1')
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        waiting = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        open(self.busy, 'w').close()  # dictation starts
        self.assertEqual(playing.wait(timeout=5), 0)  # cut by the microphone watch
        self.assertFalse(os.path.exists(os.path.join(self.folder(), 'speech.pid')))
        time.sleep(0.6)
        self.assertEqual(self.started(), ['a'])  # b is kept, waiting for the microphone
        self.assertEqual(len(self.tickets()), 1)
        os.remove(self.busy)  # dictation ends
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.let_go('b')
        self.assertEqual(waiting.wait(timeout=5), 0)

    def test_speak_test_speaks_even_with_the_voice_off(self):
        import types
        from unittest import mock
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        isolate(self, root)
        made = []

        def kokoro(*args):
            made.append(args)
            raise RuntimeError('stop here')

        fake = types.ModuleType('kokoro_onnx')
        fake.Kokoro = kokoro
        speak.set_session(self.me, voice='muted')
        for test_flag, reaches in (({}, False), ({'CLAUDE_SPEAK_TEST': '1'}, True)):
            made.clear()
            with mock.patch.dict(sys.modules, {'kokoro_onnx': fake}), \
                    mock.patch.dict(os.environ, {'CLAUDE_SPEAK_SESSION': self.me, **test_flag}), \
                    mock.patch.object(speak, 'QUEUE_POLL', 0.01), \
                    mock.patch.object(speak.shutil, 'which', side_effect=lambda n: '/usr/bin/x' if n != 'pw-dump' else None):
                if reaches:
                    with self.assertRaises(RuntimeError):
                        speak.play('Olá.')
                else:
                    self.assertEqual(speak.play('Olá.'), 0)
            self.assertEqual(bool(made), reaches)

    def test_speak_test_command_marks_the_diagnostic(self):
        data = os.path.join(self.tmp.name, '.local', 'share', 'claude-speak')
        os.makedirs(os.path.join(data, '.venv', 'bin'))
        mark = os.path.join(self.tmp.name, 'mark')
        engine = os.path.join(data, '.venv', 'bin', 'python')
        with open(engine, 'w') as fh:
            fh.write('#!/bin/sh\necho "$CLAUDE_SPEAK_TEST" > %s\n' % mark)
        os.chmod(engine, 0o755)
        for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
            open(os.path.join(data, name), 'w').close()
        r = self.speak('test', session=self.me)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(mark) as fh:
            self.assertEqual(fh.read().strip(), '1')

    def test_orphan_tmp_files_are_pruned(self):
        from unittest import mock
        done = subprocess.Popen(['true'])
        done.wait()
        folder = self.folder()
        os.makedirs(folder)
        dead = os.path.join(folder, '.tmp-%d-ab12' % done.pid)
        live = os.path.join(folder, '.tmp-%d-cd34' % os.getpid())
        odd = os.path.join(folder, '.tmp-x')
        for path in (dead, live, odd):
            open(path, 'w').close()
        with mock.patch.object(speak, 'STATE', folder):
            speak.write_atomic(os.path.join(folder, 'alvo'), 'oi')
        self.assertEqual([os.path.exists(p) for p in (dead, live, odd)], [False, True, True])


class Hook(unittest.TestCase):
    def test_transcript_fallback_takes_the_last_assistant_text(self):
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8') as fh:
            for entry in ({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'primeira'}]}},
                          {'type': 'user', 'message': {'content': 'oi'}},
                          {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'segunda'}]}},
                          {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash'}]}}):
                fh.write(json.dumps(entry) + '\n')
        self.addCleanup(os.remove, fh.name)
        self.assertEqual(speak_stop.last_message({'transcript_path': fh.name}), 'segunda')

    def plugin(self, home, hook='speak-stop.py', fake=True):
        """A copy of the hook in a fake plugin folder, with (or without) a fake bin/speak that records its call."""
        root = os.path.join(home, 'plugin')
        os.makedirs(os.path.join(root, 'hooks'))
        os.makedirs(os.path.join(root, 'bin'))
        shutil.copy(os.path.join(ROOT, 'hooks', hook), os.path.join(root, 'hooks', hook))
        if fake:
            with open(os.path.join(root, 'bin', 'speak'), 'w') as fh:
                fh.write('import sys\nopen(%r, "w").write(" ".join(sys.argv[1:]) + "|" + sys.stdin.read())\n'
                         % os.path.join(home, 'seen'))
        return os.path.join(root, 'hooks', hook)

    def hand_over(self, legacy=False, **env):
        """Runs the hook with a fake `speak` beside it and returns what the fake received (arguments, `|`, stdin)."""
        with tempfile.TemporaryDirectory() as home:
            hook = self.plugin(home)
            seen = os.path.join(home, 'seen')
            if legacy:
                os.makedirs(os.path.join(home, '.claude', 'hooks'))
                open(os.path.join(home, '.claude', 'hooks', 'speak-stop.py'), 'w').close()
            r = subprocess.run([sys.executable, '-I', hook], input=json.dumps({'last_assistant_message': REPLY}),
                               capture_output=True, text=True, env={'HOME': home, 'PATH': '/usr/bin:/bin', **env})
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
            for _ in range(50):
                if os.path.exists(seen) and os.path.getsize(seen):
                    break
                time.sleep(0.05)
            return open(seen).read() if os.path.exists(seen) else None

    def test_hook_hands_the_reply_to_speak(self):
        self.assertEqual(self.hand_over(), 'say -|' + REPLY)

    def test_hook_hands_over_even_with_env_mute(self):
        self.assertEqual(self.hand_over(CLAUDE_SPEAK='0'), 'say -|' + REPLY)

    def test_hook_is_mute_while_the_former_voice_is_installed(self):
        self.assertIsNone(self.hand_over(legacy=True))

    def test_hook_is_forced_by_the_variable(self):
        self.assertEqual(self.hand_over(legacy=True, CLAUDE_SPEAK_PLUGIN_FORCE='1'), 'say -|' + REPLY)

    def test_hook_is_silent_and_exits_zero_without_speak(self):
        with tempfile.TemporaryDirectory() as home:
            hook = self.plugin(home, fake=False)
            r = subprocess.run([sys.executable, '-I', hook], input='{"last_assistant_message": "oi"}',
                               capture_output=True, text=True, env={'HOME': home, 'PATH': '/usr/bin:/bin'})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))

    def test_hook_survives_garbage_input(self):
        with tempfile.TemporaryDirectory() as home:
            r = subprocess.run([sys.executable, '-I', self.plugin(home)], input='not json', capture_output=True,
                               text=True, env={'HOME': home, 'PATH': '/usr/bin:/bin'})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))


class Silent(unittest.TestCase):
    """`speak silent` answers whether this session will stay silent, and the new-message hook turns that into a note
    that tells Claude to leave out the 🔊 line."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.bin = os.path.join(self.home, '.local', 'bin')
        self.env = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': 'sessao-1'}

    def engine(self):
        data = os.path.join(self.home, '.local', 'share', 'claude-speak')
        os.makedirs(os.path.join(data, '.venv', 'bin'))
        for rel in ('.venv/bin/python', 'kokoro-v1.0.onnx', 'voices-v1.0.bin'):
            open(os.path.join(data, rel), 'w').close()

    def silent(self, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, 'silent'], capture_output=True, text=True,
                              env={**self.env, **env})

    def cut(self, **env):
        r = subprocess.run([sys.executable, '-I', CUT], input='{}', capture_output=True, text=True,
                           env={**self.env, **env})
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        return r.stdout

    def test_on_with_engine_speaks(self):
        self.engine()
        self.assertEqual(self.silent().returncode, 1)
        self.assertEqual(self.cut(), '')

    def test_off_here_is_silent(self):
        self.engine()
        subprocess.run([sys.executable, '-I', SPEAK, 'off'], capture_output=True, env=self.env)
        r = self.silent()
        self.assertEqual((r.returncode, r.stdout), (0, ''))
        note = self.cut()
        self.assertIn('🔊', note)
        self.assertIn('desligada', note)

    def test_off_all_and_env_mute_are_silent(self):
        self.engine()
        self.assertEqual(self.silent(CLAUDE_SPEAK='0').returncode, 0)
        subprocess.run([sys.executable, '-I', SPEAK, 'on', 'all'], capture_output=True, env=self.env)
        subprocess.run([sys.executable, '-I', SPEAK, 'off', 'all'], capture_output=True, env=self.env)
        self.assertEqual(self.silent().returncode, 0)

    def test_without_engine_is_silent(self):
        self.assertEqual(self.silent().returncode, 0)
        self.assertIn('🔊', self.cut())

    def test_new_message_does_not_cut_any_speech_even_this_sessions(self):
        self.engine()
        folder = os.path.join(self.home, '.local', 'state', 'claude-speak')
        os.makedirs(folder)
        script = os.path.join(self.home, 'speak')
        with open(script, 'w') as fh:
            fh.write('import time\ntime.sleep(60)\n')
        speech = subprocess.Popen([sys.executable, '-I', script, '_play'], start_new_session=True)
        self.addCleanup(speech.wait)
        self.addCleanup(speech.kill)
        for name, text in (('speech.pid', str(speech.pid)), ('speech.owner', 'sessao-1')):
            with open(os.path.join(folder, name), 'w') as fh:
                fh.write(text)
        self.assertEqual(self.cut(), '')
        time.sleep(0.5)
        self.assertIsNone(speech.poll())
        self.assertTrue(os.path.exists(os.path.join(folder, 'speech.pid')))
        # the voice off here: the note stays (`speak off` itself cuts this session's speech, by design)
        subprocess.run([sys.executable, '-I', SPEAK, 'off'], capture_output=True, env=self.env)
        self.assertIn('desligada', self.cut())

    def test_without_speak_the_hook_still_notes(self):
        hook = Hook().plugin(self.home, 'speak-cut.py', fake=False)
        r = subprocess.run([sys.executable, '-I', hook], input='{}', capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertIn('🔊', r.stdout)

    def test_cut_hook_is_mute_with_the_former_voice_unless_forced(self):
        os.makedirs(os.path.join(self.home, '.claude', 'hooks'))
        open(os.path.join(self.home, '.claude', 'hooks', 'speak-cut.sh'), 'w').close()
        self.assertEqual(self.cut(), '')  # no engine would note; the guard keeps it mute
        self.assertIn('🔊', self.cut(CLAUDE_SPEAK_PLUGIN_FORCE='1'))


class Size(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def speak(self, *args, key='-', **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              env={**self.env, 'CLAUDE_SPEAK_SESSION': key, **env})

    def test_default_is_medium_and_general_is_kept(self):
        self.assertIn('tamanho do resumo: medium', self.speak('status').stdout)
        self.assertIn('tamanho do resumo: large', self.speak('size', 'large').stdout)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'size')))
        self.assertIn('tamanho do resumo: large', self.speak('status').stdout)

    def test_variable_beats_everything(self):
        self.speak('size', 'large')
        self.assertIn('tamanho do resumo: small', self.speak('status', CLAUDE_SPEAK_SIZE='small').stdout)

    def test_bad_size_is_refused(self):
        for args in (('size',), ('size', 'huge'), ('size', 'small', 'tudo')):
            r = self.speak(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn('voz:', r.stderr)

    def test_session_size_stays_in_the_session_and_all_sets_every_one(self):
        key = '%d-%s' % (os.getpid(), speak_stat_start())
        other = '99999999-1'
        folder = os.path.join(self.tmp.name, '.local', 'state', 'claude-speak', 'sessions')
        self.speak('size', 'small', key=key)
        self.assertEqual(speak_read(folder, key)['size'], 'small')
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'size')))
        self.speak('size', 'large', 'all', key=key)
        self.assertEqual(speak_read(folder, key)['size'], 'large')
        self.assertEqual(open(os.path.join(self.tmp.name, '.config', 'claude-speak', 'size')).read().strip(), 'large')
        self.assertNotIn('size', speak_read(folder, other) if os.path.exists(os.path.join(folder, other)) else {})

    def test_say_uses_the_size_limit(self):
        # no engine: nothing is played, but the size reaches to_speak
        self.assertEqual(self.speak('say', '-', CLAUDE_SPEAK_MODE='summary').returncode, 0)


class Voice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def speak(self, *args, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True,
                              env={**self.env, **env})

    def test_list_marks_the_current_one(self):
        out = self.speak('voice').stdout
        for part in ('dora', 'pf_dora', 'alex', 'pm_alex', 'santa', 'pm_santa', 'feminina', 'masculina'):
            self.assertIn(part, out)
        self.assertRegex(out, r'(?m)^\* dora')
        self.assertRegex(self.speak('voice', CLAUDE_SPEAK_VOICE='pm_santa').stdout, r'(?m)^\* santa')

    def test_short_and_full_names_are_saved(self):
        self.assertIn('voz: pm_alex', self.speak('voice', 'alex').stdout)
        self.assertEqual(open(os.path.join(self.tmp.name, '.config', 'claude-speak', 'voice')).read().strip(), 'pm_alex')
        self.speak('voice', 'pm_santa')
        self.assertIn('voz: pm_santa', self.speak('status').stdout)

    def test_unknown_name_is_refused_and_nothing_is_saved(self):
        r = self.speak('voice', 'bob')
        self.assertEqual(r.returncode, 2)
        self.assertIn('voz:', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, '.config', 'claude-speak', 'voice')))

    def test_order_is_variable_then_file_then_default(self):
        self.assertIn('voz: pf_dora', self.speak('status').stdout)
        self.speak('voice', 'alex')
        self.assertIn('voz: pm_alex', self.speak('status').stdout)
        self.assertIn('voz: pm_santa', self.speak('status', CLAUDE_SPEAK_VOICE='pm_santa').stdout)


class Rule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def rule(self, **env):
        r = subprocess.run([sys.executable, '-I', SPEAK, 'rule'], capture_output=True, text=True,
                           env={**self.env, **env})
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        return r.stdout

    def test_marker_is_replaced_by_the_size_in_force(self):
        self.assertIn('two or three sentences', self.rule())
        self.assertIn('one short sentence', self.rule(CLAUDE_SPEAK_SIZE='small'))
        self.assertIn('four to six sentences', self.rule(CLAUDE_SPEAK_SIZE='large'))
        self.assertNotIn('{size}', self.rule())

    def test_rule_names_the_commands(self):
        text = self.rule()
        for name in ('on', 'off', 'mode', 'size', 'voice', 'status', 'stop', 'install'):
            self.assertIn('/speak:' + name, text)
        self.assertIn('speak size', text)
        self.assertIn('speak voice', text)


class StartHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.env = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}

    def run_hook(self, **env):
        r = subprocess.run([sys.executable, '-I', START], input='{}', capture_output=True, text=True,
                           env={**self.env, **env})
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        return r.stdout

    def engine(self):
        data = os.path.join(self.home, '.local', 'share', 'claude-speak')
        os.makedirs(os.path.join(data, '.venv', 'bin'))
        for rel in ('.venv/bin/python', 'kokoro-v1.0.onnx', 'voices-v1.0.bin'):
            open(os.path.join(data, rel), 'w').close()

    def player(self):
        os.makedirs(os.path.join(self.home, 'bin'))
        path = os.path.join(self.home, 'bin', 'aplay')
        open(path, 'w').close()
        os.chmod(path, 0o755)
        return {'PATH': os.path.join(self.home, 'bin') + ':/usr/bin:/bin'}

    def test_prints_the_rule(self):
        out = self.run_hook()
        self.assertIn('🔊', out)
        self.assertNotIn('{size}', out)

    def test_without_engine_it_asks_claude_to_offer_the_install(self):
        out = self.run_hook()
        self.assertIn('speak install', out)
        self.assertIn('350 MB', out)

    def test_with_engine_and_player_there_is_no_notice(self):
        self.engine()
        out = self.run_hook(**self.player())
        self.assertNotIn('speak install', out)
        self.assertNotIn('tocador', out)

    def test_without_player_it_says_so(self):
        self.engine()
        out = self.run_hook(PATH='/nonexistent')
        self.assertIn('tocador', out)
        self.assertNotIn('speak install', out)

    def test_mute_with_the_former_voice_unless_forced(self):
        os.makedirs(os.path.join(self.home, '.claude', 'hooks'))
        open(os.path.join(self.home, '.claude', 'hooks', 'speak-stop.py'), 'w').close()
        self.assertEqual(self.run_hook(), '')
        self.assertIn('🔊', self.run_hook(CLAUDE_SPEAK_PLUGIN_FORCE='1'))


class Plugin(unittest.TestCase):
    """The manifests, hooks.json and the slash commands are valid and point to files that exist."""

    def load(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
            return json.load(fh)

    def test_manifests(self):
        plugin = self.load('.claude-plugin', 'plugin.json')
        self.assertEqual(plugin['name'], 'speak')
        self.assertRegex(plugin['version'], r'^\d+\.\d+\.\d+$')
        market = self.load('.claude-plugin', 'marketplace.json')
        self.assertEqual(market['name'], 'cc-speaker')
        self.assertEqual([p['name'] for p in market['plugins']], ['speak'])
        self.assertTrue(os.path.isdir(os.path.join(ROOT, market['plugins'][0]['source'])))

    def test_hooks_point_to_files_that_exist(self):
        hooks = self.load('hooks', 'hooks.json')['hooks']
        self.assertEqual(set(hooks), {'SessionStart', 'UserPromptSubmit', 'Stop'})
        self.assertEqual(hooks['SessionStart'][0]['matcher'], 'startup|resume|clear|compact')
        for entries in hooks.values():
            for entry in entries:
                for hook in entry['hooks']:
                    match = re.fullmatch(r'python3 -I "\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[\w.-]+)"', hook['command'])
                    self.assertTrue(match, hook['command'])
                    self.assertTrue(os.path.exists(os.path.join(ROOT, match.group(1))))

    def test_slash_commands_are_for_the_human_only(self):
        names = ('on', 'off', 'mode', 'size', 'voice', 'status', 'stop', 'install')
        self.assertEqual(sorted(os.listdir(os.path.join(ROOT, 'skills'))), sorted(names))
        for name in names:
            with open(os.path.join(ROOT, 'skills', name, 'SKILL.md'), encoding='utf-8') as fh:
                front = fh.read().split('---')[1]
            self.assertRegex(front, r'(?m)^disable-model-invocation: true$', name)
            self.assertRegex(front, r'(?m)^name: %s$' % name)
        with open(os.path.join(ROOT, 'skills', 'stop', 'SKILL.md'), encoding='utf-8') as fh:
            self.assertNotIn('$ARGUMENTS', fh.read())

    def test_removed_pieces_are_gone(self):
        for rel in ('prompts', 'tests/test_speak_prompt.py', 'hooks/speak-cut.sh', 'skills/speak'):
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel)), rel)


class Isolation(unittest.TestCase):
    """The in-process tests must not touch the real folders: run the Session class with HOME and XDG pointing to a
    temporary folder that holds the former `claude-voz` folders, and check that they are left intact."""

    def test_in_process_tests_leave_the_former_folders_alone(self):
        with tempfile.TemporaryDirectory() as home:
            made = {}
            for rel in ('.local/share', '.config', '.local/state'):
                folder = os.path.join(home, rel, 'claude-voz')
                os.makedirs(folder)
                with open(os.path.join(folder, 'marca'), 'w') as fh:
                    fh.write('x')
                made[folder] = ['marca']
            env = {k: v for k, v in os.environ.items() if not k.startswith(('XDG_', 'CLAUDE_SPEAK'))}
            env['HOME'] = home
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'test_speak.py'), 'Session'],
                               capture_output=True, text=True, env=env, cwd=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            for folder, names in made.items():
                self.assertEqual(os.listdir(folder), names, folder)
            for rel in ('.local/share', '.config', '.local/state'):
                self.assertEqual(os.listdir(os.path.join(home, rel)), ['claude-voz'], rel)


if __name__ == '__main__':
    unittest.main()
