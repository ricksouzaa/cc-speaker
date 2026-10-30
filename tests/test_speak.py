"""The spoken reply: `speak` picks what is heard (whole prose, or the 🔊 line), turns on and off without the engine,
and the Stop hook only hands the reply over."""
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import isolation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, 'hooks', 'speak-stop.py')
START = os.path.join(ROOT, 'hooks', 'speak-start.py')
CUT = os.path.join(ROOT, 'hooks', 'speak-cut.py')
SPEAK = os.path.join(ROOT, 'bin', 'speak')


data_dir = isolation.data_dir  # a path inside the plugin's data root below a home


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


speak = load('speak', SPEAK)
speak_stop = load('speak_stop', HOOK)
MODULE_ROOT, _remove_module_root = isolation.module_root()  # threads that outlive a test read this, never the real folder
isolation.pin_module(speak, MODULE_ROOT)


def tearDownModule():
    _remove_module_root()
    isolation.assert_no_workers(unittest.TestCase())
    isolation.assert_untouched(unittest.TestCase())


def remove_if_there(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def no_leaked_watcher(case):
    """Safety net: fails the test (at its cleanup) if a microphone watcher thread is still alive."""
    import threading

    def check():
        alive = [th for th in threading.enumerate()
                 if th.is_alive() and 'watch_microphone.<locals>.loop' in getattr(th._target, '__qualname__', '')]
        case.assertEqual(alive, [], 'a microphone watcher outlived its test')
    case.addCleanup(check)


def isolate(case, root, module=None):
    """Points every path constant of the in-process `speak` module (or `module`) into `root`, pins HOME and drops
    CLAUDE_* and XDG_* from the environment (see tests/isolation.py). Undone at the test's cleanup."""
    return isolation.isolate(case, module or speak, root)


REPLY = """## O que mudou

Fiz a mudança em `bin/speak` e no [painel](https://x.y/z).

```python
print("não leia isto")
```

| O quê | Onde |
|---|---|
| Comando `speak off` | `~/.local/bin/speak` |

- Rode `speak mode summary` para voltar ao resumo
- O log fica em state/error.log da pasta de dados do plugin e no speak-stop.py

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


class Filter(unittest.TestCase):
    def test_inline_code_keeps_only_plain_words(self):
        self.assertEqual(speak.clean('Rode `speak off` na `main`, veja `summary`.'), 'Rode speak off na main, veja summary.')
        for gone in ('ci-mac', 'cc-speaker', 'speak-cc-speaker', 'install_marked', 'e863ea0', 'CLAUDE_SPEAK=0'):
            self.assertEqual(speak.clean('Veja `%s` agora.' % gone), 'Veja agora.')

    def test_acronyms_are_spelled_unless_said_as_a_word(self):
        self.assertEqual(speak.clean('O IBGE e a ANTT.'), 'O i bê gê éh e a á êne tê tê.')
        self.assertEqual(speak.clean('O SUS, o PIX e o NASA.'), 'O SUS, o PIX e o NASA.')
        self.assertEqual(speak.clean('CPF e CNPJ.'), 'cê pê éfe e cê êne pê jota.')
        self.assertEqual(speak.clean('O IPVA e o IPCA.'), 'O i pê vê á e o i pê cê á.')
        self.assertEqual(speak.clean('Tarefa XII, capítulo IV.'), 'Tarefa XII, capítulo IV.')
        self.assertEqual(speak.clean('ATENÇÃO: NÃO mexa, A e B.'), 'ATENÇÃO: NÃO mexa, A e B.')
        self.assertEqual(speak.clean('Um CD novo, API-REST e INSS.'), 'Um cê dê novo, API-REST e i êne ésse ésse.')

    def test_own_words_file_adds_acronyms_said_as_a_word(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        isolate(self, tmp.name)
        self.assertEqual(speak.clean('A CVM e a ANBIMA.'), 'A cê vê ême e a á êne bê i ême á.')
        os.makedirs(speak.CONF, exist_ok=True)
        with open(os.path.join(speak.CONF, 'words'), 'w') as fh:
            fh.write('# lidas como palavra\ncvm\nAnbima\n')
        self.assertEqual(speak.clean('A CVM e a ANBIMA.'), 'A CVM e a ANBIMA.')

    def test_enem_is_respelt_and_the_letter_e_is_stressed(self):
        self.assertEqual(speak.clean('O Enem e o IBGE.'), 'O ênêi e o i bê gê éh.')

    def test_commit_codes_and_head_go(self):
        self.assertEqual(speak.clean('Commit b48e609 e 93a66bd prontos.'), 'Commit e prontos.')
        self.assertEqual(speak.clean('Está no HEAD agora.'), 'Está no agora.')
        self.assertEqual(speak.clean('Versão decade e 1234567 ficam.'), 'Versão decade e 1234567 ficam.')

    def test_middle_dot_becomes_a_comma(self):
        self.assertEqual(speak.clean('um · dois'), 'um, dois')

    def test_pickup_line(self):
        self.assertEqual(speak.full_text('cc-speaker — ramo main · HEAD 93a66bd · enviado'),
                         'cc-speaker — ramo main, enviado.')

    def test_branch_names_go_after_the_keyword(self):
        self.assertEqual(speak.clean('Estou no ramo main agora'), 'Estou no ramo main agora')
        self.assertEqual(speak.clean('Estou no ramo ci-mac.'), 'Estou no ramo.')
        self.assertEqual(speak.clean('O branch fix_1 e o worktree wt2 sumiram'), 'O branch e o worktree sumiram')
        self.assertEqual(speak.clean('No ramo fix/fila-da-voz agora'), 'No ramo agora')
        self.assertEqual(speak.clean('No `fix/fila-da-voz` agora'), 'No agora')

    def test_lowercase_words_with_hyphen_and_digit_go(self):
        self.assertEqual(speak.clean('Use wt-1 e python3-venv hoje'), 'Use e hoje')
        self.assertEqual(speak.clean('Em 2026-10-29 sim'), 'Em 2026-10-29 sim')

    def test_slash_commands_are_read(self):
        self.assertEqual(speak.clean('para cortar uma fala que está tocando, o `/speak stop`'),
                         'para cortar uma fala que está tocando, o speak stop'.replace('o speak', 'o barra speak'))
        self.assertEqual(speak.clean('Use `/speak stop` agora.'), 'Use barra speak stop agora.')
        self.assertEqual(speak.clean('Use /speak stop agora.'), 'Use barra speak stop agora.')
        self.assertEqual(speak.clean('Rode `/reload-plugins`.'), 'Rode barra reload plugins.')
        self.assertEqual(speak.clean('Rode /reload-plugins.'), 'Rode barra reload plugins.')
        self.assertEqual(speak.clean('Rode `/plugin install speak@cc-speaker` antes.'), 'Rode barra plugin install antes.')
        self.assertEqual(speak.clean('Rode `/speak`'), 'Rode barra speak')
        self.assertEqual(speak.full_text('Para cortar, o `/speak stop`.'), 'Para cortar, o barra speak stop.')

    def test_versions_are_read_digit_by_digit(self):
        self.assertEqual(speak.clean('atualizei da versão 0.9.1 para a 0.9.2'),
                         'atualizei da versão 0 ponto 9 ponto 1 para a 0 ponto 9 ponto 2')
        self.assertEqual(speak.clean('atualizei da versão `0.9.1` para a `v0.9.2`.'),
                         'atualizei da versão 0 ponto 9 ponto 1 para a 0 ponto 9 ponto 2.')
        self.assertEqual(speak.clean('Claude Code `2.1.312` e 1.5 e 1.2.3.4.'),
                         'Claude Code 2 ponto 1 ponto 312 e 1 ponto 5 e 1 ponto 2 ponto 3 ponto 4.')
        self.assertEqual(speak.clean('Em 2026-10-29 sim, commit b48e609 sai.'), 'Em 2026-10-29 sim, commit sai.')
        self.assertEqual(speak.clean('Rode `speak update` na 0.9.1.'), 'Rode speak update na 0 ponto 9 ponto 1.')
        self.assertEqual(speak.clean('e 1.2.3.4.5 ficam'), 'e 1.2.3.4.5 ficam')

    def test_paths_still_go(self):
        for path in ('/home/x/y', '~/.claude/x', 'dir/arquivo', '/tmp/a.txt', './bin/speak', '../x', '/usr/bin/env',
                     'https://x.y/speak'):
            self.assertEqual(speak.clean('Veja %s agora.' % path), 'Veja agora.', path)
            self.assertEqual(speak.clean('Veja `%s` agora.' % path), 'Veja agora.', path)
        self.assertEqual(speak.clean('Veja `/home/x` e /home/x/y.'), 'Veja e')

    def test_a_one_level_path_reads_as_a_command(self):
        self.assertEqual(speak.clean('Veja /tmp agora.'), 'Veja barra tmp agora.')

    def test_portuguese_compounds_stay(self):
        self.assertEqual(speak.clean('O alto-falante e o guarda-costas'), 'O alto-falante e o guarda-costas')


class Ahead(unittest.TestCase):
    """The next piece is synthesized while the current one plays, so no silence falls between pieces."""

    def setUp(self):
        isolation.guard_workers(self)

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


class FakeClock:
    """A clock that only moves when a fake engine says it spent time."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def timed_engine(clock, cost, seconds, log=None):
    """A fake synth: each piece takes `cost` seconds on `clock` and yields `seconds` of audio (the sample IS the
    duration, see the `duration` argument of synthesize_ahead)."""
    def synth(piece):
        clock.now += cost
        if log is not None:
            log.append(piece)
        return seconds
    return synth


class Deliver(unittest.TestCase):
    """The pure decision: start (or restart) playing now, or wait for more audio to be ready?"""

    def test_fast_machine_delivers_at_once(self):
        self.assertTrue(speak.enough_buffered(1.0, 100.0, 2.0))

    def test_nothing_left_to_generate_delivers(self):
        self.assertTrue(speak.enough_buffered(0.0, 0.0, 0.1))

    def test_slow_machine_waits_for_enough_audio(self):
        rm = 0.5 * speak.SAFETY
        need = 12.0 * (1 - rm) / rm
        self.assertFalse(speak.enough_buffered(need - 0.01, 12.0, 0.5))
        self.assertTrue(speak.enough_buffered(need + 0.01, 12.0, 0.5))

    def test_boundary_of_the_formula(self):
        rm = 0.6 * speak.SAFETY
        need = 10.0 * (1 - rm) / rm
        self.assertTrue(speak.enough_buffered(need, 10.0, 0.6))
        # the margin: a rate of exactly 1 is not enough to count as fast, only 1 / SAFETY is
        self.assertTrue(speak.enough_buffered(0.0, 10.0, 1 / speak.SAFETY))
        self.assertFalse(speak.enough_buffered(0.0, 10.0, 1.0))

    def test_zero_rate_waits_until_the_end(self):
        self.assertFalse(speak.enough_buffered(50.0, 1.0, 0.0))


class AdaptiveWait(unittest.TestCase):
    """The generator holds the speech back while the engine is slower than speech, then plays it through."""

    def setUp(self):
        isolation.guard_workers(self)

    def test_fast_engine_delivers_the_first_piece_without_waiting_for_the_others(self):
        import threading
        clock, release = FakeClock(), threading.Event()
        quick = timed_engine(clock, 1.0, 4.0)

        def synth(piece):
            if piece != 'a' * 100:
                release.wait(5)  # the other pieces are not ready while the first is asked for
            return quick(piece)

        gen = speak.synthesize_ahead(['a' * 100, 'b' * 100, 'c' * 100], synth, clock=clock, duration=lambda s: s)
        try:
            self.assertEqual(next(gen), 4.0)
        finally:
            release.set()
            gen.close()

    def test_slow_engine_holds_the_first_piece_until_the_criterion_holds(self):
        clock, log = FakeClock(), []
        texts = [c * 100 for c in 'abcd']
        gen = speak.synthesize_ahead(texts, timed_engine(clock, 8.0, 4.0, log), clock=clock, duration=lambda s: s)
        first = next(gen)
        # rate 0.5: with 1 or 2 pieces ready the buffer is short of the 16.2 s and 10.8 s needed; 3 pieces do it
        self.assertGreaterEqual(len(log), 3)
        self.assertEqual(first, 4.0)
        self.assertEqual(list(gen), [4.0, 4.0, 4.0])
        self.assertEqual(log, texts)

    def test_order_is_kept(self):
        clock = FakeClock()
        seconds = {'a' * 50: 1.0, 'b' * 50: 2.0, 'c' * 50: 3.0}
        gen = speak.synthesize_ahead(list(seconds), lambda p: clock.__setattr__('now', clock.now + 5) or seconds[p],
                                     clock=clock, duration=lambda s: s)
        self.assertEqual(list(gen), [1.0, 2.0, 3.0])

    def test_an_error_after_a_slow_start_still_delivers_the_ready_pieces_then_raises(self):
        clock = FakeClock()

        def synth(piece):
            clock.now += 8.0
            if piece == 'c' * 100:
                raise ValueError('motor falhou')
            return 4.0

        got = []
        with self.assertRaises(ValueError):
            for samples in speak.synthesize_ahead(['a' * 100, 'b' * 100, 'c' * 100, 'd' * 100], synth,
                                                  clock=clock, duration=lambda s: s):
                got.append(samples)
        self.assertEqual(got, [4.0, 4.0])

    def test_closing_stops_the_generation_between_pieces(self):
        import threading
        clock, release, calls = FakeClock(), threading.Event(), []

        def synth(piece):
            calls.append(piece)
            if len(calls) > 2:
                release.wait(5)
            clock.now += 0.1
            return 4.0

        gen = speak.synthesize_ahead(['p%d' % i * 50 for i in range(50)], synth, clock=clock, duration=lambda s: s)
        self.assertEqual(next(gen), 4.0)
        gen.close()
        release.set()
        time.sleep(0.3)
        self.assertLessEqual(len(calls), 3)


def fake_claude(path):
    """A program named `claude` that is not the Python interpreter: a copy of the system shell. A symlink to Python
    would not do on the Mac, where python3 is a stub that re-executes `.../Python.app/Contents/MacOS/Python` and the
    process then shows that name, as it never would for the real Claude Code (a binary called `claude`)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy('/bin/sh', path)
    return path


def run_under_claude(fake, code, *args, **kw):
    """Runs `python -I -c code args...` as a child of the fake claude (which waits for it and does not exec it)."""
    return subprocess.run([fake, '-c', '"$@"; exit $?', 'sh', sys.executable, '-I', '-c', code, *args], **kw)


@unittest.skipUnless(sys.platform.startswith('linux'),
                     'pw-play, paplay and aplay are the Linux players; the Mac plays with afplay')
class Player(unittest.TestCase):
    """The player is the first one on PATH that takes raw samples: `pw-play --raw` came with PipeWire 1.1, so an
    older pw-play (1.0.x, Ubuntu 24.04) is skipped in favour of paplay or aplay."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = os.path.join(self.tmp, 'bin')
        os.makedirs(self.bin)
        self.old_path = os.environ.get('PATH')
        os.environ['PATH'] = self.bin
        self.addCleanup(os.environ.__setitem__, 'PATH', self.old_path or '')

    def fake(self, name, help_text=''):
        """A program on PATH whose `--help` prints `help_text` (pw-play prints its usage on stderr)."""
        path = os.path.join(self.bin, name)
        with open(path, 'w') as f:  # only shell builtins: the test PATH holds nothing else
            f.write('#!/bin/sh\nwhile read -r line; do echo "$line" >&2; done <<"HELP"\n%sHELP\n' % help_text)
        os.chmod(path, 0o755)
        return path

    def test_old_pw_play_without_raw_is_skipped(self):
        self.fake('pw-play', 'pw-play [options] [<file>|-]\n  -h, --help\n')
        self.fake('aplay')
        self.assertEqual(speak.player_command()[0], 'aplay')
        self.assertTrue(speak.player_found())

    def test_new_pw_play_with_raw_is_chosen(self):
        self.fake('pw-play', 'pw-play [options] [<file>|-]\n  -h, --help\n      --raw  RAW mode\n')
        self.fake('aplay')
        self.assertEqual(speak.player_command()[0], 'pw-play')

    def test_only_an_old_pw_play_means_no_player(self):
        self.fake('pw-play', 'pw-play [options]\n  -h, --help\n')
        self.assertIsNone(speak.player_command())
        self.assertFalse(speak.player_found())

    def test_paplay_and_aplay_need_no_check(self):
        self.fake('aplay')
        self.assertEqual(speak.player_command()[0], 'aplay')


class Microphone(unittest.TestCase):
    def setUp(self):
        no_leaked_watcher(self)

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
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_WAIT_POLL', 0), \
                mock.patch.object(speak, 'current_recordings', side_effect=lambda: seen.pop(0)):
            self.assertTrue(speak.wait_turn(None, True))
        self.assertEqual(seen, [])  # looked three times: two busy, then free
        with open(speak.PID) as fh:
            self.assertEqual(fh.read(), str(os.getpid()))
        self.assertEqual(os.listdir(speak.QUEUE), [])

    def wait_in_thread(self, session):
        """Runs wait_turn(session, True) in a thread; returns (thread, result list)."""
        import threading
        result = []
        thread = threading.Thread(target=lambda: result.append(speak.wait_turn(session, True)), daemon=True)
        thread.start()
        return thread, result

    def test_the_wait_reads_the_microphone_once_per_interval(self):
        import time
        from unittest import mock
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        isolate(self, root)
        held = [True]
        reads = []
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_WAIT_POLL', 0.3), \
                mock.patch.object(speak, 'playing', side_effect=lambda: 123 if held[0] else None), \
                mock.patch.object(speak, 'current_recordings', side_effect=lambda: reads.append(time.monotonic()) or set()):
            thread, result = self.wait_in_thread(None)
            time.sleep(0.7)  # about seventy laps of the queue, held by another speech
            held[0] = False
            thread.join(5)
        self.assertEqual(result, [True])
        # readings at 0, 0.3 and 0.6 s, plus the fresh one before taking the turn: never one per lap
        self.assertLessEqual(len(reads), 5)
        self.assertGreaterEqual(len(reads), 3)
        speak.clear_speech(os.getpid())

    def test_the_turn_is_not_taken_on_an_old_reading_of_the_microphone(self):
        import time
        from unittest import mock
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        isolate(self, root)
        me = speak.session_key(os.getpid())
        speak.set_session(me, mic='wait')
        held = [True]
        busy = [False]
        reads = []
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_WAIT_POLL', 0.4), \
                mock.patch.object(speak, 'playing', side_effect=lambda: 123 if held[0] else None), \
                mock.patch.object(speak, 'current_recordings',
                                  side_effect=lambda: reads.append(1) or ({7} if busy[0] else set())):
            thread, result = self.wait_in_thread(me)
            time.sleep(0.1)  # the stored reading says free
            busy[0] = True  # a recording begins; the stored reading does not know
            held[0] = False  # the other speech ends: this one would be the head
            time.sleep(0.15)
            self.assertEqual(result, [])  # the fresh reading found it busy: no turn
            self.assertFalse(os.path.exists(speak.PID))
            self.assertEqual(len(reads), 2)  # the first one and the fresh one
            busy[0] = False
            thread.join(5)  # the next scheduled reading finds it free
        self.assertEqual(result, [True])
        speak.clear_speech(os.getpid())

    def test_watch_cuts_on_any_recording(self):
        import threading
        from unittest import mock
        done = threading.Event()
        player = object()
        with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', return_value={7}), \
                mock.patch.object(speak, 'cut_by_microphone', side_effect=lambda p: done.set()) as cut:
            stop, thread = speak.watch_microphone(player)
            self.assertTrue(done.wait(2))
            stop.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
        cut.assert_called_with(player)

    def test_watch_stops_when_the_speech_ends(self):
        from unittest import mock
        with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', return_value=set()):
            stop, thread = speak.watch_microphone(object())
            self.assertTrue(thread.is_alive())
            speak.stop_watching((stop, thread))
        self.assertFalse(thread.is_alive())


