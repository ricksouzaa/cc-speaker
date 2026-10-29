"""The data root of `speak` (lib/speak_paths.py), the one-time move from the former folders, the engine environment
check of `speak install` and the line the SessionStart hook writes to CLAUDE_ENV_FILE. Every folder is below a
temporary HOME; nothing real is touched."""
import importlib.machinery
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import isolation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
import speak_paths  # noqa: E402

START = os.path.join(ROOT, 'hooks', 'speak-start.py')
SPEAK = os.path.join(ROOT, 'bin', 'speak')
FALLBACK = ('.claude', 'plugins', 'data', 'speak-cc-speaker')


def put(path, text=''):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fh:
        fh.write(text)


def tearDownModule():
    isolation.assert_untouched(unittest.TestCase())


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = tmp.name
        isolation.scrub_environ(self, self.home)

    def path(self, *parts):
        return os.path.join(self.home, *parts)


class Root(Base):
    def test_raiz_pela_variavel(self):
        os.environ['CLAUDE_SPEAK_DATA'] = '/x'
        self.assertEqual(speak_paths.root(self.path('qualquer', 'bin', 'speak')), '/x')

    def test_a_variavel_do_claude_code_nao_conta(self):
        """The panel module never gets it, the hooks do: reading it would give them two folders."""
        os.environ['CLAUDE_PLUGIN_DATA'] = '/x'
        script = self.path('dev', 'cc-speaker', 'bin', 'speak')
        self.assertEqual(speak_paths.root(script), self.path(*FALLBACK))
        cached = self.path('.claude', 'plugins', 'cache', 'cat', 'plug', '1.0', 'bin', 'speak')
        self.assertEqual(speak_paths.root(cached), self.path('.claude', 'plugins', 'data', 'plug-cat'))

    def test_raiz_pela_variavel_do_speak(self):
        os.environ['CLAUDE_SPEAK_DATA'] = '/s'
        self.assertEqual(speak_paths.root(self.path('qualquer', 'bin', 'speak')), '/s')

    def test_raiz_pelo_lugar_do_script(self):
        script = self.path('.claude', 'plugins', 'cache', 'cat', 'plug', '1.0', 'bin', 'speak')
        self.assertEqual(speak_paths.root(script), self.path('.claude', 'plugins', 'data', 'plug-cat'))

    def test_raiz_reserva(self):
        script = self.path('dev', 'cc-speaker', 'bin', 'speak')
        self.assertEqual(speak_paths.root(script), self.path(*FALLBACK))
        os.environ['CLAUDE_CONFIG_DIR'] = '/c'
        self.assertEqual(speak_paths.root(script), '/c/plugins/data/speak-cc-speaker')

    def test_subpastas(self):
        os.environ['CLAUDE_SPEAK_DATA'] = '/x'
        self.assertEqual(speak_paths.paths('/y/bin/speak'), ('/x/engine', '/x/config', '/x/state'))


