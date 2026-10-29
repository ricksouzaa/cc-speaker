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


class RealRoots(unittest.TestCase):
    def test_a_bateria_nao_tocou_na_raiz_real(self):
        isolation.assert_untouched(self)

    def test_o_ambiente_da_bateria_nao_leva_pastas_reais(self):
        self.assertEqual(isolation.START_ENV_LEAK, [], 'a bateria foi iniciada com variáveis CLAUDE_*/XDG_* de pastas')


if __name__ == '__main__':
    unittest.main()