class Dictation(unittest.TestCase):
    """The dictation of Claude Code (holding the space bar) shows in pw-dump as `PipeWire ALSA [<process name>]` /
    `alsa_capture.<process name>`, the name being that of a live `claude` process. In `play` and `auto` only it holds
    and cuts the speech; `wait` is as ever. The data are from a real pw-dump (Ubuntu 26.04, Claude Code 2.1.312)."""
    NAME = '2.1.312'

    def setUp(self):
        no_leaked_watcher(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        self.me = speak.session_key(os.getpid())
        from unittest import mock
        system = mock.patch.object(speak.speak_os, 'SYSTEM', 'linux')  # these tests see the machine as Linux does
        system.start()
        self.addCleanup(system.stop)

    @staticmethod
    def stream(ident, app, node_name, binary=None):
        props = {'media.class': 'Stream/Input/Audio', 'application.name': app, 'node.name': node_name}
        if binary:
            props.update({'application.process.binary': binary, 'application.process.id': 1044783})
        return {'id': ident, 'info': {'props': props}}

    def dump(self, discord=False, dictation=False, other=False):
        nodes = [{'id': 5, 'info': {'props': {'media.class': 'Audio/Source'}}}]
        if discord:
            nodes.append(self.stream(94, 'WEBRTC VoiceEngine', 'WEBRTC VoiceEngine', 'Discord'))
        if dictation:
            nodes.append(self.stream(72, 'PipeWire ALSA [%s]' % self.NAME, 'alsa_capture.%s' % self.NAME))
        if other:
            nodes.append(self.stream(80, 'PipeWire ALSA [firefox]', 'alsa_capture.firefox'))
        return json.dumps(nodes)

    def read(self, **kinds):
        """What speak reads from a fake pw-dump while a `claude` process called NAME is alive."""
        from unittest import mock
        done = subprocess.CompletedProcess([], 0, self.dump(**kinds).encode(), b'')
        with mock.patch.object(speak.speak_os, 'SYSTEM', 'linux'), \
                mock.patch.object(speak.speak_os, 'claude_names', return_value={self.NAME}), \
                mock.patch.object(speak.speak_os.subprocess, 'run', return_value=done):
            return speak.current_recordings()

    def test_the_dictation_is_told_from_the_meeting(self):
        recs = self.read(discord=True, dictation=True, other=True)
        self.assertEqual(recs, {94, 72, 80})  # still a set of every recording
        self.assertEqual(recs.dictation, {72})
        self.assertEqual(self.read(discord=True).dictation, set())
        self.assertEqual(self.read(), set())

    def test_by_the_node_name_alone_too(self):
        from unittest import mock
        nodes = [self.stream(7, 'ALSA plug-in', 'alsa_capture.%s' % self.NAME)]
        with mock.patch.object(speak.speak_os, 'claude_names', return_value={self.NAME}):
            self.assertEqual(speak.speak_os.recordings(json.dumps(nodes)).dictation, {7})
        with mock.patch.object(speak.speak_os, 'claude_names', return_value={'9.9.9'}):
            self.assertEqual(speak.speak_os.recordings(json.dumps(nodes)).dictation, set())

    def test_processes_are_read_only_when_a_stream_looks_like_alsa(self):
        from unittest import mock
        with mock.patch.object(speak.speak_os, 'claude_names', side_effect=AssertionError('read')):
            self.assertEqual(speak.speak_os.recordings(self.dump(discord=True)), {94})

    @unittest.skipIf(sys.platform == 'darwin', 'the names are read from /proc')
    def test_claude_names_come_from_a_process_made_by_the_test(self):
        bin_dir = tempfile.mkdtemp(dir=self.tmp.name)
        fake = os.path.join(bin_dir, '8.8.8-teste')  # the native build is named by its version, argv[0] is `claude`
        os.symlink(os.path.realpath(sys.executable), fake)  # comm is the name it was started by
        proc = subprocess.Popen(['claude', '-I', '-c', 'import time; time.sleep(60)'], executable=fake)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        end = time.time() + 5
        while time.time() < end and '8.8.8-teste' not in speak.speak_os.claude_names():
            time.sleep(0.05)
        self.assertIn('8.8.8-teste', speak.speak_os.claude_names())
        proc.kill()
        proc.wait()
        self.assertNotIn('8.8.8-teste', speak.speak_os.claude_names())

    def test_the_mac_cannot_tell_who_records(self):
        from unittest import mock
        with mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'):
            self.assertEqual(speak.speak_os.claude_names(), set())
        for choice in ('play', 'auto', 'wait'):
            speak.set_session(self.me, mic=choice)  # written as on Linux; only the reading of the microphone is the Mac's
            with mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'):
                self.assertEqual(speak.holds_with(self.me, {'input'}), choice == 'wait', choice)
                self.assertEqual(speak.ticket_holds(self.me, {'input'}), choice == 'wait', choice)
        speak.set_session(self.me, mic='play')
        with mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'), \
                mock.patch.object(speak, 'current_recordings', return_value={'input'}):
            self.assertFalse(speak.holds_for_microphone(self.me))

    def test_play_and_auto_hold_only_for_the_dictation_wait_for_any(self):
        cases = {  # (meeting, dictation, both) -> holds
            'wait': (True, True, True), 'play': (False, True, True), 'auto': (False, True, True)}
        for choice, (meeting, dictation, both) in cases.items():
            speak.set_session(self.me, mic=choice)
            for kinds, expected in ((dict(discord=True), meeting), (dict(dictation=True), dictation),
                                    (dict(discord=True, dictation=True), both), ({}, False)):
                recs = self.read(**kinds)
                self.assertEqual(speak.holds_with(self.me, recs), expected, (choice, kinds))
                self.assertEqual(speak.ticket_holds(self.me, recs), expected, (choice, kinds))
        self.assertTrue(speak.ticket_holds('', self.read(discord=True)))  # no session in the ticket: wait
        self.assertFalse(speak.ticket_holds(self.me, self.read(other=True)))  # another program's ALSA is not it

    def test_a_ticket_of_another_session_follows_that_sessions_choice(self):
        speak.set_session(self.me, mic='play')
        recs = self.read(discord=True)
        self.assertFalse(speak.ticket_holds(self.me, recs))
        self.assertTrue(speak.ticket_holds('', recs))
        self.assertTrue(speak.ticket_holds(self.me, self.read(discord=True, dictation=True)))

    def test_the_turn_in_play_comes_with_the_meeting_and_waits_for_the_dictation(self):
        from unittest import mock
        speak.set_session(self.me, mic='play')
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', return_value=self.read(discord=True)):
            self.assertTrue(speak.wait_turn(self.me, True))
        speak.clear_speech(os.getpid())
        seen = [self.read(discord=True, dictation=True), self.read(discord=True, dictation=True), self.read(discord=True)]
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_WAIT_POLL', 0), \
                mock.patch.object(speak, 'current_recordings', side_effect=lambda: seen.pop(0)):
            self.assertTrue(speak.wait_turn(self.me, True))
        self.assertEqual(seen, [])  # two laps held by the dictation, then it let go (the meeting went on)
        speak.clear_speech(os.getpid())
        speak.drop_own_tickets()

    def test_the_watcher_cuts_in_play_only_for_the_dictation(self):
        import threading
        from unittest import mock
        speak.set_session(self.me, mic='play')
        for kinds, cuts in ((dict(discord=True), False), (dict(discord=True, dictation=True), True)):
            done = threading.Event()
            with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                    mock.patch.object(speak, 'current_recordings', return_value=self.read(**kinds)), \
                    mock.patch.object(speak, 'cut_by_microphone', side_effect=lambda p: done.set()):
                watcher = speak.watch_microphone(object(), self.me)
                self.assertEqual(done.wait(0.5), cuts, kinds)
                speak.stop_watching(watcher)

    def test_auto_does_not_take_the_dictation_for_a_meeting(self):
        speak.set_session(self.me, mic='auto')
        speak.track_mic(self.me, self.read(dictation=True))
        self.assertNotIn('micseen', speak.read_session(self.me))
        speak.track_mic(self.me, self.read(discord=True, dictation=True))  # a meeting starts, with dictation going on
        self.assertTrue(speak.read_session(self.me).get('micseen'))
        speak.track_mic(self.me, self.read(dictation=True))  # the meeting ends while the user still dictates
        self.assertEqual(speak.mic(self.me), 'wait')


class MicChoice(unittest.TestCase):
    """`speak mic wait|play|auto`: wait (default) holds and cuts, play does neither, auto is play and goes back to wait
    when the microphone turns from busy to free, in the scope where it was written."""

    def setUp(self):
        no_leaked_watcher(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = isolate(self, self.tmp.name)
        self.sleep = subprocess.Popen(['sleep', '60'])
        self.addCleanup(self.sleep.wait)
        self.addCleanup(self.sleep.kill)
        self.me = speak.session_key(os.getpid())
        self.other = speak.session_key(self.sleep.pid)
        self.folder = data_dir(self.tmp.name, 'state', 'sessions')
        fake = os.path.join(self.tmp.name, 'fakebin')  # a pw-dump that always says nothing records
        os.makedirs(fake)
        with open(os.path.join(fake, 'pw-dump'), 'w') as fh:
            fh.write('#!/bin/sh\necho "[]"\n')
        os.chmod(os.path.join(fake, 'pw-dump'), 0o755)
        self.env = {'HOME': self.tmp.name, 'PATH': fake + ':/usr/bin:/bin', 'REAL_SPEAK': SPEAK,
                    'BUSY_FILE': os.path.join(self.tmp.name, 'busy')}
        self.mac_driver = os.path.join(self.tmp.name, 'mac_driver.py')  # the Mac asks CoreAudio, not pw-dump
        with open(self.mac_driver, 'w') as fh:
            fh.write(self.MAC_DRIVER)

    MAC_DRIVER = (
        'import importlib.machinery, importlib.util, os, sys\n'
        'loader = importlib.machinery.SourceFileLoader("speak", os.environ["REAL_SPEAK"])\n'
        'm = importlib.util.module_from_spec(importlib.util.spec_from_loader("speak", loader)); loader.exec_module(m)\n'
        'm.current_recordings = lambda: {9} if os.path.exists(os.environ["BUSY_FILE"]) else set()\n'
        'sys.exit(m.main(sys.argv[1:]))\n')

    def make_busy(self):
        """A microphone in use, as the system sees it: a pw-dump with a recording stream, or (Mac) a busy file."""
        if sys.platform == 'darwin':
            open(self.env['BUSY_FILE'], 'w').close()
            return
        with open(os.path.join(self.tmp.name, 'fakebin', 'pw-dump'), 'w') as fh:
            fh.write('#!/bin/sh\necho \'[{"id":9,"info":{"props":{"media.class":"Stream/Input/Audio"}}}]\'\n')

    def run_speak(self, *args, session=None, **env):
        script = self.mac_driver if sys.platform == 'darwin' else SPEAK
        return subprocess.run([sys.executable, '-I', script, *args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env={**self.env, 'CLAUDE_SPEAK_SESSION': session or '-', **env})

    def general(self):
        try:
            with open(speak.MIC_FILE) as fh:
                return fh.read().strip()
        except OSError:
            return None

    def session_file(self, key):
        return speak_read(self.folder, key) if os.path.exists(os.path.join(self.folder, key)) else {}

    def test_default_is_wait_and_the_value_is_validated(self):
        self.assertEqual(speak.mic(None), 'wait')
        for args in (('mic',), ('mic', 'toca'), ('mic', 'play', 'tudo')):
            r = self.run_speak(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn('voz:', r.stderr)

    def test_status_and_json_say_it_with_the_scope(self):
        self.assertIn('microfone em uso: espera\n', self.run_speak('status', session=self.me).stdout)
        self.run_speak('mic', 'play', session=self.me)
        out = self.run_speak('status', session=self.me).stdout
        self.assertIn('microfone em uso: toca \u00b7 s\u00f3 nesta sess\u00e3o', out)
        data = json.loads(self.run_speak('status', '--json', session=self.me).stdout)
        self.assertEqual((data['mic'], data['scope']['mic']), ('play', 'session'))
        other = json.loads(self.run_speak('status', '--json', session=self.other).stdout)
        self.assertEqual((other['mic'], other['scope']['mic']), ('wait', 'all'))
        self.run_speak('mic', 'auto', 'all', session=self.me)
        both = [json.loads(self.run_speak('status', '--json', session=k).stdout) for k in (self.me, self.other)]
        self.assertEqual([(d['mic'], d['scope']['mic']) for d in both], [('auto', 'all')] * 2)
        self.assertIn('toca nesta reuni\u00e3o', self.run_speak('status', session=self.me).stdout)

    def test_session_choice_stays_and_all_removes_it_from_the_sessions(self):
        self.run_speak('mic', 'play', session=self.me)
        self.assertEqual(self.session_file(self.me), {'mic': 'play'})
        self.assertIsNone(self.general())
        self.run_speak('mic', 'auto', 'all', session=self.me)
        self.assertEqual(self.session_file(self.me), {})
        self.assertEqual(self.general(), 'auto')

    def test_variable_beats_everything(self):
        self.run_speak('mic', 'play')
        data = json.loads(self.run_speak('status', '--json', CLAUDE_SPEAK_MIC='wait').stdout)
        self.assertEqual(data['mic'], 'wait')

    def test_wait_holds_the_turn_play_and_auto_do_not(self):
        from unittest import mock
        for choice, waits in (('wait', True), ('play', False), ('auto', False)):
            speak.set_session(self.me, mic=choice)
            with mock.patch.object(speak, 'current_recordings', return_value={7}):
                self.assertEqual(speak.holds_for_microphone(self.me), waits, choice)
        speak.set_session(self.me, mic='wait')
        with mock.patch.object(speak, 'current_recordings', return_value=set()):
            self.assertFalse(speak.holds_for_microphone(self.me))

    def test_play_on_the_mac_does_not_even_look_at_the_microphone(self):
        from unittest import mock
        speak.set_session(self.me, mic='play')
        with mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'), \
                mock.patch.object(speak, 'current_recordings', side_effect=AssertionError('looked')):
            self.assertFalse(speak.holds_for_microphone(self.me))

    def test_turn_comes_at_once_with_play_while_recording(self):
        from unittest import mock
        speak.set_session(self.me, mic='play')
        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'current_recordings', return_value={7}):
            self.assertTrue(speak.wait_turn(self.me, True))
        speak.drop_own_tickets()

    def three_sessions(self):
        """Three live session keys (this process, the test's sleep and another sleep of its own)."""
        extra = subprocess.Popen(['sleep', '60'])
        self.addCleanup(extra.wait)
        self.addCleanup(extra.kill)
        return self.me, self.other, speak.session_key(extra.pid)

    def run_turns(self, sessions, busy_now, free_after):
        """Joins the queue with one speech per session, in order (fake microphone, no player), and returns the order in
        which they took the turn. `busy_now`: the microphone is busy at first; `free_after`: how many turns must go
        before it is freed (None: it stays busy until the first `wait` that is left alone)."""
        import threading
        import time
        from unittest import mock
        busy = [busy_now]
        order = []
        threads = []

        def queued():
            try:
                return len(os.listdir(speak.QUEUE))
            except OSError:
                return 0

        def speech(key):
            if speak.wait_turn(key, True):
                order.append(key)

        with mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_WAIT_POLL', 0), \
                mock.patch.object(speak, 'current_recordings', side_effect=lambda: {7} if busy[0] else set()):
            for key in sessions:
                before = queued() + len(order)
                thread = threading.Thread(target=speech, args=(key,), daemon=True)
                thread.start()
                threads.append(thread)
                for _ in range(200):
                    if queued() + len(order) > before:
                        break
                    time.sleep(0.01)
            deadline = time.time() + 5
            while len(order) < free_after and time.time() < deadline:
                time.sleep(0.01)
            busy[0] = False
            for thread in threads:
                thread.join(5)
        speak.drop_own_tickets()
        return order

    def test_a_speech_that_waits_for_the_microphone_does_not_hold_the_ones_behind(self):
        a, b, c = self.three_sessions()
        speak.set_session(a, mic='wait')
        speak.set_session(b, mic='play')
        speak.set_session(c, mic='play')
        # A arrived first, B behind: B plays while the microphone is busy, A plays after it is free
        self.assertEqual(self.run_turns([a, b], True, 1), [b, a])
        # three speeches: B and C play in order, then A
        self.assertEqual(self.run_turns([a, b, c], True, 2), [b, c, a])

    def test_with_the_microphone_free_the_order_is_the_order_of_arrival(self):
        a, b, c = self.three_sessions()
        speak.set_session(a, mic='wait')
        speak.set_session(b, mic='play')
        speak.set_session(c, mic='wait')
        self.assertEqual(self.run_turns([a, b, c], False, 0), [a, b, c])

    def test_a_ticket_without_session_counts_as_wait(self):
        speak.set_session(self.other, mic='play')
        self.assertTrue(speak.ticket_holds('', {7}))
        self.assertFalse(speak.ticket_holds('', set()))
        self.assertFalse(speak.ticket_holds(self.other, {7}))
        self.assertTrue(speak.ticket_holds(self.me, {7}))

    def test_watcher_cuts_only_on_wait(self):
        import threading
        from unittest import mock
        for choice, cuts in (('wait', True), ('play', False), ('auto', False)):
            speak.set_session(self.me, mic=choice)
            done = threading.Event()
            with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                    mock.patch.object(speak, 'current_recordings', return_value={7}), \
                    mock.patch.object(speak, 'cut_by_microphone', side_effect=lambda p: done.set()):
                watcher = speak.watch_microphone(object(), self.me)
                self.assertEqual(done.wait(0.5), cuts, choice)
                speak.stop_watching(watcher)

    def test_the_watcher_follows_a_change_made_while_it_speaks(self):
        import threading
        from unittest import mock
        speak.set_session(self.me, mic='play')
        done = threading.Event()
        with mock.patch.object(speak, 'MIC_POLL', 0.01), \
                mock.patch.object(speak, 'current_recordings', return_value={7}), \
                mock.patch.object(speak, 'cut_by_microphone', side_effect=lambda p: done.set()):
            watcher = speak.watch_microphone(object(), self.me)
            self.assertFalse(done.wait(0.1))
            speak.set_session(self.me, mic='wait')
            self.assertTrue(done.wait(2))
            speak.stop_watching(watcher)

    def test_auto_of_a_session_goes_back_to_wait_in_the_session_when_the_meeting_ends(self):
        speak.set_session(self.me, mic='auto', mode='full')
        speak.track_mic(self.me, set())  # free and never seen busy: stays
        self.assertEqual(speak.mic(self.me), 'auto')
        speak.track_mic(self.me, None)  # could not be read: nothing changes
        speak.track_mic(self.me, {7})
        self.assertEqual(self.session_file(self.me), {'mic': 'auto', 'mode': 'full', 'micseen': True})
        speak.track_mic(self.me, {7})
        self.assertEqual(speak.mic(self.me), 'auto')
        speak.track_mic(self.me, set())
        self.assertEqual(self.session_file(self.me), {'mic': 'wait', 'mode': 'full'})
        self.assertIsNone(self.general())  # the general setting was never touched
        self.assertFalse(os.path.exists(speak.MIC_SEEN))

    def test_auto_of_all_goes_back_to_wait_for_all_and_the_other_session_is_not_touched(self):
        speak.set_session(self.other, mic='play')
        os.makedirs(os.path.dirname(speak.MIC_FILE), exist_ok=True)
        with open(speak.MIC_FILE, 'w') as fh:
            fh.write('auto\n')
        speak.track_mic(self.me, {7})
        self.assertTrue(os.path.exists(speak.MIC_SEEN))
        self.assertEqual(self.session_file(self.me), {})
        speak.track_mic(self.me, set())
        self.assertEqual(self.general(), 'wait')
        self.assertFalse(os.path.exists(speak.MIC_SEEN))
        self.assertEqual(self.session_file(self.other), {'mic': 'play'})

    def test_auto_chosen_with_the_microphone_free_waits_for_the_next_meeting(self):
        r = self.run_speak('mic', 'auto', 'all')  # the microphone is free (fake pw-dump; on the Mac, no busy file)
        self.assertEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(speak.MIC_SEEN))
        speak.track_mic(None, set())
        self.assertEqual(self.general(), 'auto')
        speak.track_mic(None, {7})  # the next meeting begins ...
        speak.track_mic(None, set())  # ... and ends
        self.assertEqual(self.general(), 'wait')

    def test_auto_chosen_in_the_middle_of_the_meeting_counts_as_seen(self):
        self.make_busy()
        self.run_speak('mic', 'auto', 'all')
        self.assertTrue(os.path.exists(speak.MIC_SEEN))
        self.run_speak('mic', 'play', 'all')  # a new choice forgets what was seen
        self.assertFalse(os.path.exists(speak.MIC_SEEN))

    def test_the_message_hook_tick_ends_the_meeting(self):
        speak.set_session(self.me, mic='auto', micseen=True)
        r = self.run_speak('_mictick', session=self.me)  # the microphone is free (fake pw-dump; on the Mac, no busy file)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.session_file(self.me), {'mic': 'wait'})

    def test_tick_leaves_other_choices_alone(self):
        for choice in ('wait', 'play'):
            speak.set_session(self.me, mic=choice, micseen=True)
            self.run_speak('_mictick', session=self.me)
            self.assertEqual(speak.mic(self.me), choice)


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
        self.assertTrue(os.path.exists(data_dir(self.home, 'engine', 'kokoro-v1.0.onnx')))
        self.assertTrue(os.path.exists(data_dir(self.home, 'config', 'off')))
        with open(data_dir(self.home, 'config', 'mode')) as fh:
            self.assertEqual(fh.read().strip(), 'summary')
        for old in ('.local/share', '.config', '.local/state'):
            self.assertFalse(os.path.exists(self.path(old, 'claude-voz')), old)
        self.assertFalse(os.path.exists(data_dir(self.home, 'state', 'sessoes')))

    def test_old_state_marker_and_leftovers(self):
        for name in ('tudo', 'fala.pid', 'fala.dono', 'erro.log', 'fala-123.wav', 'fala-9.wav'):
            self.put(self.path('.local', 'state', 'claude-voz', name), 'x')
        self.speak('status')
        folder = data_dir(self.home, 'state')
        self.assertTrue(os.path.exists(os.path.join(folder, 'all')))
        for name in ('tudo', 'fala.pid', 'fala.dono', 'erro.log', 'fala-123.wav', 'fala-9.wav'):
            self.assertFalse(os.path.exists(os.path.join(folder, name)), name)

    def test_old_mode_completo_becomes_full(self):
        self.put(self.path('.config', 'claude-voz', 'modo'), 'completo\n')
        self.assertIn('modo: full', self.speak('status').stdout)
        with open(data_dir(self.home, 'config', 'mode')) as fh:
            self.assertEqual(fh.read().strip(), 'full')
        self.assertFalse(os.path.exists(data_dir(self.home, 'config', 'modo')))

    def test_new_folder_wins_and_old_is_left(self):
        self.put(self.path('.config', 'claude-voz', 'desligado'))
        os.makedirs(data_dir(self.home, 'config'))
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
        self.assertTrue(os.path.exists(data_dir(self.tmp.name, 'config', 'off')))
        self.assertIn('voz: ligada', self.speak('on').stdout)

    def test_session_switch(self):
        out = self.speak('status', CLAUDE_SPEAK='0').stdout
        self.assertIn('voz: desligada', out)
        self.assertIn('CLAUDE_SPEAK=0', out)

    def test_mode_defaults_to_summary_and_is_kept(self):
        self.assertIn('modo: summary', self.speak('status').stdout)
        self.assertIn('modo: full', self.speak('mode', 'full').stdout)
        self.assertIn('modo: full', self.speak('status').stdout)
        self.assertIn('modo: summary', self.speak('status', CLAUDE_SPEAK_MODE='summary').stdout)
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
    return speak.speak_os.started(os.getpid())


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
        mark = data_dir(self.tmp.name, 'state', 'all')
        before = speak.session_started(self.other) - 3600
        os.utime(mark, (before, before))
        self.assertIn('voz: desligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)

    def test_mode_here_does_not_touch_other_sessions(self):
        self.speak('mode', 'full', session=self.me)
        mine = self.speak('status', session=self.me).stdout
        self.assertIn('modo full', mine)
        self.assertIn('modo: full \u00b7 s\u00f3 nesta sess\u00e3o', mine)
        other = self.speak('status', session=self.other).stdout
        self.assertIn('modo: summary', other)
        self.assertIn('esta sessão: segue a geral, modo segue o geral', other)

    def test_mode_all_sets_every_session_and_the_general(self):
        self.speak('mode', 'summary', session=self.other)
        self.speak('mode', 'full', 'all', session=self.me)
        other = self.speak('status', session=self.other).stdout  # its own choice was removed, not copied
        self.assertIn('modo segue o geral', other)
        self.assertIn('modo: full\n', other)
        self.assertIn('modo: full', self.speak('status', session=self.me).stdout)
        self.assertEqual(open(data_dir(self.tmp.name, 'config', 'mode')).read().strip(), 'full')

    def test_mode_outside_a_session_is_general(self):
        self.speak('mode', 'summary', session='-')
        self.assertIn('modo: summary', self.speak('status', session=self.me).stdout)

    def test_say_uses_the_session_mode(self):
        from unittest import mock
        heard = []
        with mock.patch.dict(os.environ), \
                mock.patch.object(speak, 'speak_background', lambda text, session, how=None: heard.append((text, how)) or 0), \
                mock.patch.object(speak.sys, 'stdin', io.StringIO(REPLY)):
            for name in ('CLAUDE_SPEAK', 'CLAUDE_SPEAK_MODE'):
                os.environ.pop(name, None)
            os.environ['CLAUDE_SPEAK_SESSION'] = self.me
            speak.set_session(self.me, mode='summary')
            speak.main(['say', '-'])
        self.assertEqual(heard, [('Terminei a voz; falta você testar.', 'summary')])  # the mode goes with the speech

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
        self.assertTrue(os.path.exists(data_dir(self.tmp.name, 'config', 'off')))
        self.assertFalse(os.path.exists(data_dir(self.tmp.name, 'state', 'x')))
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
        fake = fake_claude(os.path.join(self.tmp.name, 'bin', 'claude'))

        def run(cmd):
            code = 'import subprocess,sys; print(subprocess.run(["sh","-c",sys.argv[1]],capture_output=True,text=True).stdout)'
            inner = '%s -I %s %s' % (sys.executable, SPEAK, cmd)
            return run_under_claude(fake, code, inner, capture_output=True, text=True, env=self.env).stdout

        status = run('status')
        self.assertIn('voz: ', status)
        self.assertNotIn('fora de uma sessão', status)
        run('off')
        self.assertTrue(any(n.split('-')[0].isdigit() for n in os.listdir(self.state)))

    def test_session_found_through_shells_pid(self):
        """The session file is named after the fake claude's own pid."""
        fake = fake_claude(os.path.join(self.tmp.name, 'bin', 'claude'))
        code = ('import subprocess,sys,os; print(os.getppid()); sys.stdout.flush();'
                'subprocess.run(["sh","-c",sys.argv[1]],capture_output=True,text=True)')
        inner = '%s -I %s off' % (sys.executable, SPEAK)
        out = run_under_claude(fake, code, inner, capture_output=True, text=True, env=self.env).stdout
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
        fake = fake_claude(os.path.join(self.tmp.name, 'claude'))
        code = ('import subprocess,sys,os,json; print(os.getppid()); sys.stdout.flush();'
                'subprocess.run(["sh","-c",sys.argv[1]],input=sys.argv[2].encode(),capture_output=True)')
        hook_cmd = '%s -I %s' % (sys.executable, hook)
        event = json.dumps({'last_assistant_message': 'Olá, tudo bem.'})
        out = run_under_claude(fake, code, hook_cmd, event, capture_output=True, text=True,
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
        self.assertTrue(os.path.exists(data_dir(self.tmp.name, 'config', 'off')))
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
        folder = data_dir(self.tmp.name, 'state')
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
        folder = data_dir(self.tmp.name, 'state')
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
        folder = data_dir(self.tmp.name, 'state')
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
        folder = data_dir(self.tmp.name, 'state')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'speech.pid'), 'w') as fh:
            fh.write(str(other.pid))
        self.speak('stop', session=self.me)
        self.assertFalse(self.ends(other, 0.5))

    def test_stop_without_argument_cuts_any_speech(self):
        speech = self.speech(self.other)
        self.speak('stop', session=self.me)
        self.assertTrue(self.ends(speech))

    def test_fim_corta_so_a_sessao(self):
        self.queue_setup()
        playing = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        theirs = self.waiter('b', self.other)
        mine = self.waiter('c', self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 2))
        self.speak('stop', 'here', session=self.me, **self.env)
        self.assertTrue(self.ends(playing, 5))
        self.assertTrue(self.ends(mine, 5))
        self.assertIsNone(theirs.poll())
        # B was neither cut nor dropped: it takes the turn (its ticket goes when it does, so counting tickets here
        # races with the player) and keeps running until released.
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.assertIsNone(theirs.poll())
        self.let_go('b')
        self.assertEqual(theirs.wait(timeout=5), 0)

    def cut_while_locked(self, change):
        """Runs stop_if_mine(me) in a thread while this test holds the queue lock, applies `change` (a swap of the
        speech files) under that lock, and releases it. Passes only if the cut reads the files under the lock."""
        import threading
        with speak.queue_lock():
            thread = threading.Thread(target=speak.stop_if_mine, args=(self.me,))
            thread.start()
            time.sleep(0.3)  # it is waiting for the lock (or, if the lock is missing, has already read the old files)
            change()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def write_state(self, name, text):
        with open(os.path.join(self.folder(), name), 'w') as fh:
            fh.write(text)

    def test_corte_com_troca_de_dono_entre_leitura_e_corte(self):
        mine = self.speech(self.me)
        theirs = self.speech(self.other)  # leaves the files naming `other` and its pid
        self.write_state('speech.pid', str(mine.pid))
        self.write_state('speech.owner', self.me)

        def swap():
            self.write_state('speech.pid', str(theirs.pid))
            self.write_state('speech.owner', self.other)
        self.cut_while_locked(swap)
        self.assertFalse(self.ends(theirs, 0.5))  # the speech that took over is spared
        self.assertIsNone(mine.poll())  # and the old one is not cut by mistake either

    def test_corte_com_dono_velho_e_pid_novo(self):
        theirs = self.speech(self.other)
        self.write_state('speech.owner', self.me)  # stale owner: the old speech died without clearing it
        self.write_state('speech.pid', '0')

        def take_over():  # wait_turn writes the pid first, then the owner
            self.write_state('speech.pid', str(theirs.pid))
            time.sleep(0.2)
            self.write_state('speech.owner', self.other)
        self.cut_while_locked(take_over)
        self.assertFalse(self.ends(theirs, 0.5))

    def test_fim_sem_fala(self):
        speech = self.speech(self.other)
        self.speak('status', session=self.me)  # the first call writes the one-time marker `scope`; settle it first
        before = sorted(n for n in os.listdir(self.folder()) if n != 'queue.lock')  # the lock file is empty bookkeeping
        r = self.speak('stop', 'here', session=self.me)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
        self.assertFalse(self.ends(speech, 0.5))
        self.assertEqual(sorted(n for n in os.listdir(self.folder()) if n != 'queue.lock'), before)

    def test_fim_fora_de_sessao_nao_corta_nada(self):
        speech = self.speech(self.other)
        r = self.speak('stop', 'here', session='-')
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.ends(speech, 0.5))

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
        return data_dir(self.tmp.name, 'state')

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
        'if sys.platform == "darwin":  # the Mac asks CoreAudio, not pw-dump: the same busy file stands in for it\n'
        '    m.current_recordings = lambda: {9} if os.path.exists(os.environ["BUSY_FILE"]) else set()\n'
        'if os.environ.get("DRIVER") == "play":\n'
        '    sys.exit(m.main(["_play", name]))\n'
        'if not m.wait_turn(m.current_session(), sys.platform == "darwin" or bool(m.shutil.which("pw-dump"))):\n'
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
                    'LOG_FILE': self.logfile, 'RELEASE': self.release, 'BUSY_FILE': self.busy}

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
        data = data_dir(self.tmp.name, 'engine')
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


