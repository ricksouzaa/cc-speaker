"""Guard of the test battery: nothing under the real data folders may be created, changed or deleted by the tests.
The file name sorts last, so its test runs after all the others in `unittest discover`."""
import os
import tempfile
import unittest

import isolation


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.join(tmp.name, 'raiz')

    def put(self, name, text):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write(text)
        return path

    def test_sem_mudanca_nao_ha_diferenca(self):
        self.put('state/a', 'x')
        before = isolation.snapshot([self.root])
        self.assertEqual(isolation.differences(before, isolation.snapshot([self.root])), [])

    def test_arquivo_criado_mudado_e_apagado_aparecem(self):
        a = self.put('state/a', 'x')
        self.put('state/b', 'y')
        before = isolation.snapshot([self.root])
        os.remove(os.path.join(self.root, 'state', 'b'))
        with open(a, 'w') as fh:
            fh.write('xx')  # the size changes
        self.put('state/c', 'z')
        text = '\n'.join(isolation.differences(before, isolation.snapshot([self.root])))
        self.assertIn('apagado: %s' % os.path.join(self.root, 'state', 'b'), text)
        self.assertIn('mudado: %s' % a, text)
        self.assertIn('criado: %s' % os.path.join(self.root, 'state', 'c'), text)

    def test_raiz_inexistente_que_passa_a_existir_e_apanhada(self):
        before = isolation.snapshot([self.root])
        self.assertEqual(before, {})
        self.put('state/a', 'x')
        self.assertTrue(isolation.differences(before, isolation.snapshot([self.root])))


class SpeechNoise(unittest.TestCase):
    HOME = os.path.expanduser('~')

    def test_so_o_que_a_fala_real_escreve_e_ruido(self):
        state = os.path.join(self.HOME, '.claude', 'plugins', 'data', 'speak-cc-speaker', 'state')
        old = os.path.join(self.HOME, '.local', 'state', 'claude-speak')
        for path in (state, os.path.join(state, 'queue'), os.path.join(state, 'queue', '1-2'),
                     os.path.join(state, 'queue.lock'), os.path.join(state, 'speech.owner'),
                     os.path.join(state, 'sessions', 'k'), os.path.join(state, 'error.log'),
                     old, os.path.join(old, 'queue'), os.path.join(old, 'speech.pid')):
            self.assertTrue(isolation.is_speech_noise(path), path)
        for path in (os.path.join(state, 'install.lock'), os.path.join(state, 'all'),
                     os.path.join(self.HOME, '.claude', 'plugins', 'data', 'speak-cc-speaker', 'engine', 'queue'),
                     os.path.join(self.HOME, '.config', 'claude-speak', 'mode'),
                     os.path.join(old, 'install.progress')):
            self.assertFalse(isolation.is_speech_noise(path), path)

    PROCS = [(100, 1, ['python3', '-m', 'unittest']), (101, 100, ['py', '-I', '/x/bin/speak', '_play', 'oi']),
             (200, 1, ['py', '-I', '/c/0.7.3/bin/speak', '_play', 'oi']), (201, 1, ['py', '-I', '/c/bin/speak', 'say', '-']),
             (202, 1, ['py', '-I', '/c/bin/speak', 'status']), (203, 1, ['py', '-I', '/c/bin/speak', '_play', 'x'])]

    def test_processo_real_exclui_filho_da_bateria_e_o_de_home_temporaria(self):
        home = {200: isolation.pwd.getpwuid(os.getuid()).pw_dir, 201: isolation.pwd.getpwuid(os.getuid()).pw_dir,
                203: '/tmp/tmpabc'}
        found = isolation.real_speech_pids(self.PROCS, me=100, home_of=home.get)
        self.assertEqual(found, {200, 201} if os.path.isdir('/proc/self') else {200, 201, 203})

    def test_sem_fala_real_tudo_e_acusado_e_com_ela_so_o_ruido(self):
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        state = os.path.join(root, 'state')
        os.makedirs(state)
        before = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(before[0]),
                                 setattr(isolation, 'ROOTS', before[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root]
        isolation.BEFORE.update(isolation.snapshot([root]))
        open(os.path.join(state, 'queue.lock'), 'w').close()
        with self.assertRaises(AssertionError):
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set())
        isolation.assert_untouched(Case(), speech_after={5}, speech_before=set())
        isolation.assert_untouched(Case(), speech_after=set(), speech_before={5})
        open(os.path.join(state, 'install.lock'), 'w').close()
        with self.assertRaises(AssertionError):
            isolation.assert_untouched(Case(), speech_after={5}, speech_before=set())


class RealRoots(unittest.TestCase):
    def test_a_bateria_nao_tocou_na_raiz_real(self):
        isolation.assert_untouched(self)

    def test_o_ambiente_da_bateria_nao_leva_pastas_reais(self):
        self.assertEqual(isolation.START_ENV_LEAK, [], 'a bateria foi iniciada com variáveis CLAUDE_*/XDG_* de pastas')


if __name__ == '__main__':
    unittest.main()