class MoveOnce(Base):
    def old(self):
        put(self.path('.local', 'share', 'claude-speak', 'model.onnx'), 'm')
        put(self.path('.config', 'claude-speak', 'voice'), 'pm_alex')
        put(self.path('.local', 'state', 'claude-speak', 'sessions', 'k'), '{}')
        put(self.path('.local', 'state', 'claude-speak', 'phone', 'x'), 'p')

    def test_muda_uma_vez(self):
        self.old()
        base = self.path(*FALLBACK)
        self.assertEqual(speak_paths.migrate_old(base), ['engine', 'config', 'state'])
        self.assertTrue(os.path.exists(os.path.join(base, 'engine', 'model.onnx')))
        self.assertTrue(os.path.exists(os.path.join(base, 'config', 'voice')))
        self.assertTrue(os.path.exists(os.path.join(base, 'state', 'sessions', 'k')))
        self.assertFalse(os.path.exists(os.path.join(base, 'state', 'phone')))
        for old in ('.local/share', '.config', '.local/state'):
            self.assertFalse(os.path.exists(self.path(old, 'claude-speak')), old)
        self.assertEqual(speak_paths.migrate_old(base), [])

    def test_xdg_vale_so_para_achar_as_antigas(self):
        put(self.path('xdg', 'claude-speak', 'voice'), 'v')
        os.environ['XDG_CONFIG_HOME'] = self.path('xdg')
        self.assertEqual(speak_paths.migrate_old(self.path('r')), ['config'])
        self.assertTrue(os.path.exists(self.path('r', 'config', 'voice')))

    def test_nova_vence(self):
        self.old()
        base = self.path(*FALLBACK)
        os.makedirs(os.path.join(base, 'engine'))
        self.assertEqual(speak_paths.migrate_old(base), ['config', 'state'])
        self.assertTrue(os.path.exists(self.path('.local', 'share', 'claude-speak', 'model.onnx')))
        self.assertFalse(os.path.exists(os.path.join(base, 'engine', 'model.onnx')))
        self.assertTrue(os.path.exists(os.path.join(base, 'config', 'voice')))

    def test_destino_existente_deixa_a_pasta_antiga_intacta(self):
        self.old()
        base = self.path(*FALLBACK)
        put(os.path.join(base, 'config', 'voice'), 'nova')
        self.assertEqual(speak_paths.migrate_old(base), ['engine', 'state'])
        self.assertTrue(os.path.exists(self.path('.config', 'claude-speak', 'voice')))
        with open(os.path.join(base, 'config', 'voice')) as fh:
            self.assertEqual(fh.read(), 'nova')

    def test_motor_ja_presente_config_antiga_ainda_muda(self):
        put(self.path(*FALLBACK, 'engine', 'm'), 'm')
        put(self.path('.config', 'claude-speak', 'voice'), 'v')
        self.assertEqual(speak_paths.migrate_old(self.path(*FALLBACK)), ['config'])
        self.assertTrue(os.path.exists(self.path(*FALLBACK, 'config', 'voice')))

    def test_pelo_comando_speak(self):
        self.old()
        env = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-'}
        subprocess.run([sys.executable, '-I', SPEAK, 'status'], capture_output=True, text=True, env=env)
        self.assertTrue(os.path.exists(self.path(*FALLBACK, 'engine', 'model.onnx')))
        self.assertFalse(os.path.exists(self.path('.local', 'state', 'claude-speak')))

    def test_copia_que_falha_no_meio_nao_deixa_destino_pela_metade(self):
        put(self.path('src', 'a'), '1')
        put(self.path('src', 'b'), '2')

        def copy_then_fail(src, dst, **kw):
            os.makedirs(dst)  # half a copy: the destination exists, with one file in it
            put(os.path.join(dst, 'a'), '1')
            raise OSError('disco cheio')

        with mock.patch.object(speak_paths.os, 'rename', side_effect=OSError('outro disco')), \
                mock.patch.object(speak_paths.shutil, 'copytree', side_effect=copy_then_fail):
            self.assertFalse(speak_paths.move_dir(self.path('src'), self.path('dst')))
        self.assertFalse(os.path.exists(self.path('dst')))
        self.assertTrue(os.path.exists(self.path('src', 'a')) and os.path.exists(self.path('src', 'b')))

    def test_destino_que_aparece_na_corrida_nao_e_apagado(self):
        put(self.path('src', 'a'), '1')
        real_rename = os.rename

        def other_wins(src, dst):
            if dst == self.path('dst'):
                put(self.path('dst', 'vencedor'), 'w')
                raise OSError('destino existe')
            return real_rename(src, dst)

        with mock.patch.object(speak_paths.os, 'rename', side_effect=other_wins):
            self.assertFalse(speak_paths.move_dir(self.path('src'), self.path('dst')))
        self.assertTrue(os.path.exists(self.path('dst', 'vencedor')))
        self.assertTrue(os.path.exists(self.path('src', 'a')))
        self.assertEqual([n for n in os.listdir(self.home) if '.part' in n], [])

    def leftovers(self):
        return sorted(n for n in os.listdir(self.home) if '.part' in n)

    def other_disk(self, src_path):
        """An os.rename that refuses to move `src_path` (as between two disks) and does everything else for real."""
        real_rename = os.rename

        def rename(src, dst):
            if src == src_path:
                raise OSError('outro disco')
            return real_rename(src, dst)
        return rename

    def test_cada_falha_da_copia_remove_o_arquivo_temporario(self):
        """Whatever stops the copy between two disks (a file that cannot be read, a destination that appears, the final
        rename failing, an error nobody expected), `<destino>.part-<pid>` is gone afterwards; the source stays."""
        real_rename = os.rename
        real_copyfile, real_copytree = shutil.copyfile, shutil.copytree
        src, dst = self.path('src'), self.path('dst')

        def copy_fails_at_b(a, b, **kw):
            if os.path.basename(a) == 'b':
                raise OSError('disco cheio')
            return real_copyfile(a, b, **kw)

        def final_rename_fails(a, b):
            if a == src:
                raise OSError('outro disco')
            if b == dst:
                raise OSError('rename final falhou')
            return real_rename(a, b)

        def winner_appears(a, b):
            if a == src:
                raise OSError('outro disco')
            put(os.path.join(dst, 'vencedor'), 'w')
            raise OSError('destino existe')

        def copy_then_crash(a, b, **kw):
            os.makedirs(b)  # half a copy, then something nobody expected (not an OSError)
            raise RuntimeError('inesperado')

        cases = {  # name: (os.rename, shutil.copyfile, shutil.copytree, exception the call lets through)
            'um arquivo falha no meio': (self.other_disk(src), copy_fails_at_b, real_copytree, None),
            'rename final falha': (final_rename_fails, real_copyfile, real_copytree, None),
            'o destino aparece': (winner_appears, real_copyfile, real_copytree, None),
            'erro inesperado': (self.other_disk(src), real_copyfile, copy_then_crash, RuntimeError),
        }
        for name, (rename, copyfile, copytree, raises) in cases.items():
            with self.subTest(name):
                shutil.rmtree(src, ignore_errors=True)
                shutil.rmtree(dst, ignore_errors=True)
                put(os.path.join(src, 'a'), '1')
                put(os.path.join(src, 'b'), '2')
                with mock.patch.object(speak_paths.os, 'rename', side_effect=rename), \
                        mock.patch.object(shutil, 'copyfile', copyfile), \
                        mock.patch.object(shutil, 'copytree', copytree):
                    if raises:
                        with self.assertRaises(raises):
                            speak_paths.move_dir(src, dst)
                    else:
                        self.assertFalse(speak_paths.move_dir(src, dst))
                self.assertEqual(self.leftovers(), [])
                self.assertTrue(os.path.exists(os.path.join(src, 'a')) and os.path.exists(os.path.join(src, 'b')))

    def test_copia_entre_discos_que_funciona_remove_a_origem(self):
        put(self.path('src', 'sub', 'a'), '1')
        real_rename = os.rename

        def cross_disk(src, dst):
            if src == self.path('src'):
                raise OSError('outro disco')
            return real_rename(src, dst)

        with mock.patch.object(speak_paths.os, 'rename', side_effect=cross_disk):
            self.assertTrue(speak_paths.move_dir(self.path('src'), self.path('dst')))
        self.assertTrue(os.path.exists(self.path('dst', 'sub', 'a')))
        self.assertFalse(os.path.exists(self.path('src')))