class Pause(unittest.TestCase):
    """Pausing and resuming: real waiting processes (the fake driver of the queue tests, which runs speak's own
    wait_turn) frozen and continued by `speak pause` and `speak resume`. Nothing plays; sleep-like processes only."""
    DRIVER = Session.DRIVER
    speak = Session.speak
    folder = Session.folder
    queue_setup = Session.queue_setup
    waiter = Session.waiter
    started = Session.started
    until = Session.until
    tickets = Session.tickets
    let_go = Session.let_go
    ends = Session.ends

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
        self.queue_setup()
        self.addCleanup(self.cleanup_stop)  # helpers that wait for a turn must not outlive the test

    def cleanup_stop(self):
        self.speak('stop', session=self.me)

    def json(self):
        try:
            with open(os.path.join(self.folder(), 'speech.json')) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def stopped(self, pid):
        out = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
        return out.startswith('T')

    def children(self, pid):
        out = subprocess.run(['ps', '-axo', 'pid=,ppid='], capture_output=True, text=True).stdout
        return [int(a) for a, b in (line.split() for line in out.splitlines()) if int(b) == pid]

    def playing_pid(self):
        try:
            with open(os.path.join(self.folder(), 'speech.pid')) as fh:
                return int(fh.read())
        except (OSError, ValueError):
            return None

    def test_the_turn_is_written_with_session_folder_and_mode(self):
        proc = self.waiter('a', self.me, CLAUDE_SPEAK_DIR='/home/x/projeto', CLAUDE_SPEAK_HOW='summary')
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.assertEqual(self.json(), {'playing': {'pid': proc.pid, 'session': self.me, 'dir': '/home/x/projeto',
                                                   'how': 'summary'}, 'paused': []})
        self.let_go('a')
        self.assertEqual(proc.wait(timeout=5), 0)
        self.assertIsNone(self.json())  # nothing playing, nothing paused: no file

    def test_the_folder_comes_from_the_session_file_when_the_environment_has_none(self):
        speak.set_session(self.me, dir='/home/x/outro')
        self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.assertEqual(self.json()['playing']['dir'], '/home/x/outro')

    def test_pause_freezes_the_whole_group_and_frees_the_turn(self):
        script = os.path.join(tempfile.mkdtemp(dir=self.tmp.name), 'speak')
        with open(script, 'w') as fh:
            fh.write('import subprocess, time\nsubprocess.Popen(["sleep", "60"])\ntime.sleep(60)\n')
        proc = subprocess.Popen([sys.executable, '-I', script, '_play'], start_new_session=True)
        self.addCleanup(proc.wait)
        self.addCleanup(lambda: os.killpg(proc.pid, signal.SIGKILL))
        self.assertTrue(self.until(lambda: self.children(proc.pid)))
        child = self.children(proc.pid)[0]
        os.makedirs(self.folder(), exist_ok=True)
        for name, text in (('speech.pid', str(proc.pid)), ('speech.owner', self.me)):
            with open(os.path.join(self.folder(), name), 'w') as fh:
                fh.write(text)
        r = self.speak('pause', session=self.other)  # any session may pause
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'Fala pausada.'))
        self.assertTrue(self.until(lambda: self.stopped(proc.pid) and self.stopped(child)))
        for name in ('speech.pid', 'speech.owner'):
            self.assertFalse(os.path.exists(os.path.join(self.folder(), name)))
        paused = self.json()['paused']
        self.assertEqual([(p['pid'], p['session']) for p in paused], [(proc.pid, self.me)])
        self.assertIsNone(self.json()['playing'])

    def test_pause_with_nothing_playing_says_so(self):
        r = self.speak('pause', session=self.me)
        self.assertEqual(r.returncode, 1)
        self.assertIn('não há fala tocando', r.stderr)

    def test_pause_does_not_freeze_a_process_that_is_not_a_speech(self):
        other = subprocess.Popen(['sleep', '60'], start_new_session=True)
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        os.makedirs(self.folder(), exist_ok=True)
        with open(os.path.join(self.folder(), 'speech.pid'), 'w') as fh:
            fh.write(str(other.pid))
        self.assertEqual(self.speak('pause', session=self.me).returncode, 1)
        time.sleep(0.2)
        self.assertFalse(self.stopped(other.pid))

    def test_pause_refuses_arguments(self):
        for cmd in ('pause', 'resume'):
            r = self.speak(cmd, 'x', session=self.me)
            self.assertEqual(r.returncode, 2)
            self.assertIn('speak %s' % cmd, r.stderr)

    def test_the_next_speech_plays_while_the_first_is_paused(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        time.sleep(0.4)
        self.assertEqual(self.started(), ['a'])
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.stopped(first.pid)))
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.assertEqual(self.json()['playing']['pid'], second.pid)
        self.assertEqual([p['pid'] for p in self.json()['paused']], [first.pid])
        self.let_go('b')
        self.assertEqual(second.wait(timeout=5), 0)
        self.assertIsNone(first.poll())  # nobody continues it by itself
        self.assertTrue(self.stopped(first.pid))
        self.assertEqual(self.json()['playing'], None)

    def test_resume_with_the_turn_free_continues_at_once(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.stopped(first.pid)))
        r = self.speak('resume', session=self.me)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'Continuando a fala.'))
        self.assertTrue(self.until(lambda: not self.stopped(first.pid)))
        self.assertEqual(self.playing_pid(), first.pid)
        with open(os.path.join(self.folder(), 'speech.owner')) as fh:
            self.assertEqual(fh.read(), self.me)
        self.assertEqual((self.json()['playing']['pid'], self.json()['paused']), (first.pid, []))
        self.let_go('a')
        self.assertEqual(first.wait(timeout=5), 0)
        self.assertIsNone(self.json())

    def test_resume_with_nothing_paused_says_so(self):
        r = self.speak('resume', session=self.me)
        self.assertEqual(r.returncode, 1)
        self.assertIn('não há fala pausada', r.stderr)

    def test_resume_behind_a_speech_playing_waits_for_it_and_goes_before_the_queue(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        third = self.waiter('c', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        r = self.speak('resume', session=self.me)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'Continuando a fala assim que for a vez dela.'))
        self.assertTrue(self.until(lambda: len(self.tickets()) == 2))
        self.assertEqual(sorted(self.tickets(), key=lambda n: int(n.split('-')[0]))[-1].split('-')[1], str(third.pid))
        time.sleep(0.6)
        self.assertTrue(self.stopped(first.pid))  # the speech playing is not cut, and a stays frozen
        self.assertEqual(self.started(), ['a', 'b'])
        self.assertIsNone(second.poll())
        self.let_go('b')
        self.assertEqual(second.wait(timeout=5), 0)
        self.assertTrue(self.until(lambda: not self.stopped(first.pid)))  # before c
        self.assertEqual(self.playing_pid(), first.pid)
        self.assertEqual(self.started(), ['a', 'b'])
        self.assertIsNone(third.poll())
        self.let_go('a')
        self.assertEqual(first.wait(timeout=5), 0)
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b', 'c']))
        self.let_go('c')
        self.assertEqual(third.wait(timeout=5), 0)
        self.assertEqual(self.tickets(), [])

    def test_resume_twice_while_waiting_starts_one_helper_only(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.other)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.speak('resume', session=self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        r = self.speak('resume', session=self.me)
        self.assertEqual(r.returncode, 0)
        self.assertIn('já está esperando a vez', r.stdout)
        time.sleep(0.4)
        self.assertEqual(len(self.tickets()), 1)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'the microphone is faked through a pw-dump in the PATH')
    def test_resume_waits_for_the_microphone_like_any_speech(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.stopped(first.pid)))
        open(self.busy, 'w').close()
        r = self.speak('resume', session=self.me)
        self.assertEqual(r.returncode, 0)
        self.assertIn('assim que', r.stdout)
        time.sleep(1.5)
        self.assertTrue(self.stopped(first.pid))  # the microphone is busy: it stays frozen
        os.remove(self.busy)
        self.assertTrue(self.until(lambda: not self.stopped(first.pid), 6))
        self.assertEqual(self.playing_pid(), first.pid)

    def two_paused(self):
        """a (other session) is paused, then b (me) is paused: the most recent pause is b's."""
        first = self.waiter('a', self.other)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.me)
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.stopped(second.pid) and self.stopped(first.pid)))
        return first, second

    def test_resume_takes_the_pause_of_this_session_first(self):
        first, second = self.two_paused()
        self.speak('resume', session=self.other)
        self.assertTrue(self.until(lambda: not self.stopped(first.pid)))
        self.assertTrue(self.stopped(second.pid))
        self.assertEqual([p['pid'] for p in self.json()['paused']], [second.pid])

    def test_resume_of_a_session_without_pause_takes_the_most_recent(self):
        first, second = self.two_paused()
        r = subprocess.run([sys.executable, '-I', SPEAK, 'resume'], capture_output=True, text=True,
                           env={**self.env, 'CLAUDE_SPEAK_SESSION': 'terceira'})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.until(lambda: not self.stopped(second.pid)))
        self.assertTrue(self.stopped(first.pid))

    def test_stop_ends_the_paused_ones(self):
        first, second = self.two_paused()
        self.assertEqual(self.speak('stop', session=self.me).returncode, 0)
        self.assertTrue(self.ends(first, 5))
        self.assertTrue(self.ends(second, 5))
        self.assertIsNone(self.json())

    def test_stop_here_ends_only_the_paused_ones_of_this_session(self):
        first, second = self.two_paused()
        self.speak('stop', 'here', session=self.me)
        self.assertTrue(self.ends(second, 5))
        self.assertIsNone(first.poll())
        self.assertTrue(self.stopped(first.pid))
        self.assertEqual([p['pid'] for p in self.json()['paused']], [first.pid])

    def test_a_dead_session_loses_its_paused_speech_on_the_next_look(self):
        first = self.waiter('a', 'morta-1')
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        # 99999999-1: no such process, so the session is dead
        dead = '99999999-1'
        os.remove(os.path.join(self.folder(), 'speech.json'))
        with open(os.path.join(self.folder(), 'speech.json'), 'w') as fh:
            json.dump({'playing': None, 'paused': [{'pid': first.pid, 'session': dead, 'dir': '', 'how': ''}]}, fh)
        os.kill(first.pid, signal.SIGSTOP)
        self.assertTrue(self.until(lambda: self.stopped(first.pid)))
        self.speak('status', session=self.me)
        self.assertTrue(self.ends(first, 5))
        self.assertIsNone(self.json())

    def test_pruning_sessions_ends_the_paused_one_of_a_dead_session(self):
        first = self.waiter('a', self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        dead = '99999999-1'
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.stopped(first.pid)))
        data = self.json()
        data['paused'][0]['session'] = dead
        with open(os.path.join(self.folder(), 'speech.json'), 'w') as fh:
            json.dump(data, fh)
        self.speak('mode', 'full', session=self.me)  # writes a session file: that prunes
        self.assertTrue(self.ends(first, 5))

    def test_a_dead_speech_is_swept_from_the_file(self):
        gone = subprocess.Popen(['true'])
        gone.wait()
        os.makedirs(self.folder(), exist_ok=True)
        with open(os.path.join(self.folder(), 'speech.json'), 'w') as fh:
            json.dump({'playing': {'pid': gone.pid, 'session': self.me, 'dir': '', 'how': ''},
                       'paused': [{'pid': gone.pid, 'session': self.me, 'dir': '', 'how': ''}]}, fh)
        data = json.loads(self.speak('status', '--json', session=self.me).stdout)
        self.assertEqual((data['speaking'], data['paused']), (None, []))
        self.assertIsNone(self.json())

    def test_status_json_tells_who_speaks_and_what_is_paused(self):
        first = self.waiter('a', self.other, CLAUDE_SPEAK_DIR='/x/um', CLAUDE_SPEAK_HOW='full')
        self.assertTrue(self.until(lambda: self.started() == ['a']))
        second = self.waiter('b', self.me, CLAUDE_SPEAK_DIR='/x/dois', CLAUDE_SPEAK_HOW='summary')
        self.assertTrue(self.until(lambda: len(self.tickets()) == 1))
        self.speak('pause', session=self.me)
        self.assertTrue(self.until(lambda: self.started() == ['a', 'b']))
        data = json.loads(self.speak('status', '--json', session=self.me).stdout)
        self.assertEqual(data['session'], self.me)
        self.assertEqual(data['stateDir'], self.folder())
        self.assertEqual((data['speaking']['session'], data['speaking']['dir'], data['speaking']['how']),
                         (self.me, '/x/dois', 'summary'))
        self.assertEqual([(p['session'], p['dir'], p['how']) for p in data['paused']], [(self.other, '/x/um', 'full')])
        text = self.speak('status', session=self.me).stdout
        self.assertIn('fala: tocando agora', text)
        self.assertIn('pausada', text)

    def test_background_speech_records_folder_and_mode(self):
        from unittest import mock
        calls = []
        with mock.patch.object(speak.subprocess, 'Popen', lambda cmd, **k: calls.append(k)), \
                mock.patch.object(speak, 'engine_ready', lambda: True), \
                mock.patch.dict(os.environ, {'CLAUDE_SPEAK_CWD': '/x/projeto'}):
            speak.speak_background('oi', self.me, how='full')
        self.assertEqual(calls[0]['env']['CLAUDE_SPEAK_DIR'], '/x/projeto')
        self.assertEqual(calls[0]['env']['CLAUDE_SPEAK_HOW'], 'full')
        self.assertEqual(speak.read_session(self.me).get('dir'), '/x/projeto')

    def test_the_stop_hook_hands_over_its_folder(self):
        from unittest import mock
        calls = []
        data = {'last_assistant_message': 'oi', 'cwd': '/x/projeto'}
        with mock.patch.object(speak_stop.subprocess, 'run', lambda cmd, **k: calls.append(k)), \
                mock.patch.object(speak_stop.sys, 'stdin', io.StringIO(json.dumps(data))):
            speak_stop.main()
        self.assertEqual(calls[0]['env']['CLAUDE_SPEAK_CWD'], '/x/projeto')


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
                fh.write('import os, sys\n'
                         'open(%r, "w").write(" ".join(sys.argv[1:]) + "|" + sys.stdin.read())\n'
                         % os.path.join(home, 'seen'))
        return os.path.join(root, 'hooks', hook)

    def hand_over(self, **env):
        """Runs the hook with a fake `speak` beside it and returns what the fake received (arguments, `|`, stdin)."""
        with tempfile.TemporaryDirectory() as home:
            hook = self.plugin(home)
            seen = os.path.join(home, 'seen')
            r = subprocess.run([sys.executable, '-I', hook], input=json.dumps({'last_assistant_message': REPLY}),
                               capture_output=True, text=True, env={'HOME': home, 'PATH': '/usr/bin:/bin', **env})
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
            for _ in range(50):
                if os.path.exists(seen) and os.path.getsize(seen):
                    break
                time.sleep(0.05)
            return open(seen).read() if os.path.exists(seen) else None

    def end_hook(self, fake_body=None, **env):
        """Runs hooks/speak-end.py beside a fake `speak`; returns (completed process, what the fake saw, seconds)."""
        with tempfile.TemporaryDirectory() as home:
            hook = self.plugin(home, 'speak-end.py')
            if fake_body is not None:
                with open(os.path.join(os.path.dirname(os.path.dirname(hook)), 'bin', 'speak'), 'w') as fh:
                    fh.write(fake_body)
            started = time.time()
            r = subprocess.run([sys.executable, '-I', hook], input=json.dumps({'session_id': 'abc', 'reason': 'other'}),
                               capture_output=True, text=True, env={'HOME': home, 'PATH': '/usr/bin:/bin', **env})
            took = time.time() - started
            seen = os.path.join(home, 'seen')
            return r, (open(seen).read() if os.path.exists(seen) else None), took

    def test_fim_chama_o_corte_da_sessao(self):
        r, seen, _ = self.end_hook()
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
        self.assertEqual(seen, 'stop here|')

    def test_fim_rapido(self):
        """The hook gives `speak stop here` 1 s and no more (the SessionEnd budget is 1.5 s): a `speak` that hangs for
        30 s ends the hook at about 1 s, and one that fails ends it at once. The bound is the hook's own second plus the
        cost of starting Python here and now (measured with an empty script), so a loaded machine, where starting the
        two interpreters is slow, does not fail it; a hook that waited for the 30 s child would still fail by far."""
        started = time.monotonic()
        subprocess.run([sys.executable, '-I', '-c', 'pass'], check=True)
        startup = time.monotonic() - started  # one interpreter start, under the present load
        limit = 1.0 + 0.5 + 4 * startup  # the second the hook waits, the old slack, and four interpreter starts
        r, _, took = self.end_hook('import time\ntime.sleep(30)\n')
        self.assertEqual(r.returncode, 0)
        self.assertGreaterEqual(took, 0.9)  # it was the hook's limit that ended it, not an early exit
        self.assertLess(took, limit)
        r, _, took = self.end_hook('raise SystemExit(7)\n')
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
        self.assertLess(took, limit)

    def test_fim_sem_speak_sai_com_zero(self):
        with tempfile.TemporaryDirectory() as home:
            hook = self.plugin(home, 'speak-end.py', fake=False)
            r = subprocess.run([sys.executable, '-I', hook], input='não é json', capture_output=True, text=True,
                               env={'HOME': home, 'PATH': '/usr/bin:/bin'})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))

    def test_hook_hands_the_reply_to_speak(self):
        self.assertEqual(self.hand_over(), 'say -|' + REPLY)

    def test_hook_hands_over_even_with_env_mute(self):
        self.assertEqual(self.hand_over(CLAUDE_SPEAK='0'), 'say -|' + REPLY)

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
        data = data_dir(self.home, 'engine')
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
        self.assertEqual((r.returncode, r.stdout), (0, 'off\n'))
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

    def test_a_missing_engine_is_not_a_voice_turned_off(self):
        self.assertEqual(subprocess.run([sys.executable, '-I', SPEAK, 'on'], capture_output=True, env=self.env).returncode, 0)
        note = self.cut()
        self.assertIn('/speak install', note)
        self.assertIn('🔊', note)
        self.assertNotIn('desligada', note)

    def test_an_engine_being_installed_says_so_with_the_percentage(self):
        import fcntl
        folder = data_dir(self.home, 'state')
        os.makedirs(folder)
        with open(os.path.join(folder, 'install.lock'), 'a+') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            note = self.cut()
            self.assertEqual(note, 'speak: o motor de voz ainda está sendo instalado; não termine esta resposta com a linha 🔊.\n')
            with open(os.path.join(folder, 'install.progress'), 'w') as fh:
                json.dump({'fase': 'baixando', 'arquivo': 'kokoro-v1.0.onnx', 'feito': 78, 'total': 100, 'passo': 2,
                           'passos': 3}, fh)
            self.assertEqual(self.cut(), 'speak: o motor de voz ainda está sendo instalado (78%); não termine esta resposta com a linha 🔊.\n')

    def test_voice_off_with_the_engine_missing_keeps_todays_note(self):
        subprocess.run([sys.executable, '-I', SPEAK, 'off'], capture_output=True, env=self.env)
        self.assertIn('desligada', self.cut())

    def test_new_message_does_not_cut_any_speech_even_this_sessions(self):
        self.engine()
        folder = data_dir(self.home, 'state')
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

    def test_aviso_full(self):
        self.engine()
        full = 'speak: a leitura é da resposta inteira; não termine esta resposta com a linha 🔊.\n'
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'full'], capture_output=True, env=self.env)
        self.assertEqual(self.cut(), full)
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'summary'], capture_output=True, env=self.env)
        self.assertEqual(self.cut(), '')
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'full'], capture_output=True, env=self.env)
        subprocess.run([sys.executable, '-I', SPEAK, 'off'], capture_output=True, env=self.env)
        self.assertEqual(self.cut(), 'speak: a voz está desligada nesta sessão; não termine esta resposta com a linha 🔊.\n')

    def test_volta_ao_resumo(self):
        self.engine()
        back = 'speak: a leitura voltou a ser só o resumo; termine esta resposta com a linha 🔊.\n'
        full = 'speak: a leitura é da resposta inteira; não termine esta resposta com a linha 🔊.\n'

        sleeper = subprocess.Popen(['sleep', '60'])  # live session keys: dead ones are pruned at every write
        self.addCleanup(sleeper.wait)
        self.addCleanup(sleeper.kill)
        one, two = speak.session_key(os.getpid()), speak.session_key(sleeper.pid)
        self.env['CLAUDE_SPEAK_SESSION'] = one

        def run(*args):
            return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, env=self.env)
        run('mode', 'full')
        self.assertEqual(run('rule').returncode, 0)  # the session starts in full: the rule said so
        self.assertEqual(self.cut(), full)
        self.assertEqual(self.cut(), full)
        run('mode', 'summary')
        self.assertEqual(self.cut(), back)
        self.assertEqual(self.cut(), '')
        # starts in summary: nothing; the voice off leaves what was told alone
        env = {**self.env, 'CLAUDE_SPEAK_SESSION': two}
        subprocess.run([sys.executable, '-I', SPEAK, 'rule'], capture_output=True, env=env)
        self.assertEqual(self.cut(CLAUDE_SPEAK_SESSION=two), '')
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'full'], env=env, capture_output=True)
        self.assertEqual(self.cut(CLAUDE_SPEAK_SESSION=two), full)
        subprocess.run([sys.executable, '-I', SPEAK, 'off'], env=env, capture_output=True)
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'summary'], env=env, capture_output=True)
        self.assertIn('desligada', self.cut(CLAUDE_SPEAK_SESSION=two))
        subprocess.run([sys.executable, '-I', SPEAK, 'on'], env=env, capture_output=True)
        self.assertEqual(self.cut(CLAUDE_SPEAK_SESSION=two), back)

    def test_a_voz_que_volta_avisa_uma_vez(self):
        """Voice off then on in summary mode: the model was told to leave the 🔊 line out, so it is told once to write it."""
        self.engine()
        back = 'speak: a leitura voltou a ser só o resumo; termine esta resposta com a linha 🔊.\n'
        self.env['CLAUDE_SPEAK_SESSION'] = speak.session_key(os.getpid())

        def run(*args):
            return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True, env=self.env)
        run('rule')
        self.assertEqual(self.cut(), '')
        run('off')
        self.assertIn('desligada', self.cut())
        self.assertIn('desligada', self.cut())
        run('on')
        self.assertEqual(self.cut(), back)
        self.assertEqual(self.cut(), '')

    def test_without_speak_the_hook_still_notes(self):
        hook = Hook().plugin(self.home, 'speak-cut.py', fake=False)
        r = subprocess.run([sys.executable, '-I', hook], input='{}', capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertIn('🔊', r.stdout)


class Again(unittest.TestCase):
    """`speak say -` keeps the last reply of each session; `speak again` speaks it again (fake player, no engine)."""

    NO_LINE = 'Fiz a mudança no painel. Rode os testes depois.'

    def setUp(self):
        from unittest import mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        self.sleep = subprocess.Popen(['sleep', '60'])
        self.addCleanup(self.sleep.wait)
        self.addCleanup(self.sleep.kill)
        self.me = speak.session_key(os.getpid())
        self.other = speak.session_key(self.sleep.pid)
        self.calls = []
        speak.write_atomic(os.path.join(speak.STATE, 'scope'), '')  # the one-time migration of old session files is done
        real_popen = subprocess.Popen

        def fake_popen(cmd, **k):  # only the speech process is faked: on the Mac `ps` runs through Popen too
            if '_play' in cmd:
                return self.calls.append((cmd, k))
            return real_popen(cmd, **k)

        patchers = [mock.patch.dict(os.environ), mock.patch.object(speak, 'engine_ready', lambda: True),
                    mock.patch.object(speak.subprocess, 'Popen', fake_popen)]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in ('CLAUDE_SPEAK', 'CLAUDE_SPEAK_MODE', 'CLAUDE_SPEAK_SIZE'):
            os.environ.pop(name, None)

    def run_speak(self, *args, session=None, stdin=''):
        from unittest import mock
        os.environ['CLAUDE_SPEAK_SESSION'] = session or self.me
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(speak.sys, 'stdin', io.StringIO(stdin)), \
                mock.patch.object(speak.sys, 'stdout', out), mock.patch.object(speak.sys, 'stderr', err):
            code = speak.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def spoken(self):
        return [cmd[-1] for cmd, _ in self.calls]

    def test_say_keeps_only_the_last_reply_of_each_session(self):
        self.run_speak('say', '-', stdin='Primeira.\n🔊 Um.')
        self.run_speak('say', '-', stdin='Segunda.\n🔊 Dois.')
        self.run_speak('say', '-', stdin='Outra sessão.\n🔊 Três.', session=self.other)
        self.assertEqual(speak.read_last(self.me), ('Segunda.\n🔊 Dois.', 'summary'))
        self.assertEqual(speak.read_last(self.other), ('Outra sessão.\n🔊 Três.', 'summary'))
        self.assertEqual(sorted(os.listdir(speak.LAST)), sorted([self.me, self.other]))

    def test_again_repeats_the_way_it_played_and_never_another_sessions_reply(self):
        self.run_speak('say', '-', stdin='Texto.\n🔊 Resumo meu.')
        self.run_speak('say', '-', stdin='Outro.\n🔊 Resumo alheio.', session=self.other)
        self.calls.clear()
        code, out, _ = self.run_speak('again')
        self.assertEqual((code, self.spoken()), (0, ['Resumo meu.']))
        self.assertIn('resumo', out)

    def test_again_repeats_in_the_mode_it_was_read(self):
        speak.set_session(self.me, mode='full')
        self.run_speak('say', '-', stdin='Texto inteiro.\n🔊 Resumo.')
        self.calls.clear()
        self.run_speak('again')
        self.assertEqual(self.spoken(), ['Texto inteiro.'])

    def test_again_summary_and_full_ask_for_the_other_reading(self):
        self.run_speak('say', '-', stdin='Texto inteiro.\n🔊 Resumo.')  # summary is the mode
        self.calls.clear()
        code, out, _ = self.run_speak('again', 'full')
        self.assertEqual((code, self.spoken()), (0, ['Texto inteiro.']))
        self.assertIn('inteira', out)
        speak.set_session(self.me, mode='full')
        self.run_speak('say', '-', stdin='Texto inteiro.\n🔊 Resumo.')
        self.calls.clear()
        self.run_speak('again', 'summary')
        self.assertEqual(self.spoken(), ['Resumo.'])

    def test_again_summary_without_a_summary_line_reads_it_all_and_says_so(self):
        speak.set_session(self.me, mode='full')
        self.run_speak('say', '-', stdin=self.NO_LINE)
        self.calls.clear()
        code, out, _ = self.run_speak('again', 'summary')
        self.assertEqual((code, self.spoken()), (0, ['Fiz a mudança no painel. Rode os testes depois.']))
        self.assertIn('não tinha resumo', out)

    def test_without_a_stored_reply_it_says_so_and_fails(self):
        code, out, err = self.run_speak('again')
        self.assertEqual((code, self.calls), (1, []))
        self.assertIn('ainda não há uma resposta', err)
        self.assertEqual(self.run_speak('again', session='-')[0], 1)

    def test_bad_argument_is_refused(self):
        self.run_speak('say', '-', stdin='x.\n🔊 Y.')
        code, _, err = self.run_speak('again', 'tudo')
        self.assertEqual(code, 2)
        self.assertIn('speak again', err)

    def test_again_speaks_with_the_voice_off_and_the_reply_is_kept_with_it_off(self):
        self.run_speak('off')
        self.run_speak('say', '-', stdin='Texto.\n🔊 Resumo calado.')
        self.assertEqual(self.calls, [])  # nothing spoke by itself
        code, _, _ = self.run_speak('again')
        self.assertEqual((code, self.spoken()), (0, ['Resumo calado.']))
        env = self.calls[0][1]['env']
        self.assertEqual((env['CLAUDE_SPEAK_AGAIN'], env['CLAUDE_SPEAK_SESSION']), ('1', self.me))

    def test_the_reply_is_kept_without_the_engine_and_again_says_the_engine_is_missing(self):
        from unittest import mock
        with mock.patch.object(speak, 'engine_ready', lambda: False):
            self.run_speak('say', '-', stdin='Texto.\n🔊 Resumo.')
            code, _, err = self.run_speak('again')
        self.assertEqual((code, self.calls), (1, []))
        self.assertIn('motor', err)
        self.assertEqual(speak.read_last(self.me), ('Texto.\n🔊 Resumo.', 'summary'))

    def test_a_dead_session_loses_its_last_reply(self):
        self.run_speak('say', '-', stdin='Texto.\n🔊 Dele.', session=self.other)
        self.assertIn(self.other, os.listdir(speak.LAST))
        self.sleep.kill()
        self.sleep.wait()
        self.run_speak('say', '-', stdin='Texto.\n🔊 Meu.')
        self.assertEqual(os.listdir(speak.LAST), [self.me])


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
        self.assertTrue(os.path.exists(data_dir(self.tmp.name, 'config', 'size')))
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
        folder = data_dir(self.tmp.name, 'state', 'sessions')
        self.speak('size', 'small', key=key)
        self.assertEqual(speak_read(folder, key)['size'], 'small')
        self.assertFalse(os.path.exists(data_dir(self.tmp.name, 'config', 'size')))
        self.speak('size', 'large', 'all', key=key)
        self.assertNotIn('size', speak_read(folder, key))  # removed, not copied
        self.assertEqual(open(data_dir(self.tmp.name, 'config', 'size')).read().strip(), 'large')
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
        self.assertEqual(open(data_dir(self.tmp.name, 'config', 'voice')).read().strip(), 'pm_alex')
        self.speak('voice', 'pm_santa')
        self.assertIn('voz: pm_santa', self.speak('status').stdout)

    def test_unknown_name_is_refused_and_nothing_is_saved(self):
        r = self.speak('voice', 'bob')
        self.assertEqual(r.returncode, 2)
        self.assertIn('voz:', r.stderr)
        self.assertFalse(os.path.exists(data_dir(self.tmp.name, 'config', 'voice')))

    def test_order_is_variable_then_file_then_default(self):
        self.assertIn('voz: pf_dora', self.speak('status').stdout)
        self.speak('voice', 'alex')
        self.assertIn('voz: pm_alex', self.speak('status').stdout)
        self.assertIn('voz: pm_santa', self.speak('status', CLAUDE_SPEAK_VOICE='pm_santa').stdout)

    def test_alice_is_listed_saved_and_shown_by_name(self):
        out = self.speak('voice').stdout
        self.assertRegex(out, r'(?m)^  alice \(alice, feminina\)')
        self.assertIn('voz: alice', self.speak('voice', 'alice').stdout)
        self.assertEqual(open(data_dir(self.tmp.name, 'config', 'voice')).read().strip(), 'alice')
        self.assertRegex(self.speak('voice').stdout, r'(?m)^\* alice')
        self.assertNotIn('[', self.speak('status').stdout.split('voz: alice')[1].splitlines()[0])
        self.assertEqual(json.loads(self.speak('status', '--json').stdout)['voice'], 'alice')

    def test_old_saved_values_still_work(self):
        os.makedirs(os.path.dirname(data_dir(self.tmp.name, 'config', 'voice')))
        for full, short in (('pf_dora', 'dora'), ('pm_alex', 'alex'), ('pm_santa', 'santa')):
            with open(data_dir(self.tmp.name, 'config', 'voice'), 'w') as fh:
                fh.write(full + '\n')
            self.assertIn('voz: %s, velocidade 1.1' % full, self.speak('status').stdout)
            self.assertRegex(self.speak('voice').stdout, r'(?m)^\* ' + short)

    def test_default_speed_follows_the_voice_and_the_variable_wins(self):
        self.assertIn('velocidade 1.1', self.speak('status').stdout)
        self.speak('voice', 'alice')
        self.assertIn('velocidade 1.05', self.speak('status').stdout)
        self.assertIn('velocidade 1.3', self.speak('status', CLAUDE_SPEAK_SPEED='1.3').stdout)
        self.assertIn('velocidade 1.05', self.speak('status', CLAUDE_SPEAK_SPEED='x').stdout)
        self.assertIn('voz: pm_alex, velocidade 1.1', self.speak('status', CLAUDE_SPEAK_VOICE='pm_alex').stdout)

    def test_recipes(self):
        self.assertEqual(speak.recipe('alice'), ((('pf_dora', 0.6), ('af_heart', 0.4)), 1.05))
        self.assertEqual(speak.recipe('pf_dora'), ((('pf_dora', 1.0),), 1.1))
        self.assertEqual(speak.recipe('pm_other'), ((('pm_other', 1.0),), 1.1))

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'needs numpy')
    def test_alice_style_is_the_weighted_sum_in_float32(self):
        import numpy as np
        path = os.path.join(self.tmp.name, 'voices.bin')
        with open(path, 'wb') as fh:
            np.savez(fh, pf_dora=np.array([1.0, 2.0, 3.0], dtype='float32'),
                     af_heart=np.array([10.0, 20.0, 30.0], dtype='float32'))
        voices = np.load(path)
        style = speak.voice_style(voices, speak.recipe('alice')[0])
        self.assertEqual(style.dtype, np.float32)
        np.testing.assert_allclose(style, [4.6, 9.2, 13.8], rtol=1e-6)
        self.assertEqual(speak.voice_style(voices, speak.recipe('pf_dora')[0]), 'pf_dora')


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

    def test_a_linha_so_vai_nas_respostas_ao_humano_nunca_no_recap(self):
        text = self.rule(CLAUDE_SPEAK_MODE='summary')
        self.assertIn('Only in replies to the human: never in the recap (away summary', text)
        self.assertIn('nor in titles or other text Claude Code writes on its own', text)

    def test_regra_sem_linha_no_full(self):
        full = self.rule(CLAUDE_SPEAK_MODE='full')
        self.assertIn('do not write', full)
        self.assertNotIn('two or three sentences', full)
        self.assertNotIn('{', full)
        summary = self.rule(CLAUDE_SPEAK_MODE='summary')
        self.assertNotIn('do not write', summary)
        self.assertIn('every reply to the human ends with that `🔊` line', summary)
        self.assertIn('two or three sentences', summary)
        # the mode of the session (an exception in its file) is the one in force, not only the environment
        subprocess.run([sys.executable, '-I', SPEAK, 'mode', 'full'], capture_output=True,
                       env={**self.env, 'CLAUDE_SPEAK_SESSION': 'sessao-9'})
        self.assertIn('do not write', self.rule(CLAUDE_SPEAK_SESSION='sessao-9'))

    def test_rule_names_the_commands(self):
        text = self.rule()
        for name in ('on', 'off', 'mode', 'size', 'mic', 'voice', 'status', 'stop', 'install'):
            self.assertIn('`speak %s' % name, text)
        self.assertIn('`/speak`', text)
        self.assertNotIn('/speak:', text)
        self.assertIn('speak size', text)
        self.assertIn('speak voice', text)
        self.assertNotIn('mobile', text)


class StartHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.env = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-',
                    'CLAUDE_SPEAK_AUTOINSTALL': '0'}

    def run_hook(self, **env):
        r = subprocess.run([sys.executable, '-I', START], input='{}', capture_output=True, text=True,
                           env={**self.env, **env})
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        return r.stdout

    def engine(self):
        data = data_dir(self.home, 'engine')
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

    def test_with_engine_and_player_there_is_no_notice(self):
        self.engine()
        out = self.run_hook(**self.player())
        self.assertNotIn('instalado', out)
        self.assertNotIn('tocador', out)

    def test_without_player_it_says_so(self):
        self.engine()
        out = self.run_hook(PATH='/nonexistent')
        self.assertIn('tocador', out)
        self.assertNotIn('instalado', out)

    def test_copy_without_lib_exits_0_and_prints_nothing(self):
        """A plugin copy that lost lib/ must not break the session start: fail-open, exit 0."""
        with tempfile.TemporaryDirectory() as copy:
            hooks = os.path.join(copy, 'hooks')
            os.makedirs(hooks)
            shutil.copy(START, hooks)
            r = subprocess.run([sys.executable, '-I', os.path.join(hooks, 'speak-start.py')], input='{}',
                               capture_output=True, text=True, env=isolation.clean_env(copy))
        self.assertEqual((r.returncode, r.stdout), (0, ''), r.stderr)


