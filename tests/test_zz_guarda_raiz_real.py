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
                     os.path.join(state, 'soft-4321'),  # the marker of a speech that pauses itself (speak.soft_marker)
                     old, os.path.join(old, 'queue'), os.path.join(old, 'speech.pid')):
            self.assertTrue(isolation.is_speech_noise(path), path)
        for path in (os.path.join(state, 'install.lock'), os.path.join(state, 'all'),
                     os.path.join(state, 'soft-x'), os.path.join(state, 'soft-12.tmp'), os.path.join(state, 'soft-12', 'x'),
                     os.path.join(self.HOME, '.claude', 'plugins', 'data', 'speak-cc-speaker', 'config', 'soft-12'),
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
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set())
        isolation.assert_untouched(Case(), speech_after={5}, speech_before=set(), speech_seen=set())
        isolation.assert_untouched(Case(), speech_after=set(), speech_before={5}, speech_seen=set())
        open(os.path.join(state, 'install.lock'), 'w').close()
        with self.assertRaises(AssertionError):
            isolation.assert_untouched(Case(), speech_after={5}, speech_before=set(), speech_seen=set())


class SeenDuringTheBattery(unittest.TestCase):
    """A real speech that starts and ends in the middle of the battery is seen by the watch, not by the two ends."""

    def case(self):
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        self.state = os.path.join(root, 'state')
        os.makedirs(self.state)
        saved = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(saved[0]),
                                 setattr(isolation, 'ROOTS', saved[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root]
        isolation.BEFORE.update(isolation.snapshot([root]))
        return Case()

    def test_o_olhar_junta_as_falas_que_passaram_entre_as_pontas(self):
        now = [set()]
        watch = isolation.SpeechWatch(finder=lambda: now[0])
        self.assertEqual(watch.look(), set())
        now[0] = {41}
        watch.look()
        now[0] = set()  # the speech ended: the end of the battery would see nothing
        self.assertEqual(watch.look(), {41})
        now[0] = {42}
        self.assertEqual(watch.look(), {41, 42})

    def test_a_linha_de_fundo_olha_sozinha_e_para(self):
        import time
        now = [set()]
        watch = isolation.SpeechWatch(finder=lambda: now[0], every=0.01).start()
        self.addCleanup(watch.stop)
        now[0] = {7}
        end = time.time() + 3
        while 7 not in watch.seen and time.time() < end:
            time.sleep(0.01)
        now[0] = set()
        self.assertIn(7, watch.seen)
        watch.stop()
        watch.thread.join(2)
        self.assertFalse(watch.thread.is_alive())

    def test_fala_curta_do_meio_perdoa_o_ruido_de_fila_e_so_ele(self):
        case = self.case()
        open(os.path.join(self.state, 'queue.lock'), 'w').close()
        with self.assertRaises(AssertionError):  # nobody was seen: the same change is reported
            isolation.assert_untouched(case, speech_after=set(), speech_before=set(), speech_seen=set())
        isolation.assert_untouched(case, speech_after=set(), speech_before=set(), speech_seen={99})
        open(os.path.join(self.state, 'install.lock'), 'w').close()  # not a speech name: reported even then
        with self.assertRaises(AssertionError):
            isolation.assert_untouched(case, speech_after=set(), speech_before=set(), speech_seen={99})

    def test_com_fala_vista_o_que_nao_e_nome_de_fala_continua_acusado(self):
        case = self.case()
        os.makedirs(os.path.join(os.path.dirname(self.state), 'config'))
        open(os.path.join(os.path.dirname(self.state), 'config', 'mode'), 'w').close()
        with self.assertRaises(AssertionError):
            isolation.assert_untouched(case, speech_after=set(), speech_before=set(), speech_seen={99})


class Workers(unittest.TestCase):
    def test_thread_viva_de_trabalho_e_apanhada_e_depois_que_acaba_nao(self):
        import threading

        def work():
            release.wait(5)
        work.__qualname__ = 'synthesize_ahead.<locals>.work'
        release = threading.Event()
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        self.addCleanup(release.set)
        with self.assertRaises(AssertionError):
            isolation.assert_no_workers(unittest.TestCase(), wait=0.05)
        release.set()
        thread.join(2)
        isolation.assert_no_workers(unittest.TestCase(), wait=0.05)


class LiveLast(unittest.TestCase):
    STATE = os.path.join(os.path.expanduser('~'), '.claude', 'plugins', 'data', 'speak-cc-speaker', 'state')
    PROCS = [(100, 1, ['python3', '-m', 'unittest']), (101, 100, ['claude']), (300, 1, ['claude', '--resume']),
             (301, 1, ['node', '/x/bin/claude']), (302, 1, ['vim', 'notas.txt']), (303, 300, ['sleep', '1'])]

    def test_claude_real_e_o_que_nao_descende_da_bateria(self):
        self.assertEqual(isolation.real_claude_pids(self.PROCS, me=100), {300, 301})

    def test_last_de_sessao_real_viva_e_ruido_so_ela(self):
        last = os.path.join(self.STATE, 'last')
        for path in (last, os.path.join(last, '300-5555'), os.path.join(last, '301-9')):
            self.assertTrue(isolation.is_live_last(path, {300, 301}), path)
        for path in (os.path.join(last, '302-5'), os.path.join(last, '300-5555.tmp'), os.path.join(last, 'x'),
                     os.path.join(last, '300-5555', 'mais'), os.path.join(self.STATE, 'sessions', '300-5555'),
                     os.path.join(self.STATE, 'all')):
            self.assertFalse(isolation.is_live_last(path, {300, 301}), path)

    def test_guarda_ignora_last_de_claude_vivo_e_acusa_o_resto(self):
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        state = os.path.join(root, 'state')
        os.makedirs(os.path.join(state, 'last'))
        saved = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(saved[0]),
                                 setattr(isolation, 'ROOTS', saved[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root]
        isolation.BEFORE.update(isolation.snapshot([root]))
        with open(os.path.join(state, 'last', '300-5555'), 'w') as fh:
            fh.write('x')
        isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(), claude_pids={300})
        with self.assertRaises(AssertionError):  # the same change, with no such live session
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(), claude_pids={999})
        open(os.path.join(state, 'install.lock'), 'w').close()
        with self.assertRaises(AssertionError):  # anything else is still reported
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(), claude_pids={300})

    def test_a_gravacao_real_do_last_passa_pela_pasta_state_e_so_ela_e_perdoada(self):
        # The real hook saves the last reply through a temporary file in `state`, then moves it into `state/last`
        # (speak.write_atomic): the `state` folder itself changes too. It is forgiven only with that saved reply.
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        state = os.path.join(root, 'state')
        os.makedirs(os.path.join(state, 'last'))
        saved = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(saved[0]),
                                 setattr(isolation, 'ROOTS', saved[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root]
        isolation.BEFORE.update(isolation.snapshot([root]))
        later = os.stat(state).st_mtime + 5  # a change the snapshot surely sees, whatever the clock's grain

        def check(pids, own=frozenset(), seen=frozenset()):
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(seen),
                                       claude_pids=pids, own_pids=own)

        os.utime(state, (later, later))
        with self.assertRaises(AssertionError):  # `state` alone changed: no saved reply explains it
            check({300})
        with open(os.path.join(state, '.tmp-300-ab12'), 'w') as fh:
            fh.write('x')
        os.replace(os.path.join(state, '.tmp-300-ab12'), os.path.join(state, 'last', '300-5555'))
        os.utime(state, (later, later))
        check({300})
        with self.assertRaises(AssertionError):  # the same change, with no such live session
            check({999})
        # The session that launched the battery: a child `speak say -` with no forced session finds that key by
        # itself, so its last reply is what a leak of the battery would write (and "Ouvir de novo" there would then
        # repeat the text of a test). It is reported, whoever else is alive, and even while a real speech plays.
        with self.assertRaises(AssertionError):
            check({300}, own={300})
        with self.assertRaises(AssertionError):
            check({300, 301}, own={300})
        with self.assertRaises(AssertionError) as caught:
            check({300, 301}, own={300}, seen={7})
        self.assertIn(os.path.join(state, 'last', '300-5555'), str(caught.exception))
        check({300, 301}, own={301})  # the file of another live session is still noise
        open(os.path.join(state, 'install.lock'), 'w').close()
        with self.assertRaises(AssertionError):  # anything else is still reported
            check({300})

    def test_escolhas_de_sessao_real_viva_sao_ruido_so_elas(self):
        sessions = os.path.join(self.STATE, 'sessions')
        for path in (sessions, os.path.join(sessions, '300-5555'), os.path.join(sessions, '301-9')):
            self.assertTrue(isolation.is_live_session(path, {300, 301}), path)
        for path in (os.path.join(sessions, '302-5'), os.path.join(sessions, '300-5555.tmp'), os.path.join(sessions, 'x'),
                     os.path.join(sessions, '300-5555', 'mais'), os.path.join(self.STATE, 'last', '300-5555'),
                     os.path.join(self.STATE, 'all')):
            self.assertFalse(isolation.is_live_session(path, {300, 301}), path)
        self.assertFalse(isolation.is_live_session(sessions, set()))  # no live session: the folder is reported too

    def test_a_gravacao_real_das_escolhas_da_sessao_passa_pela_pasta_state_e_so_ela_e_perdoada(self):
        # The hooks of a live session write its own file in `state/sessions` with no speech at all: `speak rule` at the
        # start of a conversation and after a compaction, `speak told` at a new message. The file goes through a
        # temporary one in `state` (speak.write_atomic), so `state`, `state/sessions` and the file change together.
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        state = os.path.join(root, 'state')
        sessions = os.path.join(state, 'sessions')
        os.makedirs(sessions)
        for key in ('300-5555', '302-7'):  # both were there before the battery
            with open(os.path.join(sessions, key), 'w') as fh:
                fh.write('{}')
        saved = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(saved[0]),
                                 setattr(isolation, 'ROOTS', saved[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root]
        isolation.BEFORE.update(isolation.snapshot([root]))
        later = os.stat(state).st_mtime + 5  # a change the snapshot surely sees, whatever the clock's grain

        def check(pids, own=frozenset()):
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(),
                                       claude_pids=pids, own_pids=own)

        def write(key):
            with open(os.path.join(state, '.tmp-300-ab12'), 'w') as fh:
                fh.write('{"told": "summary"}')
            os.replace(os.path.join(state, '.tmp-300-ab12'), os.path.join(sessions, key))
            for folder in (state, sessions):
                os.utime(folder, (later, later))

        for folder in (state, sessions):
            os.utime(folder, (later, later))
        with self.assertRaises(AssertionError):  # the folders alone changed: no session file explains `state`
            check({300})
        write('300-5555')
        check({300})
        with self.assertRaises(AssertionError):  # the same change, with no such live session
            check({999})
        # The session that launched the battery: a child `speak` with no forced session finds that key by itself, so
        # its file is what a leak of the battery would write. It is reported, whoever else is alive.
        with self.assertRaises(AssertionError):
            check({300}, own={300})
        with self.assertRaises(AssertionError):
            check({300, 301}, own={300})
        write('302-7')
        with self.assertRaises(AssertionError):  # the file of a session that is not a live Claude Code is reported
            check({300})
        check({300, 302})
        open(os.path.join(state, 'all'), 'w').close()
        with self.assertRaises(AssertionError):  # anything else is still reported
            check({300, 302})

    def test_o_claude_que_lancou_a_bateria_e_o_que_esta_acima_dela(self):
        procs = self.PROCS + [(400, 300, ['zsh', '-c', 'python3 -m unittest']), (401, 400, ['python3', '-m', 'unittest']),
                              (500, 301, ['python3', '-m', 'unittest'])]
        self.assertEqual(isolation.own_claude_pids(procs, me=401), {300})
        self.assertEqual(isolation.own_claude_pids(procs, me=500), {301})  # a node install: `claude` is the script
        self.assertEqual(isolation.own_claude_pids(procs, me=100), set())  # started from a plain terminal
        self.assertEqual(isolation.own_claude_pids(procs, me=101), set())  # the battery's own child is not above it

    def test_a_pasta_state_so_e_perdoada_pela_gravacao_feita_dentro_dela(self):
        # Two state folders (the data root's and the former one): a live session's file written in the first does not
        # explain a change of the second, and a file that only went away explains no change of `state` at all.
        class Case(unittest.TestCase):
            def runTest(self):
                pass
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = os.path.join(tmp.name, 'speak-cc-speaker')
        state = os.path.join(root, 'state')
        old = os.path.join(tmp.name, 'state', 'claude-speak')
        os.makedirs(os.path.join(state, 'last'))
        os.makedirs(old)
        with open(os.path.join(state, 'last', '300-5555'), 'w') as fh:
            fh.write('x')
        saved = dict(isolation.BEFORE), isolation.ROOTS
        self.addCleanup(lambda: (isolation.BEFORE.clear(), isolation.BEFORE.update(saved[0]),
                                 setattr(isolation, 'ROOTS', saved[1])))
        isolation.BEFORE.clear()
        isolation.ROOTS = [root, old]
        isolation.BEFORE.update(isolation.snapshot([root, old]))
        later = os.stat(state).st_mtime + 5

        def check():
            isolation.assert_untouched(Case(), speech_after=set(), speech_before=set(), speech_seen=set(),
                                       claude_pids={300}, own_pids=set())

        with open(os.path.join(state, 'last', '300-5555'), 'w') as fh:
            fh.write('outra resposta')
        os.utime(state, (later, later))
        check()  # the reply saved in this `state` explains its change
        os.utime(old, (later, later))
        with self.assertRaises(AssertionError):  # but not the change of the other state folder
            check()
        os.utime(old, ns=(isolation.BEFORE[old][0], isolation.BEFORE[old][0]))
        check()
        os.remove(os.path.join(state, 'last', '300-5555'))
        with self.assertRaises(AssertionError):  # the reply went away, nothing was written: `state` is reported
            check()


class RealRoots(unittest.TestCase):
    def test_a_bateria_nao_tocou_na_raiz_real(self):
        isolation.assert_untouched(self)

    def test_o_ambiente_da_bateria_nao_leva_pastas_reais(self):
        self.assertEqual(isolation.START_ENV_LEAK, [], 'a bateria foi iniciada com variáveis CLAUDE_*/XDG_* de pastas')


if __name__ == '__main__':
    unittest.main()