class EnvFile(Base):
    def run_hook(self, env_file, **env):
        e = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_SESSION': '-', 'CLAUDE_SPEAK_AUTOINSTALL': '0',
             'CLAUDE_ENV_FILE': env_file, **env}
        return subprocess.run([sys.executable, '-I', START], input='{}', capture_output=True, text=True, env=e)

    def test_env_file(self):
        target = self.path('env.sh')
        open(target, 'w').close()
        r = self.run_hook(target, CLAUDE_SPEAK_DATA=self.path('dados'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.run_hook(target, CLAUDE_SPEAK_DATA=self.path('dados'))
        with open(target) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines, ['export CLAUDE_SPEAK_DATA=%s' % self.path('dados')])

    def test_a_variavel_do_claude_code_nao_muda_a_pasta_exportada(self):
        target = self.path('env.sh')
        open(target, 'w').close()
        self.run_hook(target, CLAUDE_PLUGIN_DATA=self.path('dados'))
        with open(target) as fh:
            self.assertNotIn(self.path('dados'), fh.read())

    def test_a_variavel_herdada_do_speak_vence_a_de_outro_plugin(self):
        target = self.path('env.sh')
        open(target, 'w').close()
        self.run_hook(target, CLAUDE_SPEAK_DATA=self.path('dados'), CLAUDE_PLUGIN_DATA=self.path('outro'))
        with open(target) as fh:
            self.assertEqual(fh.read().splitlines(), ['export CLAUDE_SPEAK_DATA=%s' % self.path('dados')])

    def test_arquivo_de_ambiente_com_bytes_que_nao_sao_texto(self):
        """A CLAUDE_ENV_FILE that is not text must neither fail the session start nor be written twice: the bytes stay,
        the line is added once, and the rule is still printed."""
        target = self.path('env.sh')
        binary = b'\xff\xfe\x00\x80binario\n'
        with open(target, 'wb') as fh:
            fh.write(binary)
        for _ in range(2):
            r = self.run_hook(target, CLAUDE_SPEAK_DATA=self.path('dados'))
            self.assertEqual((r.returncode, r.stderr), (0, ''))
            self.assertIn('\U0001F50A', r.stdout)
        with open(target, 'rb') as fh:
            data = fh.read()
        self.assertTrue(data.startswith(binary))
        self.assertEqual(data[len(binary):], ('export CLAUDE_SPEAK_DATA=%s\n' % self.path('dados')).encode())

    def test_arquivo_de_ambiente_que_nao_da_para_abrir_nao_derruba_o_gancho(self):
        r = self.run_hook(self.path('e-uma-pasta'), CLAUDE_SPEAK_DATA=self.path('dados'))
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        os.makedirs(self.path('pasta'))
        r = self.run_hook(self.path('pasta'), CLAUDE_SPEAK_DATA=self.path('dados'))
        self.assertEqual((r.returncode, r.stderr), (0, ''))
        self.assertIn('\U0001F50A', r.stdout)

    def test_sem_a_variavel_do_arquivo_nada_e_escrito(self):
        r = subprocess.run([sys.executable, '-I', START], input='{}', capture_output=True, text=True,
                           env={'HOME': self.home, 'PATH': '/usr/bin:/bin', 'CLAUDE_SPEAK_AUTOINSTALL': '0',
                                'CLAUDE_SPEAK_SESSION': '-'})
        self.assertEqual(r.returncode, 0)


class Venv(Base):
    """`speak install` rebuilds the engine environment alone when its Python does not run."""

    def setUp(self):
        super().setUp()
        loader = importlib.machinery.SourceFileLoader('speak_for_venv', SPEAK)
        spec = importlib.util.spec_from_loader('speak_for_venv', loader)
        self.speak = importlib.util.module_from_spec(spec)
        loader.exec_module(self.speak)
        self.data = self.path('engine')
        self.py = os.path.join(self.data, '.venv', 'bin', 'python')
        for name, value in (('DATA', self.data), ('VENV_PY', self.py),
                            ('MODEL', os.path.join(self.data, 'm')), ('VOICES', os.path.join(self.data, 'v'))):
            patch = mock.patch.object(self.speak, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        put(os.path.join(self.data, 'm'))
        put(os.path.join(self.data, 'v'))

    def test_python_invalido_e_quebrado(self):
        put(self.py, 'isto nao e um executavel')
        os.chmod(self.py, 0o755)
        self.assertFalse(self.speak.venv_works())

    def test_link_quebrado_e_quebrado(self):
        os.makedirs(os.path.dirname(self.py))
        os.symlink(self.path('nao-existe'), self.py)
        self.assertTrue(os.path.lexists(self.py) and not os.path.exists(self.py))
        self.assertFalse(self.speak.venv_works())

    def test_python_que_roda_nao_e_quebrado(self):
        os.makedirs(os.path.dirname(self.py))
        os.symlink(sys.executable, self.py)
        self.assertTrue(self.speak.venv_works())

    def test_install_refaz_so_o_ambiente_quebrado(self):
        put(self.py, 'lixo')
        os.chmod(self.py, 0o755)
        calls = []
        uv = self.path('uv')
        put(uv)
        with mock.patch.object(self.speak.shutil, 'which', return_value=uv), \
                mock.patch.object(self.speak.subprocess, 'check_call', side_effect=lambda a: calls.append(a)), \
                mock.patch.object(self.speak.urllib.request, 'urlretrieve', side_effect=AssertionError('baixou')):
            with mock.patch('sys.stdout', new=io.StringIO()):
                self.assertEqual(self.speak.install(), 0)
        self.assertEqual(calls[0][:2], [uv, 'venv'])
        self.assertFalse(os.path.exists(self.py))  # the broken environment was removed before the new one


if __name__ == '__main__':
    unittest.main()