START_MOD = load('speak_start', START)
isolation.pin_module(START_MOD, MODULE_ROOT)


class AutoInstallCommand(unittest.TestCase):
    """`speak autoinstall` is the one rule for starting the install by itself. In-process, with a fake Popen, a fake uv
    and a temporary home: no install, no download and no real folder is touched."""

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        self.uv = os.path.join(self.tmp.name, 'uv')
        self.popen = mock.patch.object(speak.subprocess, 'Popen').start()
        self.popen.return_value.poll.return_value = 0  # the fake child "ended": no waiting for the lock
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(speak.shutil, 'which',
                          side_effect=lambda n: self.uv if os.path.exists(self.uv) else None).start()
        mock.patch.dict(os.environ, {'CLAUDE_SPEAK_AUTOINSTALL': '1'}).start()

    def have_uv(self):
        open(self.uv, 'w').close()

    def have_engine(self):
        for path in (speak.VENV_PY, speak.MODEL, speak.VOICES):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'w').close()

    def test_starts_one_detached_install_with_the_log(self):
        self.have_uv()
        self.assertEqual(speak.autoinstall()[0], 'installing')
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0][1:], ['-u', '-I', os.path.realpath(SPEAK), 'install'])
        self.assertTrue(kwargs['start_new_session'])
        self.assertEqual(kwargs['stdin'], speak.subprocess.DEVNULL)
        self.assertEqual(kwargs['stdout'].name, speak.INSTALL_LOG)

    def test_free_lock_spawns_the_child_without_passing_the_lock(self):
        import fcntl
        self.have_uv()
        self.assertEqual(speak.autoinstall()[0], 'installing')
        self.assertNotIn('pass_fds', self.popen.call_args.kwargs)
        for lock in (speak.INSTALL_LOCK, speak.AUTOINSTALL_LOCK):
            with open(lock, 'a+') as probe:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)  # both left free

    def test_while_one_holds_the_lock_no_other_starts(self):
        import fcntl
        self.have_uv()
        os.makedirs(speak.STATE)
        with open(speak.INSTALL_LOCK, 'a+') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertEqual(speak.autoinstall()[0], 'installing')
        self.popen.assert_not_called()

    def test_two_calls_in_a_row_start_one_install(self):
        """The child takes INSTALL_LOCK after the call returns; the fake child does it at the first look."""
        import fcntl
        self.have_uv()
        held = []

        def start(*args, **kwargs):
            lock = open(speak.INSTALL_LOCK, 'a+')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held.append(lock)
            self.addCleanup(lock.close)
            return self.mock.Mock(poll=lambda: None)
        self.popen.side_effect = start
        self.assertEqual(speak.autoinstall()[0], 'installing')
        self.assertEqual(speak.autoinstall()[0], 'installing')
        self.assertEqual(self.popen.call_count, 1)

    def test_the_call_waits_for_the_child_to_take_the_lock(self):
        self.have_uv()
        self.popen.return_value.poll.return_value = None  # the child is alive
        seen = []
        real = speak.installing
        speak.installing = lambda: seen.append(1) or (len(seen) > 4)  # the lock shows up at the 5th look
        self.addCleanup(setattr, speak, 'installing', real)
        self.assertEqual(speak.autoinstall()[0], 'installing')
        self.assertGreater(len(seen), 4)

    def test_without_uv_it_says_so_and_starts_nothing(self):
        self.assertEqual(speak.autoinstall()[0], 'no-uv')
        self.popen.assert_not_called()

    def test_after_a_failure_it_says_failed_and_does_not_retry(self):
        self.have_uv()
        os.makedirs(speak.STATE)
        with open(speak.INSTALL_FAILED, 'w') as fh:
            fh.write(speak.plugin_version())
        self.assertEqual(speak.autoinstall()[0], 'failed')
        self.popen.assert_not_called()

    def test_an_empty_or_old_failure_mark_is_dropped_and_the_install_retried(self):
        self.have_uv()
        os.makedirs(speak.STATE)
        for content in ('', '0.0.1'):
            with open(speak.INSTALL_FAILED, 'w') as fh:
                fh.write(content)
            self.popen.reset_mock()
            self.assertEqual(speak.autoinstall()[0], 'installing')
            self.popen.assert_called_once()
            self.assertFalse(os.path.exists(speak.INSTALL_FAILED))

    def test_with_the_engine_there_it_says_ready_and_clears_the_failure_mark(self):
        self.have_uv()
        self.have_engine()
        os.makedirs(speak.STATE, exist_ok=True)
        with open(speak.INSTALL_FAILED, 'w') as fh:
            fh.write(speak.plugin_version())
        self.assertEqual(speak.autoinstall()[0], 'ready')
        self.assertFalse(os.path.exists(speak.INSTALL_FAILED))
        self.popen.assert_not_called()

    def test_the_switch_says_off_and_starts_nothing(self):
        self.have_uv()
        with self.mock.patch.dict(os.environ, {'CLAUDE_SPEAK_AUTOINSTALL': '0'}):
            self.assertEqual(speak.autoinstall()[0], 'off')
        self.popen.assert_not_called()

    def test_the_command_prints_the_word_and_exits_0(self):
        for setup, word in ((lambda: None, 'no-uv'), (self.have_uv, 'installing started')):
            setup()
            out = io.StringIO()
            with self.mock.patch('sys.stdout', out):
                self.assertEqual(speak.main(['autoinstall']), 0)
            self.assertEqual(out.getvalue(), word + '\n')

    def test_only_the_call_that_starts_it_says_started(self):
        import fcntl
        self.have_uv()
        self.assertEqual(speak.autoinstall(), ('installing', True))
        with open(speak.INSTALL_LOCK, 'a+') as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertEqual(speak.autoinstall(), ('installing', False))
        self.assertEqual(speak.autoinstall()[0], 'installing')

    def slow_child(self, pid=4242):
        """A child that is alive but has not taken INSTALL_LOCK yet (a loaded machine): the call gives up waiting."""
        self.popen.return_value = self.mock.Mock(pid=pid, poll=lambda: None)
        self.alive = {pid: [sys.executable, '-u', '-I', os.path.realpath(SPEAK), 'install']}
        for patch in (self.mock.patch.object(speak, 'AUTOINSTALL_WAIT', 0.05),
                      self.mock.patch.object(speak.speak_os, 'argv', side_effect=lambda p: self.alive.get(p))):
            patch.start()

    def test_a_child_slow_to_take_the_lock_is_not_started_twice(self):
        """Hook and module call at the same instant and the child is slow: only the first call starts it and says
        `started` (the one that tells the person); the second sees that child alive and starts nothing."""
        self.have_uv()
        self.slow_child()
        self.assertEqual(speak.autoinstall(), ('installing', True))
        self.assertEqual(speak.autoinstall(), ('installing', False))
        self.assertEqual(self.popen.call_count, 1)

    def test_two_calls_at_the_same_instant_say_started_once(self):
        import threading
        self.have_uv()
        self.slow_child()
        gate, answers = threading.Barrier(2), []

        def call():
            gate.wait(5)
            answers.append(speak.autoinstall())
        threads = [threading.Thread(target=call) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(sorted(answers), [('installing', False), ('installing', True)])
        self.assertEqual(self.popen.call_count, 1)

    def test_a_child_that_died_before_taking_the_lock_is_started_again(self):
        self.have_uv()
        self.slow_child()
        self.assertEqual(speak.autoinstall(), ('installing', True))
        self.alive.clear()  # it died without leaving a failure mark
        self.assertEqual(speak.autoinstall(), ('installing', True))
        self.assertEqual(self.popen.call_count, 2)

    def test_the_help_lists_the_command(self):
        self.assertIn('speak autoinstall', speak.__doc__)


class AutoInstall(unittest.TestCase):
    """The SessionStart hook asks `speak autoinstall` and tells what it answers. Everything here is in-process with a
    fake `run`: nothing is started."""

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = os.path.join(self.tmp.name, 'state')
        self.words = {'autoinstall': 'installing started\n'}
        self.calls = []
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(START_MOD, 'run', self.fake_run).start()

    def fake_run(self, *args):
        self.calls.append(args)
        if args[0] == 'autoinstall' and isinstance(self.words['autoinstall'], Exception):
            raise self.words['autoinstall']
        return self.mock.Mock(stdout=self.words[args[0]])

    def test_start_install_maps_the_word(self):
        for word, key in (('installing started', 'installing'), ('installing', None), ('no-uv', 'no-uv'),
                          ('failed', 'failed'), ('off', None), ('ready', None), ('', None), ('lixo', None)):
            self.words['autoinstall'] = word + '\n'
            self.assertEqual(START_MOD.start_install(), key, word)

    def test_an_install_someone_else_started_is_not_told_again(self):
        """Module and hook race: the module started the install and told the person in the conversation; the hook's
        call answers a bare `installing` and says nothing, so the notice comes out once."""
        self.words['autoinstall'] = 'installing\n'
        self.assertEqual(self.main_out('engine\n'), 'regra 🔊\n')

    def test_a_call_that_times_out_is_not_a_notice(self):
        self.words['autoinstall'] = subprocess.TimeoutExpired('speak', 10)
        self.assertIsNone(START_MOD.start_install())

    def test_one_call_per_session_start(self):
        self.main_out('engine\n')
        self.assertEqual([c for c in self.calls if c[0] == 'autoinstall'], [('autoinstall',)])

    def test_with_the_engine_there_the_notice_is_not_told_but_autoinstall_still_runs(self):
        self.words['autoinstall'] = 'ready\n'
        self.assertEqual(self.main_out(''), 'regra 🔊\n')
        self.assertEqual([c for c in self.calls if c[0] == 'autoinstall'], [('autoinstall',)])  # clears install.failed

    def main_out(self, check, rule='regra 🔊\n'):
        self.words.update(rule=rule, check=check)
        out = io.StringIO()
        with self.mock.patch.object(START_MOD.sys, 'stdin', io.StringIO('{}')), \
                self.mock.patch.object(START_MOD.sys, 'stdout', out):
            START_MOD.main()
        return out.getvalue()

    def test_main_tells_the_model_the_engine_is_being_installed(self):
        out = json.loads(self.main_out('engine\n'))
        context = out['hookSpecificOutput']['additionalContext']
        self.assertIn('regra 🔊', context)
        self.assertIn('sendo instalado em segundo plano', context)
        self.assertIn('350 MB', context)

    def test_a_warning_for_the_person_goes_in_system_message_and_the_rules_in_the_context(self):
        out = json.loads(self.main_out('engine\n'))
        self.assertIn('instalando a voz', out['systemMessage'])
        self.assertIn('/speak install', out['systemMessage'])
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'SessionStart')
        self.assertTrue(out['hookSpecificOutput']['additionalContext'].startswith('regra 🔊'))

    def test_each_warning_reaches_the_person(self):
        self.words['autoinstall'] = 'no-uv\n'
        out = json.loads(self.main_out('engine\n'))
        self.assertIn('uv', out['systemMessage'])
        self.assertIn('docs.astral.sh/uv', out['systemMessage'])
        self.words['autoinstall'] = 'failed\n'
        out = json.loads(self.main_out('engine\n'))
        self.assertIn('falhou', out['systemMessage'])
        self.assertIn('/speak install', out['systemMessage'])
        self.assertIn('install.log', out['hookSpecificOutput']['additionalContext'])
        self.words['autoinstall'] = 'ready\n'
        out = json.loads(self.main_out('player\n'))
        self.assertIn('tocador', out['systemMessage'])
        self.assertIn('tocador', out['hookSpecificOutput']['additionalContext'])

    def test_switched_off_with_the_engine_missing_tells_nothing(self):
        self.words['autoinstall'] = 'off\n'
        self.assertEqual(self.main_out('engine\n'), 'regra 🔊\n')

    def test_without_a_warning_the_rules_stay_plain_text(self):
        self.words['autoinstall'] = 'ready\n'
        self.assertEqual(self.main_out(''), 'regra 🔊\n')


