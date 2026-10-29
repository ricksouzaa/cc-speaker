"""The per-system piece (lib/speak_os.py) and the session search in bin/speak that uses it."""
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


speak_os = load('speak_os_under_test', os.path.join(ROOT, 'lib', 'speak_os.py'))
speak = load('speak_for_os_tests', os.path.join(ROOT, 'bin', 'speak'))


def fake_open(files):
    real = open

    def opener(path, mode='r', *a, **k):
        if path in files:
            data = files[path]
            return io.BytesIO(data) if 'b' in mode else io.StringIO(data)
        if str(path).startswith('/proc/'):
            raise FileNotFoundError(path)
        return real(path, mode, *a, **k)
    return opener


def fake_ps(table):
    """subprocess.run stand-in: table maps the `-o` field list (and pid) to stdout."""
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        out = table.get((cmd[2], cmd[4]))
        if out is None:
            return subprocess.CompletedProcess(cmd, 1, '', '')
        return subprocess.CompletedProcess(cmd, 0, out, '')
    run.calls = calls
    return run


class LinuxTest(unittest.TestCase):
    def test_linux_le_proc(self):
        stat = '42 (my (odd) name) S 7 ' + ' '.join(str(n) for n in range(5, 25))
        files = {'/proc/42/stat': stat, '/proc/42/comm': 'claude\n', '/proc/42/cmdline': b'python3\0-I\0/x/speak\0_play\0'}
        with mock.patch.object(speak_os, 'SYSTEM', 'linux'), mock.patch('builtins.open', fake_open(files)):
            self.assertEqual(speak_os.parent(42), 7)
            self.assertEqual(speak_os.name(42), 'claude')
            self.assertEqual(speak_os.started(42), '22')
            self.assertEqual(speak_os.argv(42), ['python3', '-I', '/x/speak', '_play'])
            self.assertIsNone(speak_os.parent(43))

    def test_real_process_round_trip(self):
        if not os.path.isdir('/proc/self'):
            self.skipTest('no /proc')
        me = os.getpid()
        self.assertTrue(speak_os.alive(me))
        self.assertEqual(speak_os.parent(me), os.getppid())
        self.assertTrue(os.path.basename(speak_os.argv(me)[0]).startswith('python'))
        self.assertAlmostEqual(speak_os.started_at(me), speak.session_started(speak.session_key(me)), places=3)
        self.assertEqual(speak_os.ancestors(me)[0][0], me)


class MacTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(self.no_leaked_watcher)  # safety net: runs after the patches are undone
        patch = mock.patch.object(speak_os, 'SYSTEM', 'mac')
        patch.start()
        self.addCleanup(patch.stop)

    def no_leaked_watcher(self):
        import threading
        alive = [th for th in threading.enumerate()
                 if th.is_alive() and 'watch_microphone.<locals>.loop' in getattr(th._target, '__qualname__', '')]
        self.assertEqual(alive, [], 'a microphone watcher outlived its test')

    def run_ps(self, table):
        run = fake_ps(table)
        patch = mock.patch.object(speak_os.subprocess, 'run', run)
        patch.start()
        self.addCleanup(patch.stop)
        return run

    def test_mac_le_ps(self):
        run = self.run_ps({('ppid=,comm=', '42'): '  1 /Applications/Claude.app/Contents/MacOS/claude\n',
                           ('lstart=', '42'): 'Wed Oct 29 10:00:00 2026\n',
                           ('command=', '42'): 'node /usr/local/bin/claude --flag\n'})
        self.assertEqual(speak_os.parent(42), 1)
        self.assertEqual(speak_os.name(42), 'claude')
        start = speak_os.started(42)
        self.assertRegex(start, r'[0-9]+')
        self.assertEqual(speak_os.started(42), start)
        self.assertEqual(speak_os.started_at(42), float(start))
        self.assertEqual(speak_os.start_epoch(start), float(start))
        self.assertEqual(speak_os.argv(42), ['node', '/usr/local/bin/claude', '--flag'])

    def test_comm_with_spaces(self):
        self.run_ps({('ppid=,comm=', '5'): ' 9 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n'})
        self.assertEqual(speak_os.parent(5), 9)
        self.assertEqual(speak_os.name(5), 'Google Chrome')

    def test_one_ps_call_per_ancestor(self):
        run = self.run_ps({('ppid=,comm=', '50'): ' 40 /bin/zsh\n', ('ppid=,comm=', '40'): ' 1 /usr/bin/login\n'})
        self.assertEqual(speak_os.ancestors(50), [(50, 'zsh'), (40, 'login')])
        self.assertEqual(len(run.calls), 2)

    def test_ancestors_when_ps_fails(self):
        self.run_ps({})
        self.assertEqual(speak_os.ancestors(50), [(50, '?')])

    def as_mac_everywhere(self):
        """Mac also for the speak_os module that bin/speak imported (a separate instance); no CLAUDE_SPEAK_SESSION."""
        for patch in (mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'), mock.patch.object(speak_os, 'SYSTEM', 'mac'),
                      mock.patch.dict(os.environ, {}),
                      mock.patch.object(speak.os, 'getppid', return_value=60)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop('CLAUDE_SPEAK_SESSION', None)

    def test_mac_node(self):
        run = self.run_ps({('ppid=,comm=', '60'): ' 50 bash\n', ('ppid=,comm=', '50'): ' 1 /usr/local/bin/node\n',
                           ('command=', '60'): 'bash\n', ('command=', '50'): 'node /usr/local/bin/claude\n',
                           ('lstart=', '50'): 'Wed Oct 29 10:00:00 2026\n'})
        self.assertEqual(speak_os.name(50), 'node')
        self.assertEqual(speak_os.argv(50), ['node', '/usr/local/bin/claude'])
        self.as_mac_everywhere()
        run.calls.clear()
        self.assertRegex(speak.current_session(), r'50-[0-9]+')
        walk = [c for c in run.calls if c[2] == 'ppid=,comm=']
        self.assertEqual([c[4] for c in walk], ['60', '50'])  # one ps call per level, not two

    def test_ps_falha(self):
        self.as_mac_everywhere()
        for failure in (OSError('no ps'), None):
            tried = []

            def run(cmd, **kw):
                tried.append(cmd)
                if failure:
                    raise failure
                return subprocess.CompletedProcess(cmd, 0, '', '')
            with mock.patch.object(speak_os.subprocess, 'run', run):
                self.assertIsNone(speak_os.parent(60))
                self.assertIsNone(speak_os.name(60))
                self.assertIsNone(speak_os.started(60))
                self.assertIsNone(speak_os.started_at(60))
                self.assertIsNone(speak_os.argv(60))
                self.assertEqual(speak_os.ancestors(60), [(60, '?')])
                del tried[:]
                self.assertIsNone(speak.current_session())
                self.assertTrue(tried, 'the Mac path (ps) was not taken')

    def test_alive_uses_kill_zero(self):
        with mock.patch.object(speak_os.os, 'kill') as kill:
            self.assertTrue(speak_os.alive(7))
            kill.assert_called_with(7, 0)
            kill.side_effect = ProcessLookupError
            self.assertFalse(speak_os.alive(7))
            kill.side_effect = PermissionError
            self.assertTrue(speak_os.alive(7))

    def test_session_started_from_key_without_asking_the_process(self):
        with mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'), \
                mock.patch.object(speak.speak_os.subprocess, 'run', side_effect=AssertionError('asked ps')):
            self.assertEqual(speak.session_started('50-1793354400'), 1793354400.0)

    # --- sound and microphone on the Mac, with everything the Mac would provide replaced by fakes ----------------

    def test_mac_player_afplay(self):
        self.as_mac_everywhere()
        with mock.patch.object(speak_os.shutil, 'which', lambda n: '/usr/bin/afplay' if n == 'afplay' else None):
            self.assertEqual(speak_os.player(), ['afplay'])
            self.assertEqual(speak.player_command(), ['afplay'])
            self.assertTrue(speak.player_found())
        with mock.patch.object(speak_os.shutil, 'which', lambda n: None):
            self.assertIsNone(speak_os.player())
            self.assertFalse(speak.player_found())

    def test_streams_by_system(self):
        with mock.patch.object(speak_os, 'SYSTEM', 'linux'):
            self.assertTrue(speak_os.streams())
        with mock.patch.object(speak_os, 'SYSTEM', 'mac'):
            self.assertFalse(speak_os.streams())

    def core(self, devices, channels=None, running=None, fail=None, outputs=(), broken=()):
        class Core:
            def default_outputs(self):
                return list(outputs)

            def devices(self):
                if fail:
                    raise OSError('coreaudio')
                return devices

            def input_channels(self, dev):
                if dev in broken:
                    raise OSError('slay')
                return (channels or {}).get(dev, 0)

            def running(self, dev):
                return (running or {}).get(dev, False)
        return Core()

    def test_mac_mic_ctypes(self):
        self.as_mac_everywhere()
        cases = [  # (fake CoreAudio, expected)
            (self.core([1, 2], {2: 1}, {2: True}), True),  # an input device is running
            (self.core([1, 2], {2: 1}, {1: True}), False),  # only an output device is running
            (self.core([1, 2], {2: 1}, {}), False),  # input device idle
            (self.core([]), False),  # no devices
            (self.core([1], fail=True), None)]  # CoreAudio fails
        for core, expected in cases:
            with mock.patch.object(speak_os, '_coreaudio', return_value=core):
                self.assertIs(speak_os.mic_busy(), expected)
        with mock.patch.object(speak_os, '_coreaudio', return_value=None):
            self.assertIsNone(speak_os.mic_busy())

    def test_mac_mic_ignores_the_default_output(self):
        self.as_mac_everywhere()
        duplex = {5: 1, 6: 1}  # 5: headset (input and output, running because afplay plays), 6: another microphone
        for outputs in ([5], [9, 5]):  # the default output, or the system output, is the headset
            for running, expected in (({5: True}, False), ({5: True, 6: True}, True)):
                core = self.core([5, 6], duplex, running, outputs=outputs)
                with mock.patch.object(speak_os, '_coreaudio', return_value=core):
                    self.assertIs(speak_os.mic_busy(), expected, (outputs, running))

    def test_mac_mic_skips_a_device_that_errors(self):
        self.as_mac_everywhere()
        core = self.core([4, 6], {4: 1, 6: 1}, {4: True, 6: True}, broken=(4,))
        with mock.patch.object(speak_os, '_coreaudio', return_value=core):
            self.assertIs(speak_os.mic_busy(), True)  # 4 is skipped, 6 answers
        core = self.core([4], {4: 1}, {4: True}, broken=(4,))
        with mock.patch.object(speak_os, '_coreaudio', return_value=core):
            self.assertIs(speak_os.mic_busy(), False)

    def test_notices_come_from_the_system_piece(self):
        with mock.patch.object(speak_os, 'SYSTEM', 'mac'):
            self.assertIn('brew install uv', speak_os.notice_uv())
            self.assertEqual(speak_os.player_names(), 'afplay')
        with mock.patch.object(speak_os, 'SYSTEM', 'linux'):
            self.assertNotIn('brew', speak_os.notice_uv())
            self.assertIn('aplay', speak_os.player_names())
        with mock.patch.object(speak_os, '_coreaudio', side_effect=OSError('no framework')):
            self.assertIsNone(speak_os.mic_busy())

    def test_coreaudio_is_never_loaded_on_linux(self):
        with mock.patch.object(speak_os, 'SYSTEM', 'mac'), mock.patch.object(speak_os.sys, 'platform', 'linux'), \
                mock.patch('ctypes.CDLL', side_effect=AssertionError('loaded')):
            self.assertIsNone(speak_os._coreaudio())
            self.assertIsNone(speak_os.mic_busy())

    def test_linux_mic_reads_pw_dump(self):
        dump = b'[{"id": 9, "info": {"props": {"media.class": "Stream/Input/Audio"}}}]'
        done = subprocess.CompletedProcess([], 0, dump, b'')
        with mock.patch.object(speak_os, 'SYSTEM', 'linux'), \
                mock.patch.object(speak_os.subprocess, 'run', return_value=done):
            self.assertTrue(speak_os.mic_busy())
            self.assertEqual(speak_os.recordings_now(), {9})
        with mock.patch.object(speak_os, 'SYSTEM', 'linux'), \
                mock.patch.object(speak_os.subprocess, 'run', side_effect=OSError):
            self.assertIsNone(speak_os.mic_busy())

    def mac_play(self, sounddevice, pieces=('um', 'dois'), watch_mic=None, linux=False):
        """Runs speak.play('...') as on the Mac with fakes: kokoro, soundfile, afplay (Popen) and `sounddevice`
        (a module, or None for "cannot be imported"). Returns (code, afplay commands, wavs written, state folder)."""
        import tempfile
        import types
        if linux:
            for patch in (mock.patch.object(speak.speak_os, 'SYSTEM', 'linux'),
                          mock.patch.object(speak.speak_os, 'player', lambda: ['aplay'])):
                patch.start()
                self.addCleanup(patch.stop)
        else:
            self.as_mac_everywhere()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = os.path.join(tmp.name, 'state')
        os.makedirs(os.path.join(state, 'queue'))
        wavs, launched = [], []

        class Kokoro:
            def __init__(self, *a):
                pass

            def create(self, piece, **kw):
                return (FakeSamples(piece), 24000)

        kokoro = types.ModuleType('kokoro_onnx')
        kokoro.Kokoro = Kokoro
        sound = types.ModuleType('soundfile')

        def write(path, samples, rate):
            with open(path, 'wb') as fh:
                fh.write(b'RIFF')
            wavs.append(path)
        sound.write = write

        class Proc:
            def __init__(self, cmd):
                launched.append(cmd)
                self.existed = os.path.exists(cmd[1])

            def wait(self):
                return 0

            def kill(self):
                pass

        class LinuxProc(Proc):
            def __init__(self, cmd):
                launched.append(cmd)
                self.stdin = io.BytesIO()
                self.stdin.close = lambda: None
        popen = (lambda cmd, **kw: LinuxProc(cmd)) if linux else (lambda cmd, **kw: Proc(cmd))
        patches = [
            mock.patch.dict(sys.modules, {'kokoro_onnx': kokoro, 'soundfile': sound, 'sounddevice': sounddevice}),
            mock.patch.dict(os.environ, {'CLAUDE_SPEAK_TEST': '1', 'CLAUDE_SPEAK_SESSION': '-'}),
            mock.patch.object(speak, 'STATE', state),
            mock.patch.object(speak, 'QUEUE', os.path.join(state, 'queue')),
            mock.patch.object(speak, 'PID', os.path.join(state, 'speech.pid')),
            mock.patch.object(speak, 'OWNER', os.path.join(state, 'speech.owner')),
            mock.patch.object(speak, 'LOCK', os.path.join(state, 'queue.lock')),
            mock.patch.object(speak, 'QUEUE_POLL', 0.01), mock.patch.object(speak, 'MIC_POLL', 0.01),
            mock.patch.object(speak, 'pieces', lambda text: list(pieces)),
            mock.patch.object(speak.speak_os, '_coreaudio', return_value=self.core([1], {1: 1}, {})),
            mock.patch.object(speak.shutil, 'which', lambda n: '/usr/bin/afplay' if n == 'afplay' else None),
            mock.patch.object(speak.subprocess, 'Popen', popen)]
        if watch_mic:
            patches.append(mock.patch.object(speak, 'current_recordings', watch_mic))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return speak.play('x'), launched, wavs, state

    def test_play_mac_arquivo_por_pedaco(self):
        code, launched, wavs, state = self.mac_play(None)  # sounddevice cannot be imported: afplay for every piece
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in launched], ['afplay', 'afplay'])
        self.assertEqual([c[1] for c in launched], wavs)
        self.assertEqual(len(set(wavs)), 2)
        self.assertTrue(all(os.path.dirname(w) == state for w in wavs))
        self.assertEqual([n for n in os.listdir(state) if n.endswith('.wav')], [])

    def test_play_mac_sounddevice_em_fluxo(self):
        sd = FakeSoundDevice()
        code, launched, wavs, state = self.mac_play(sd)
        self.assertEqual(code, 0)
        self.assertEqual(sd.stream.written, ['um', 'dois'])
        self.assertEqual((launched, wavs), ([], []))
        self.assertEqual(sd.stream.events, ['start', 'write', 'write', 'stop', 'close'])
        self.assertEqual(sd.opened, [{'samplerate': 24000, 'channels': 1, 'dtype': 'float32'}])

    def test_play_mac_sounddevice_abrir_falha_cai_para_afplay(self):
        sd = FakeSoundDevice(fail_open=True)
        code, launched, wavs, state = self.mac_play(sd)
        self.assertEqual((code, len(launched), len(wavs)), (0, 2, 2))
        self.assertEqual([n for n in os.listdir(state) if n.endswith('.wav')], [])

    def test_play_mac_sounddevice_falha_no_segundo_pedaco(self):
        sd = FakeSoundDevice(fail_write_at=2)
        code, launched, wavs, state = self.mac_play(sd, pieces=('um', 'dois', 'tres'))
        self.assertEqual(code, 0)
        self.assertEqual(sd.stream.written, ['um'])  # the first piece went out through the stream
        self.assertEqual(len(launched), 2)  # the second (played again) and the third through afplay
        self.assertEqual(len(wavs), 2)
        self.wait_closed(sd)
        self.assertEqual(sd.stream.events.count('close'), 1)
        self.assertEqual([n for n in os.listdir(state) if n.endswith('.wav')], [])

    def wait_closed(self, sd):
        """The stream is closed in a daemon thread after a failure: waits (up to 2 s) for that."""
        import time
        end = time.time() + 2
        while 'close' not in sd.stream.events and time.time() < end:
            time.sleep(0.01)

    def fast_deadline(self):
        for patch in (mock.patch.object(speak, 'STREAM_SLACK', 0.1),):
            patch.start()
            self.addCleanup(patch.stop)

    def test_play_mac_sounddevice_escrita_que_nao_volta_cai_para_afplay(self):
        import time
        self.fast_deadline()
        sd = FakeSoundDevice(hang_write_at=2)
        start = time.time()
        code, launched, wavs, state = self.mac_play(sd, pieces=('um', 'dois', 'tres'))
        self.assertLess(time.time() - start, 3)
        self.assertEqual(code, 0)
        self.assertEqual(sd.stream.written, ['um'])
        self.assertEqual(len(launched), 2)  # the piece that hung and the next one, by afplay
        self.wait_closed(sd)
        self.assertIn('abort', sd.stream.events)
        self.assertEqual(sd.stream.events.count('close'), 1)
        self.assertEqual([n for n in os.listdir(state) if n.endswith('.wav')], [])

    def test_play_mac_sounddevice_stop_que_trava_termina_no_prazo(self):
        import time
        self.fast_deadline()
        sd = FakeSoundDevice(hang_stop=True)
        start = time.time()
        code, launched, wavs, state = self.mac_play(sd)
        self.assertLess(time.time() - start, 3)
        self.assertEqual((code, launched), (0, []))
        self.assertEqual(sd.stream.written, ['um', 'dois'])
        self.wait_closed(sd)
        self.assertEqual(sd.stream.events.count('close'), 1)

    def test_play_mac_sounddevice_start_falha_fecha_o_fluxo(self):
        sd = FakeSoundDevice(fail_start=True)
        code, launched, wavs, state = self.mac_play(sd)
        self.assertEqual((code, len(launched)), (0, 2))
        self.assertEqual(sd.stream.events, ['start', 'close'])

    def test_stream_close_is_once_even_from_two_threads(self):
        import threading
        sd = FakeSoundDevice()
        with mock.patch.dict(sys.modules, {'sounddevice': sd}):
            player = speak.StreamPlayer()
        gate = threading.Barrier(2)
        real = sd.stream.close

        def slow_close():
            real()
        sd.stream.close = slow_close

        def closer():
            gate.wait()
            player.close()
        threads = [threading.Thread(target=closer) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sd.stream.events.count('close'), 1)

    def test_play_mac_corte_pelo_microfone_no_sounddevice(self):
        import threading
        sd = FakeSoundDevice(block_write_at=1)
        cut = threading.Event()
        calls = []

        def recording():
            calls.append(1)
            return {7} if sd.stream and sd.stream.blocked.is_set() else set()  # busy once the first write is waiting

        def cut_now(player):
            player.kill()
            cut.set()
        with mock.patch.object(speak, 'cut_by_microphone', cut_now):
            code, launched, wavs, state = self.mac_play(sd, watch_mic=recording)
        self.assertTrue(cut.is_set())
        self.assertEqual(launched, [])  # nothing more played, not even by afplay
        self.wait_closed(sd)
        self.assertEqual(sd.stream.events[-2:], ['abort', 'close'])
        self.assertEqual(sd.stream.events.count('abort'), 1)
        self.assertEqual(sd.stream.events.count('close'), 1)

    def test_linux_never_imports_sounddevice(self):
        sd = FakeSoundDevice()
        code, launched, wavs, state = self.mac_play(sd, linux=True)
        self.assertEqual(code, 0)
        self.assertEqual([c[0] for c in launched], ['aplay'])  # one stdin player, as before
        self.assertEqual((sd.opened, wavs), ([], []))

    # --- speak install on the Mac and on Linux ------------------------------------------------------------------

    def install_run(self, system, sounddevice_ok):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        model, voices = os.path.join(tmp.name, 'm'), os.path.join(tmp.name, 'v')
        for path in (model, voices):
            open(path, 'w').close()
        calls = []

        def call(cmd, **kw):
            calls.append(cmd)
            return 0 if sounddevice_ok or cmd[-1] != 'sounddevice' else 1
        out = io.StringIO()
        with mock.patch.object(speak.speak_os, 'SYSTEM', system), mock.patch.object(speak, 'DATA', tmp.name), \
                mock.patch.object(speak, 'MODEL', model), mock.patch.object(speak, 'VOICES', voices), \
                mock.patch.object(speak, 'venv_works', lambda: True), \
                mock.patch.object(speak.shutil, 'which', lambda n: '/usr/bin/uv'), \
                mock.patch.object(speak.os.path, 'exists', lambda p: True), \
                mock.patch.object(speak.subprocess, 'check_call', call), \
                mock.patch.object(speak.subprocess, 'call', call), mock.patch('sys.stdout', out):
            code = speak.install()
        return code, calls, out.getvalue()

    def test_install_mac_sounddevice_falha_nao_derruba(self):
        code, calls, out = self.install_run('mac', False)
        self.assertEqual(code, 0)
        self.assertEqual([c[-1] for c in calls], ['kokoro-onnx', 'sounddevice'])
        self.assertIn('voz: sounddevice não instalou; o Mac toca pelo afplay', out)

    def test_install_mac_sounddevice_ok_e_linux_sem_sounddevice(self):
        code, calls, out = self.install_run('mac', True)
        self.assertEqual((code, [c[-1] for c in calls]), (0, ['kokoro-onnx', 'sounddevice']))
        self.assertNotIn('afplay', out)
        code, calls, out = self.install_run('linux', True)
        self.assertEqual((code, [c[-1] for c in calls]), (0, ['kokoro-onnx']))


