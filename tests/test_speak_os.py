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
        self.assertEqual(speak_os.argv(me)[0:1], [speak_os.argv(me)[0]])
        self.assertAlmostEqual(speak_os.started_at(me), speak.session_started(speak.session_key(me)), places=3)
        self.assertEqual(speak_os.ancestors(me)[0][0], me)


class MacTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(speak_os, 'SYSTEM', 'mac')
        patch.start()
        self.addCleanup(patch.stop)

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

    def test_mac_node(self):
        self.run_ps({('ppid=,comm=', '60'): ' 50 bash\n', ('ppid=,comm=', '50'): ' 1 /usr/local/bin/node\n',
                     ('command=', '60'): 'bash\n', ('command=', '50'): 'node /usr/local/bin/claude\n'})
        self.assertEqual(speak_os.name(50), 'node')
        self.assertEqual(speak_os.argv(50), ['node', '/usr/local/bin/claude'])
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(speak.speak_os, 'SYSTEM', 'mac'), \
                mock.patch.object(speak.os, 'getppid', return_value=60):
            os.environ.pop('CLAUDE_SPEAK_SESSION', None)
            self.run_ps({('ppid=,comm=', '60'): ' 50 bash\n', ('ppid=,comm=', '50'): ' 1 /usr/local/bin/node\n',
                         ('command=', '60'): 'bash\n', ('command=', '50'): 'node /usr/local/bin/claude\n',
                         ('lstart=', '50'): 'Wed Oct 29 10:00:00 2026\n'})
            key = speak.current_session()
        self.assertRegex(key, r'50-[0-9]+')

    def test_ps_falha(self):
        for failure in (OSError('no ps'), None):
            def run(cmd, **kw):
                if failure:
                    raise failure
                return subprocess.CompletedProcess(cmd, 0, '', '')
            with mock.patch.object(speak_os.subprocess, 'run', run), \
                    mock.patch.object(speak.os, 'getppid', return_value=60), \
                    mock.patch.dict(os.environ, {}):
                os.environ.pop('CLAUDE_SPEAK_SESSION', None)
                self.assertIsNone(speak_os.parent(60))
                self.assertIsNone(speak_os.name(60))
                self.assertIsNone(speak_os.started(60))
                self.assertIsNone(speak_os.started_at(60))
                self.assertIsNone(speak_os.argv(60))
                self.assertEqual(speak_os.ancestors(60), [(60, '?')])
                self.assertIsNone(speak.current_session())

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


class CheckTest(unittest.TestCase):
    def test_check_prints_ancestors_on_stderr_only(self):
        out = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'bin', 'speak'), 'check'],
                             capture_output=True, text=True, env={**os.environ, 'HOME': '/nonexistent-home-for-test'})
        self.assertIn('processos acima: ', out.stderr)
        self.assertNotIn('processos acima', out.stdout)


if __name__ == '__main__':
    unittest.main()