class InstallMark(unittest.TestCase):
    """`speak install` leaves a mark when it fails and clears it when it works (fake uv steps, temporary folders)."""

    def setUp(self):
        from unittest import mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        self.mark = os.path.join(speak.STATE, 'install.failed')
        patcher = mock.patch.object(speak, 'INSTALL_FAILED', self.mark)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mock = mock

    def test_a_failure_leaves_the_mark_and_a_success_removes_it(self):
        with self.mock.patch.object(speak, 'install', side_effect=subprocess.CalledProcessError(1, 'uv')), \
                self.mock.patch('sys.stderr', io.StringIO()):
            self.assertEqual(speak.install_marked(), 1)
        self.assertTrue(os.path.exists(self.mark))
        with self.mock.patch.object(speak, 'install', return_value=0):
            self.assertEqual(speak.install_marked(), 0)
        self.assertFalse(os.path.exists(self.mark))

    def test_the_mark_holds_the_plugin_version(self):
        with self.mock.patch.object(speak, 'install', side_effect=OSError('x')), self.mock.patch('sys.stderr', io.StringIO()):
            speak.install_marked()
        with open(self.mark) as fh:
            self.assertEqual(fh.read(), self.load_version())

    def load_version(self):
        with open(os.path.join(ROOT, '.claude-plugin', 'plugin.json')) as fh:
            return json.load(fh)['version']

    def test_no_uv_leaves_no_mark(self):
        with self.mock.patch.object(speak, 'install', return_value=1):
            self.assertEqual(speak.install_marked(), 1)
        self.assertFalse(os.path.exists(self.mark))