class FakeSamples:
    def __init__(self, tag):
        self.tag = tag

    def astype(self, kind):
        return self

    def tobytes(self):
        return b'\0'

    def __len__(self):
        return 24

    def reshape(self, *shape):
        return self


class FakeStream:
    def __init__(self, owner):
        import threading
        self.events, self.written, self.count = [], [], 0
        self.owner = owner
        self.fail_write_at, self.block_write_at = owner.fail_write_at, owner.block_write_at
        self.hung = threading.Event()  # never set by the stream: a call that waits on it hangs until the test ends
        self.blocked, self.released = threading.Event(), threading.Event()

    def start(self):
        self.events.append('start')
        if self.owner.fail_start:
            raise OSError('cannot start')

    def write(self, samples):
        self.count += 1
        self.events.append('write')
        if self.count == self.owner.hang_write_at:
            self.hung.wait(5)
            return
        if self.count == self.fail_write_at:
            raise OSError('PortAudio write failed')
        if self.count == self.block_write_at:
            self.blocked.set()
            self.released.wait(5)
            raise OSError('stream aborted')
        self.written.append(samples.tag)

    def stop(self):
        self.events.append('stop')
        if self.owner.hang_stop:
            self.hung.wait(5)

    def abort(self):
        self.events.append('abort')
        self.released.set()

    def close(self):
        self.events.append('close')


class FakeSoundDevice:
    """A stand-in for the `sounddevice` module."""

    def __init__(self, fail_open=False, fail_write_at=None, block_write_at=None, hang_write_at=None,
                 hang_stop=False, fail_start=False):
        self.fail_open, self.opened, self.stream = fail_open, [], None
        self.fail_write_at, self.block_write_at = fail_write_at, block_write_at
        self.hang_write_at, self.hang_stop, self.fail_start = hang_write_at, hang_stop, fail_start

    def OutputStream(self, **kw):
        if self.fail_open:
            raise OSError('no output device')
        self.opened.append(kw)
        self.stream = FakeStream(self)
        return self.stream


class CheckTest(unittest.TestCase):
    def test_check_prints_ancestors_on_stderr_only(self):
        out = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'bin', 'speak'), 'check'],
                             capture_output=True, text=True, env={**os.environ, 'HOME': '/nonexistent-home-for-test'})
        self.assertIn('processos acima: ', out.stderr)
        self.assertNotIn('processos acima', out.stdout)


if __name__ == '__main__':
    unittest.main()