class InstallLock(unittest.TestCase):
    """`speak install` takes STATE/install.lock itself, waits for a running install, and the status says so."""

    def setUp(self):
        import fcntl
        from unittest import mock
        self.fcntl, self.mock = fcntl, mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        os.makedirs(speak.STATE)
        env = mock.patch.dict(os.environ, {'CLAUDE_SPEAK_SESSION': '-'})
        env.start()
        self.addCleanup(env.stop)

    def hold(self):
        held = open(speak.INSTALL_LOCK, 'a+')
        self.fcntl.flock(held, self.fcntl.LOCK_EX)
        self.addCleanup(held.close)
        return held

    def test_install_waits_for_running_install(self):
        import threading
        held = self.hold()
        calls = []
        out = io.StringIO()
        result = []
        with self.mock.patch.object(speak, 'install', side_effect=lambda: calls.append(1) or 0), \
                self.mock.patch('sys.stdout', out):
            t = threading.Thread(target=lambda: result.append(speak.install_marked()))
            t.start()
            deadline = time.time() + 5
            while 'em andamento' not in out.getvalue() and time.time() < deadline:
                time.sleep(0.02)
            self.assertEqual(calls, [])
            self.assertTrue(t.is_alive())
            self.assertIn('outra instalação está em andamento', out.getvalue())
            self.fcntl.flock(held, self.fcntl.LOCK_UN)
            t.join(10)
        self.assertEqual((calls, result), ([1], [0]))
        self.assertFalse(os.path.exists(speak.INSTALL_FAILED))

    def test_install_without_a_running_one_says_nothing_about_waiting(self):
        out = io.StringIO()
        with self.mock.patch.object(speak, 'install', return_value=0), self.mock.patch('sys.stdout', out):
            self.assertEqual(speak.install_marked(), 0)
        self.assertNotIn('em andamento', out.getvalue())

    def test_status_says_installing_while_lock_held(self):
        self.hold()
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status'])
        self.assertIn('segundo plano', out.getvalue())
        self.assertIn('install.log', out.getvalue())
        self.assertNotIn('rode: speak install', out.getvalue())
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status', '--json'])
        data = json.loads(out.getvalue())
        self.assertIs(data['installing'], True)
        self.assertIs(data['engine'], False)

    def test_status_json_not_installing_when_lock_free(self):
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status', '--json'])
        self.assertIs(json.loads(out.getvalue())['installing'], False)

    def test_test_command_says_installing_while_lock_held(self):
        self.hold()
        err = io.StringIO()
        with self.mock.patch('sys.stderr', err):
            self.assertEqual(speak.main(['test']), 1)
        self.assertIn('segundo plano', err.getvalue())
        self.assertNotIn('rode: speak install', err.getvalue())

    def _install_with_fakes(self, urlretrieve):
        uv = os.path.join(self.tmp.name, 'uv')
        open(uv, 'w').close()
        with self.mock.patch.object(speak.shutil, 'which', return_value=uv), \
                self.mock.patch.object(speak, 'venv_works', return_value=True), \
                self.mock.patch.object(speak.subprocess, 'check_call'), \
                self.mock.patch.object(speak.urllib.request, 'urlretrieve', side_effect=urlretrieve), \
                self.mock.patch('sys.stdout', io.StringIO()):
            return speak.install()

    def test_download_uses_a_part_file_per_process(self):
        seen = []

        def fake(url, dest, reporthook=None):
            seen.append(dest)
            open(dest, 'w').close()
        self.assertEqual(self._install_with_fakes(fake), 0)
        self.assertEqual(seen, [speak.MODEL + '.part-%d' % os.getpid(), speak.VOICES + '.part-%d' % os.getpid()])
        self.assertTrue(os.path.exists(speak.MODEL) and os.path.exists(speak.VOICES))
        self.assertEqual([n for n in os.listdir(speak.DATA) if '.part' in n], [])

    def test_failed_download_removes_its_part_file(self):
        def fake(url, dest, reporthook=None):
            open(dest, 'w').close()
            raise OSError('rede caiu')
        with self.assertRaises(OSError):
            self._install_with_fakes(fake)
        self.assertEqual([n for n in os.listdir(speak.DATA) if '.part' in n], [])

    def test_every_failure_of_a_download_removes_its_part_file(self):
        """Whatever stops a download (the network, the progress hook, the final replace, an interrupt, a failure of the
        second file) leaves no `<file>.part-<pid>`; a file already complete stays."""
        part = '.part-%d' % os.getpid()
        real_replace = os.replace

        def drops(url, dest, reporthook=None):
            open(dest, 'w').close()
            raise OSError('rede caiu')

        def hook_fails(url, dest, reporthook=None):
            open(dest, 'w').close()
            with self.mock.patch.object(speak, 'write_progress', side_effect=OSError('disco cheio')):
                reporthook(0, 1000, 5000)

        def interrupted(url, dest, reporthook=None):
            open(dest, 'w').close()
            raise KeyboardInterrupt

        def second_fails(url, dest, reporthook=None):
            open(dest, 'w').close()
            if dest.startswith(speak.VOICES):
                raise OSError('rede caiu')

        def replace_fails(src, dst):
            if dst == speak.MODEL:
                raise OSError('trocar falhou')
            return real_replace(src, dst)

        for name, fake, error, replace in (('rede', drops, OSError, real_replace),
                                           ('progresso', hook_fails, OSError, real_replace),
                                           ('interrupção', interrupted, KeyboardInterrupt, real_replace),
                                           ('segundo arquivo', second_fails, OSError, real_replace),
                                           ('trocar o nome', lambda u, d, reporthook=None: open(d, 'w').close(),
                                            OSError, replace_fails)):
            with self.subTest(name):
                for path in (speak.MODEL, speak.VOICES):
                    remove_if_there(path)
                with self.mock.patch.object(speak.os, 'replace', replace), self.assertRaises(error):
                    self._install_with_fakes(fake)
                self.assertEqual([n for n in os.listdir(speak.DATA) if part in n], [])
                if name == 'segundo arquivo':
                    self.assertTrue(os.path.exists(speak.MODEL))  # the first one was complete, it stays

    def test_check_shows_the_tail_of_the_install_log_without_engine(self):
        with open(speak.INSTALL_LOG, 'w') as fh:
            fh.write('um\ndois\ntres\nquatro\ncinco\n')
        err, out = io.StringIO(), io.StringIO()
        with self.mock.patch('sys.stderr', err), self.mock.patch('sys.stdout', out):
            speak.main(['check'])
        self.assertIn('engine', out.getvalue())
        self.assertNotIn('engine', err.getvalue())
        self.assertIn('tres\nquatro\ncinco', err.getvalue())
        self.assertNotIn('dois', err.getvalue())


class InstallProgress(unittest.TestCase):
    """The install writes state/install.progress while it works; it counts only while the install lock is held."""

    def setUp(self):
        import fcntl
        from unittest import mock
        self.fcntl, self.mock = fcntl, mock
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        os.makedirs(speak.STATE)
        for name, value in (('CLAUDE_SPEAK_SESSION', '-'),):
            patcher = mock.patch.dict(os.environ, {name: value})
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (('PROGRESS_EVERY', 0), ('WAIT_POLL', 0.02)):
            patcher = mock.patch.object(speak, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def hold(self):
        held = open(speak.INSTALL_LOCK, 'a+')
        self.fcntl.flock(held, self.fcntl.LOCK_EX)
        self.addCleanup(held.close)
        return held

    def put(self, **fields):
        with open(speak.INSTALL_PROGRESS, 'w') as fh:
            json.dump(fields, fh)

    def install_with(self, urlretrieve, calls=None):
        uv = os.path.join(self.tmp.name, 'uv')
        open(uv, 'w').close()
        out = io.StringIO()
        with self.mock.patch.object(speak.shutil, 'which', return_value=uv), \
                self.mock.patch.object(speak, 'venv_works', return_value=True), \
                self.mock.patch.object(speak.subprocess, 'check_call', side_effect=lambda *a, **k: calls.append(a) if calls is not None else None), \
                self.mock.patch.object(speak.urllib.request, 'urlretrieve', side_effect=urlretrieve), \
                self.mock.patch('sys.stdout', out):
            return speak.install()

    def test_the_download_reports_the_file_and_the_bytes_and_the_file_goes_away_after(self):
        seen = []

        def fake(url, dest, reporthook=None):
            reporthook(0, 1000, 5000)
            reporthook(2, 1000, 5000)
            with open(speak.INSTALL_PROGRESS) as fh:
                seen.append(json.load(fh))
            open(dest, 'w').close()
        self.assertEqual(self.install_with(fake), 0)
        self.assertEqual(seen[0], {'fase': 'baixando', 'arquivo': 'kokoro-v1.0.onnx', 'feito': 2000, 'total': 5000,
                                   'passo': 2, 'passos': 3})
        self.assertEqual((seen[1]['arquivo'], seen[1]['passo'], seen[1]['passos']), ('voices-v1.0.bin', 3, 3))
        self.assertFalse(os.path.exists(speak.INSTALL_PROGRESS))
        self.assertEqual([n for n in os.listdir(speak.STATE) if 'progress' in n], [])

    def test_the_dependencies_step_is_reported_before_the_download(self):
        phases = []

        def check_call(*a, **k):
            with open(speak.INSTALL_PROGRESS) as fh:
                phases.append(json.load(fh))
        uv = os.path.join(self.tmp.name, 'uv')
        open(uv, 'w').close()
        with self.mock.patch.object(speak.shutil, 'which', return_value=uv), \
                self.mock.patch.object(speak, 'venv_works', return_value=True), \
                self.mock.patch.object(speak.subprocess, 'check_call', side_effect=check_call), \
                self.mock.patch.object(speak.urllib.request, 'urlretrieve', side_effect=lambda u, d, reporthook=None: open(d, 'w').close()), \
                self.mock.patch('sys.stdout', io.StringIO()):
            speak.install()
        self.assertEqual(phases[0]['fase'], 'dependências')
        self.assertEqual((phases[0]['passo'], phases[0]['passos']), (1, 3))

    def test_the_progress_file_is_written_at_most_every_half_second(self):
        writes = []
        real = speak.write_progress

        def fake(url, dest, reporthook=None):
            for blocks in range(5):
                reporthook(blocks, 1000, 5000)
            open(dest, 'w').close()
        with self.mock.patch.object(speak, 'PROGRESS_EVERY', 60), \
                self.mock.patch.object(speak, 'write_progress', side_effect=lambda **f: writes.append(f) or real(**f)):
            self.install_with(fake)
        downloads = [w for w in writes if w.get('fase') == 'baixando' and w['arquivo'] == 'kokoro-v1.0.onnx']
        self.assertLessEqual(len(downloads), 2)  # the one at the start of the file and the first call of the hook

    def test_a_failed_download_also_removes_the_progress_file(self):
        def fake(url, dest, reporthook=None):
            reporthook(1, 1000, 5000)
            raise OSError('rede caiu')
        with self.assertRaises(OSError):
            self.install_with(fake)
        self.assertFalse(os.path.exists(speak.INSTALL_PROGRESS))

    def test_the_install_log_gets_every_line_at_once(self):
        class Recording(io.StringIO):
            flushes = []

            def flush(self):
                self.flushes.append(self.getvalue())
        out = Recording()
        uv = os.path.join(self.tmp.name, 'uv')
        open(uv, 'w').close()
        with self.mock.patch.object(speak.shutil, 'which', return_value=uv), \
                self.mock.patch.object(speak, 'venv_works', return_value=True), \
                self.mock.patch.object(speak.subprocess, 'check_call'), \
                self.mock.patch.object(speak.urllib.request, 'urlretrieve', side_effect=lambda u, d, reporthook=None: open(d, 'w').close()), \
                self.mock.patch('sys.stdout', out):
            speak.install()
        self.assertTrue(any(f.endswith('voz: baixando kokoro-v1.0.onnx\n') for f in out.flushes))
        self.assertTrue(out.flushes[-1].endswith('voz: motor instalado em %s\n' % speak.DATA))

    def test_a_leftover_file_with_the_lock_free_is_ignored_and_removed(self):
        self.put(fase='baixando', arquivo='kokoro-v1.0.onnx', feito=10, total=100, passo=2, passos=3)
        self.assertIsNone(speak.install_progress())
        self.assertFalse(os.path.exists(speak.INSTALL_PROGRESS))

    def test_leftover_temporaries_go_with_the_leftover_file(self):
        self.put(fase='dependências')
        tmps = [speak.INSTALL_PROGRESS + '.tmp-123', speak.INSTALL_PROGRESS + '.tmp-9']
        other = os.path.join(speak.STATE, 'queue.lock.tmp-1')
        for path in tmps + [other]:
            open(path, 'w').close()
        self.assertIsNone(speak.install_progress())
        self.assertEqual([os.path.exists(p) for p in tmps + [other]], [False, False, True])
        # with the lock held (an install running) its temporary is left alone
        self.hold()
        open(tmps[0], 'w').close()
        speak.install_progress()
        self.assertTrue(os.path.exists(tmps[0]))

    def test_with_the_lock_held_the_progress_is_read(self):
        self.hold()
        self.assertIsNone(speak.install_progress())  # no file yet
        self.put(fase='baixando', arquivo='kokoro-v1.0.onnx', feito=10, total=100, passo=2, passos=3)
        self.assertEqual(speak.install_progress()['feito'], 10)
        with open(speak.INSTALL_PROGRESS, 'w') as fh:
            fh.write('{ruim')
        self.assertIsNone(speak.install_progress())

    def test_the_text(self):
        text = speak.progress_text
        self.assertEqual(text({'fase': 'dependências'}), 'instalando as dependências')
        self.assertEqual(text({'fase': 'baixando', 'arquivo': 'kokoro-v1.0.onnx', 'feito': 252698624, 'total': 325532232}),
                         'baixando o modelo de voz: 253 de 326 MB (78%)')
        self.assertEqual(text({'fase': 'baixando', 'arquivo': 'voices-v1.0.bin', 'feito': 1000000, 'total': 2000000}),
                         'baixando as vozes: 1 de 2 MB (50%)')
        self.assertEqual(text({'fase': 'baixando', 'arquivo': 'kokoro-v1.0.onnx', 'feito': 5000000, 'total': 0}),
                         'baixando o modelo de voz: 5 MB')
        self.assertIsNone(text(None))

    def test_status_and_json_show_the_progress(self):
        self.hold()
        self.put(fase='baixando', arquivo='kokoro-v1.0.onnx', feito=500000, total=1000000, passo=2, passos=3)
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status'])
        self.assertIn('baixando o modelo de voz: 0 de 1 MB (50%)', out.getvalue())
        self.assertIn('install.log', out.getvalue())
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status', '--json'])
        data = json.loads(out.getvalue())
        self.assertEqual((data['installing'], data['install']['feito']), (True, 500000))

    def test_json_has_no_install_when_nothing_runs(self):
        self.put(fase='dependências')  # a leftover of a dead install
        out = io.StringIO()
        with self.mock.patch('sys.stdout', out):
            speak.main(['status', '--json'])
        self.assertIsNone(json.loads(out.getvalue())['install'])

    def test_the_second_install_prints_the_progress_while_it_waits(self):
        import threading
        held = self.hold()
        out = io.StringIO()
        with self.mock.patch.object(speak, 'install', return_value=0), self.mock.patch('sys.stdout', out):
            t = threading.Thread(target=speak.install_marked)
            t.start()
            self.put(fase='baixando', arquivo='kokoro-v1.0.onnx', feito=2000000, total=4000000, passo=2, passos=3)
            deadline = time.time() + 5
            while '50%' not in out.getvalue() and time.time() < deadline:
                time.sleep(0.02)
            self.assertIn('voz: baixando o modelo de voz: 2 de 4 MB (50%)', out.getvalue())
            self.fcntl.flock(held, self.fcntl.LOCK_UN)
            t.join(10)
        self.assertFalse(t.is_alive())

    def test_silent_says_why(self):
        def why():
            out = io.StringIO()
            with self.mock.patch('sys.stdout', out):
                code = speak.main(['silent'])
            return code, out.getvalue()
        self.assertEqual(why(), (0, 'missing\n'))
        held = self.hold()
        self.assertEqual(why(), (0, 'installing\n'))
        self.put(fase='baixando', arquivo='kokoro-v1.0.onnx', feito=77, total=100, passo=2, passos=3)
        self.assertEqual(why(), (0, 'installing 77\n'))
        self.fcntl.flock(held, self.fcntl.LOCK_UN)
        with self.mock.patch.object(speak, 'is_on', return_value=False):
            self.assertEqual(why(), (0, 'off\n'))


class Scope(unittest.TestCase):
    """The session file holds only exceptions; `all` writes the general setting and removes the field from every session."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'HOME': self.tmp.name, 'PATH': '/usr/bin:/bin'}
        self.paths = isolate(self, self.tmp.name)
        self.sleep = subprocess.Popen(['sleep', '60'])
        self.addCleanup(self.sleep.wait)
        self.addCleanup(self.sleep.kill)
        self.me = speak.session_key(os.getpid())
        self.other = speak.session_key(self.sleep.pid)
        self.folder = data_dir(self.tmp.name, 'state', 'sessions')

    def speak(self, *args, session, **env):
        return subprocess.run([sys.executable, '-I', SPEAK, *args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env={**self.env, 'CLAUDE_SPEAK_SESSION': session, **env})

    def put(self, key, data):
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, key), 'w') as fh:
            fh.write(json.dumps(data))

    def test_all_remove_das_sessoes(self):
        self.put(self.me, {'mode': 'full'})
        self.put(self.other, {'mode': 'full'})
        self.speak('mode', 'summary', 'all', session=self.me)
        self.assertEqual(open(data_dir(self.tmp.name, 'config', 'mode')).read().strip(), 'summary')
        self.assertEqual(speak_read(self.folder, self.me), {})
        self.assertEqual(speak_read(self.folder, self.other), {})
        self.assertEqual(self.speak('status', '--json', session=self.other).stdout.count('"mode": "summary"'), 1)

    def test_on_all_marca_e_remove(self):
        self.put(self.other, {'voice': 'muted', 'size': 'small'})
        before = speak.session_started(self.other) - 3600
        self.speak('on', 'all', session=self.me)
        mark = data_dir(self.tmp.name, 'state', 'all')
        self.assertTrue(os.path.exists(mark))
        self.assertEqual(speak_read(self.folder, self.other), {'size': 'small'})
        self.assertIn('voz: ligada', self.speak('status', session=self.other, CLAUDE_SPEAK='0').stdout)
        self.assertLess(before, os.stat(mark).st_mtime)

    def test_status_marca(self):
        self.put(self.me, {'size': 'large'})
        out = self.speak('status', session=self.me).stdout
        self.assertIn('tamanho do resumo: large \u00b7 s\u00f3 nesta sess\u00e3o', out)
        self.assertIn('modo: summary\n', out)
        self.assertNotIn('modo: summary \u00b7', out)
        self.assertNotIn('voz: sem', out)
        self.assertTrue(all('s\u00f3 nesta sess\u00e3o' not in l for l in out.splitlines() if 'voz: ' in l and 'velocidade' in l))
        plain = self.speak('status', session=self.other).stdout
        self.assertNotIn('s\u00f3 nesta sess\u00e3o', plain)

    def test_status_json_scope(self):
        self.put(self.me, {'size': 'large'})
        data = json.loads(self.speak('status', '--json', session=self.me).stdout)
        self.assertEqual(data['scope'], {'on': 'all', 'mode': 'all', 'size': 'session', 'mic': 'all'})
        self.assertEqual(data['size'], 'large')

    def test_limpa_copias_antigas(self):
        os.makedirs(os.path.dirname(speak.MODE_FILE), exist_ok=True)
        with open(speak.MODE_FILE, 'w') as fh:
            fh.write('summary\n')
        self.put(self.me, {'voice': 'muted', 'mode': 'summary', 'size': 'medium'})
        self.put(self.other, {'mode': 'full', 'size': 'large'})
        speak.migrate()
        self.assertEqual(speak_read(self.folder, self.me), {'voice': 'muted'})
        self.assertEqual(speak_read(self.folder, self.other), {'mode': 'full', 'size': 'large'})
        # once only: an exception equal to the general value written later stays
        self.put(self.me, {'mode': 'summary'})
        speak.migrate()
        self.assertEqual(speak_read(self.folder, self.me), {'mode': 'summary'})


class DropCopiedOnce(unittest.TestCase):
    """The one-time cleanup of the old copy-on-all session files takes the queue lock, so two sessions that start
    together never run it at the same time and it runs once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolate(self, self.tmp.name)
        os.makedirs(speak.SESSIONS)
        for key in ('1-1', '2-2', '3-3'):
            speak.write_atomic(os.path.join(speak.SESSIONS, key), json.dumps({'mode': 'full', 'size': 'small'}))
        os.makedirs(os.path.dirname(speak.MODE_FILE), exist_ok=True)
        with open(speak.MODE_FILE, 'w') as fh:
            fh.write('full\n')

    def test_two_runs_at_once_do_the_work_once_and_never_overlap(self):
        import threading
        inside, most, reads = [0], [0], []
        guard = threading.Lock()
        real_read = speak.read_session

        def slow_read(key):
            with guard:
                inside[0] += 1
                most[0] = max(most[0], inside[0])
                reads.append(key)
            time.sleep(0.05)  # widens the window in which a second run could start
            try:
                return real_read(key)
            finally:
                with guard:
                    inside[0] -= 1

        gate = threading.Barrier(2)
        errors = []

        def run():
            try:
                gate.wait(5)
                speak._drop_copied_fields_once()
            except BaseException as exc:
                errors.append(exc)

        with mock.patch.object(speak, 'read_session', slow_read):
            threads = [threading.Thread(target=run) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual(errors, [])
        self.assertEqual(most[0], 1, 'two runs were inside the cleanup together')
        self.assertEqual(sorted(reads), ['1-1', '2-2', '3-3'], 'the cleanup ran more than once')
        self.assertTrue(os.path.exists(os.path.join(speak.STATE, 'scope')))
        self.assertEqual(speak_read(speak.SESSIONS, '1-1'), {'size': 'small'})

    def test_it_runs_inside_a_queue_lock_already_held_by_the_same_thread(self):
        with speak.queue_lock():  # reentrant: a caller that holds the lock does not hang
            speak._drop_copied_fields_once()
        self.assertTrue(os.path.exists(os.path.join(speak.STATE, 'scope')))


class OldOutputField(unittest.TestCase):
    def test_a_session_file_with_an_output_field_is_read_without_it(self):
        with tempfile.TemporaryDirectory() as root:
            isolate(self, root)
            os.makedirs(speak.SESSIONS)
            with open(os.path.join(speak.SESSIONS, 'k'), 'w') as fh:
                fh.write(json.dumps({'voice': 'speaking', 'mode': 'summary', 'output': 'speaker'}))
            self.assertEqual(speak.read_session('k'), {'voice': 'speaking', 'mode': 'summary'})


class StatusJson(unittest.TestCase):
    def test_padrao_summary(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            isolate(self, root)
            out = io.StringIO()
            with mock.patch.dict(os.environ, {'CLAUDE_SPEAK_SESSION': '-'}), mock.patch('sys.stdout', out):
                self.assertEqual(speak.main(['status', '--json']), 0)
            data = json.loads(out.getvalue())
            self.assertEqual((data['mode'], data['size'], data['voice'], data['on']),
                             ('summary', 'medium', 'dora', True))
            os.makedirs(os.path.dirname(speak.MODE_FILE), exist_ok=True)
            with open(speak.MODE_FILE, 'w') as fh:
                fh.write('full\n')  # a mode already saved in the general file is kept
            out = io.StringIO()
            with mock.patch.dict(os.environ, {'CLAUDE_SPEAK_SESSION': '-'}), mock.patch('sys.stdout', out):
                self.assertEqual(speak.main(['status', '--json']), 0)
            self.assertEqual(json.loads(out.getvalue())['mode'], 'full')


    def test_one_json_line_with_the_state(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            isolate(self, root)
            out = io.StringIO()
            with mock.patch.dict(os.environ, {'CLAUDE_SPEAK_SESSION': '-'}), mock.patch('sys.stdout', out):
                self.assertEqual(speak.main(['status', '--json']), 0)
        data = json.loads(out.getvalue())
        self.assertEqual((data['mode'], data['size'], data['voice'], data['engine']),
                         ('summary', 'medium', 'dora', False))


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
        self.assertEqual(set(hooks), {'SessionStart', 'UserPromptSubmit', 'Stop', 'SessionEnd'})
        self.assertNotIn('matcher', hooks['SessionEnd'][0])
        self.assertEqual(hooks['SessionStart'][0]['matcher'], 'startup|resume|clear|compact|fork')
        for entries in hooks.values():
            for entry in entries:
                for hook in entry['hooks']:
                    match = re.fullmatch(r'python3 -I "\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[\w.-]+)"', hook['command'])
                    self.assertTrue(match, hook['command'])
                    self.assertTrue(os.path.exists(os.path.join(ROOT, match.group(1))))

    def test_the_slash_command_is_a_hooks_module(self):
        hooks = self.load('hooks', 'hooks.json')
        self.assertEqual(hooks['modules'], ['./register.tsx'])
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'hooks', 'register.tsx')))
        self.assertTrue(os.path.exists(os.path.join(ROOT, 'hooks', 'register.test.tsx')))
        self.assertEqual(self.load('.claude-plugin', 'plugin.json')['version'], '0.17.0')

    def test_removed_pieces_are_gone(self):
        for rel in ('prompts', 'tests/test_speak_prompt.py', 'hooks/speak-cut.sh', 'skills'):
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel)), rel)


class Update(unittest.TestCase):
    """`speak update` and the version in `status`, on a copy of the plugin laid out as the cache does
    (`.claude/plugins/cache/cc-speaker/speak/<version>/`) and a fake `claude` that only logs and answers. The real
    `claude` is never run: PATH holds only the fake (or nothing)."""

    FAKE = (
        '#!/bin/sh\n'
        'echo "$*" >> "$FAKE_LOG"\n'
        'case "$FAKE_MODE" in\n'
        '  slow) exec sleep 30 ;;\n'
        '  fail) case "$*" in "plugin update"*) echo "sem rede: não deu" >&2; exit 3 ;; esac ;;\n'
        '  new) case "$*" in "plugin update"*) echo "✔ Plugin updated from 0.8.1 to 0.9.0"; exit 0 ;; esac ;;\n'
        '  cached) case "$*" in "plugin update"*) echo "feito"; exit 0 ;; esac ;;\n'
        '  same) case "$*" in "plugin update"*) echo "already at the latest version"; exit 0 ;; esac ;;\n'
        'esac\n'
        'echo ok\n')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, 'home')
        cache = os.path.join(self.home, '.claude', 'plugins', 'cache', 'cc-speaker', 'speak')
        self.plugin = os.path.join(cache, '0.8.1')
        os.makedirs(os.path.join(self.plugin, '.claude-plugin'))
        shutil.copytree(os.path.join(ROOT, 'bin'), os.path.join(self.plugin, 'bin'), ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(os.path.join(ROOT, 'lib'), os.path.join(self.plugin, 'lib'), ignore=shutil.ignore_patterns('__pycache__'))
        self.write_version(self.plugin, '0.8.1')
        self.cache = cache
        self.script = os.path.join(self.plugin, 'bin', 'speak')
        self.fakebin = os.path.join(self.tmp.name, 'fakebin')
        os.makedirs(self.fakebin)
        self.log = os.path.join(self.tmp.name, 'claude.log')
        self.install_fake(os.path.join(self.fakebin, 'claude'))
        self.data = os.path.join(self.tmp.name, 'data')

    def install_fake(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(self.FAKE)
        os.chmod(path, 0o755)

    @staticmethod
    def write_version(folder, version):
        os.makedirs(os.path.join(folder, '.claude-plugin'), exist_ok=True)
        with open(os.path.join(folder, '.claude-plugin', 'plugin.json'), 'w') as fh:
            json.dump({'name': 'speak', 'version': version}, fh)

    def speak(self, *args, mode='', path=None, **env):
        base = {'HOME': self.home, 'PATH': path if path is not None else self.fakebin + ':/usr/bin:/bin',
                'CLAUDE_SPEAK_DATA': self.data, 'FAKE_LOG': self.log, 'FAKE_MODE': mode, 'CLAUDE_SPEAK_SESSION': '-'}
        return subprocess.run([sys.executable, '-I', self.script, *args], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, env={**base, **env}, timeout=60)

    def calls(self):
        try:
            with open(self.log) as fh:
                return fh.read().splitlines()
        except OSError:
            return []

    def test_updated_from_to_read_from_the_claude_answer(self):
        r = self.speak('update', mode='new')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'atualizado de 0.8.1 para 0.9.0; rode /reload-plugins ou abra uma sessão '
                                           'nova para valer')
        self.assertEqual(self.calls(), ['plugin marketplace update cc-speaker', 'plugin update speak@cc-speaker'])

    def test_updated_from_to_read_from_the_newest_plugin_json_in_the_cache(self):
        self.write_version(os.path.join(self.cache, '0.10.0'), '0.10.0')
        self.write_version(os.path.join(self.cache, '0.9.0'), '0.9.0')  # 0.10.0 is higher than 0.9.0
        r = self.speak('update', mode='cached')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('atualizado de 0.8.1 para 0.10.0;', r.stdout)

    def test_already_up_to_date(self):
        r = self.speak('update', mode='same')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'já está na versão mais nova (0.8.1)')

    def test_claude_missing_says_so_and_exits_1(self):
        if shutil.which('claude', path='/usr/bin:/bin'):
            self.skipTest('a claude in the system folders')
        r = self.speak('update', path='/usr/bin:/bin')
        self.assertEqual(r.returncode, 1)
        self.assertIn('não achei o comando claude', r.stderr)
        self.assertEqual(self.calls(), [])

    def test_claude_in_local_bin_is_the_fallback(self):
        if shutil.which('claude', path='/usr/bin:/bin'):
            self.skipTest('a claude in the system folders')
        self.install_fake(os.path.join(self.home, '.local', 'bin', 'claude'))
        r = self.speak('update', mode='same', path='/usr/bin:/bin')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.calls()), 2)

    def test_a_failing_claude_passes_its_code_and_message(self):
        r = self.speak('update', mode='fail')
        self.assertEqual(r.returncode, 3)
        self.assertIn('falhou (código 3)', r.stderr)
        self.assertIn('sem rede: não deu', r.stderr)
        self.assertEqual(r.stdout, '')

    def test_a_claude_that_takes_too_long_is_stopped(self):
        started = time.time()
        r = self.speak('update', mode='slow', CLAUDE_SPEAK_UPDATE_TIMEOUT='1')
        self.assertEqual(r.returncode, 1)
        self.assertIn('passou de 1 segundos', r.stderr)
        self.assertLess(time.time() - started, 20)
        self.assertEqual(len(self.calls()), 1)  # it did not go on to the second command

    def test_outside_the_cache_the_names_are_the_fixed_ones(self):
        outside = os.path.join(self.tmp.name, 'dev')
        shutil.copytree(self.plugin, outside)
        self.script = os.path.join(outside, 'bin', 'speak')
        r = self.speak('update', mode='same')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), ['plugin marketplace update cc-speaker', 'plugin update speak@cc-speaker'])

    def test_status_shows_the_version_first_and_json_has_it(self):
        out = self.speak('status').stdout.splitlines()
        self.assertEqual(out[0], 'versão: 0.8.1')
        self.assertTrue(out[1].startswith('voz: '))
        self.assertEqual(json.loads(self.speak('status', '--json').stdout)['version'], '0.8.1')

    def test_the_version_comes_from_the_real_plugin_json(self):
        self.assertEqual(speak.plugin_version(), self.load_real())

    @staticmethod
    def load_real():
        with open(os.path.join(ROOT, '.claude-plugin', 'plugin.json')) as fh:
            return json.load(fh)['version']


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
            env = {k: v for k, v in os.environ.items() if not k.startswith(('XDG_', 'CLAUDE_SPEAK', 'CLAUDE_PLUGIN'))}
            env['HOME'] = home
            env['CLAUDE_PLUGIN_DATA'] = os.path.join(home, 'real-data')  # isolate() must ignore it
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'tests', 'test_speak.py'), 'Session'],
                               capture_output=True, text=True, env=env, cwd=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            for folder, names in made.items():
                self.assertEqual(os.listdir(folder), names, folder)
            for rel in ('.local/share', '.config', '.local/state'):
                self.assertEqual(os.listdir(os.path.join(home, rel)), ['claude-voz'], rel)
            self.assertFalse(os.path.exists(os.path.join(home, 'real-data')))


if __name__ == '__main__':
    unittest.main()
