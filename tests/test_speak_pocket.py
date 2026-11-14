"""lib/speak_pocket.py: the install of the engine (what is fetched, checked and written) and the server that speaks.
Nothing here reaches the network or the real engine: the downloads are a function of the test, the model is a
handful of bytes and the program is a small script that answers as the real one does."""
import hashlib
import io
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import isolation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lib'))
import speak_pocket  # noqa: E402

CONFIG = """weights_path: hf://kyutai/pocket-tts/languages/pequeno/model.safetensors@2dd944b
weights_path_without_voice_cloning: hf://kyutai/pocket-tts-without-voice-cloning/languages/pequeno/model.safetensors@abc123

flow_lm:
  dtype: float32
  lookup_table:
    dim: 1024
    tokenizer: tokenizers
    tokenizer_path: hf://kyutai/pocket-tts-without-voice-cloning/languages/pequeno/tokenizer.json@%s
  #weights_path: partial.safetensors

mimi:
  sample_rate: 24000
""" % speak_pocket.TOKENIZER_REVISION

# In the place of the engine's program: `--version` says it runs, and `serve --host H --port P --config C
# --default-voice V` answers /health and /tts as the real one does: a WAV whose data size is a placeholder; 400 for
# an empty text; for a text it empties itself (only quotes and brackets), the header and a stream cut short. Of the
# test alone: "corta" is cut in the middle of the audio, "demora" answers late the first time, "trava" always.
PROGRAM = '''#!%s -I
import struct, sys, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
if sys.argv[1:] == ['--version']:
    print('pocket-tts 9')
    sys.exit(0)
args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
open(args['--config'] + '.started', 'w').write(' '.join(sys.argv[1:]))
slow = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == '/health' else 404)
        self.end_headers()
        self.wfile.write(b'{"status":"healthy"}')

    def do_POST(self):
        text = urllib.parse.parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
        text = text.get('text', [''])[0]
        if not text.strip():
            self.send_response(400)
            self.end_headers()
            return
        if text == 'trava' or (text == 'demora' and not slow):
            slow.append(text)
            time.sleep(3)
        header = (b'RIFF' + struct.pack('<I', 2000000036) + b'WAVEfmt '
                  + struct.pack('<IHHIIHH', 16, 1, 1, 24000, 48000, 2, 16) + b'data' + struct.pack('<I', 2000000000))
        pcm = struct.pack('<%%dh' %% len(text), *[ord(c) %% 1000 for c in text])
        self.send_response(200)
        if text == 'corta' or not text.strip('"()[] '):
            self.send_header('Content-Length', '100000')  # more than what is sent: the stream ends before its end
            pcm = pcm if text == 'corta' else b''
        self.end_headers()
        self.wfile.write(header + pcm)


if sys.argv[1] != 'serve' or args.get('--host') != '127.0.0.1':
    sys.exit(3)
ThreadingHTTPServer(('127.0.0.1', int(args['--port'])), Handler).serve_forever()
''' % sys.executable


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(members):
    """A .tar.gz with the (name, bytes) given."""
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


class Base(unittest.TestCase):
    """A tiny engine to install: a program, a model called `pequeno` and two voices, in the place of the real ones."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        isolation.scrub_environ(self, self.tmp.name)
        self.folder = os.path.join(self.tmp.name, 'engine')
        self.release = archive([('pocket-tts-9/README.md', b'leia'), ('pocket-tts-9/pocket-tts', PROGRAM.encode())])
        self.files = {'model.safetensors': b'modelo' * 100, 'tokenizer.json': b'{"tokens": []}',
                      'embeddings/ana.safetensors': b'voz da ana', 'embeddings/rui.safetensors': b'voz do rui'}
        model = {'revision': 'abc123', 'model.safetensors': (600, digest(self.files['model.safetensors'])),
                 'tokenizer.json': (14, digest(self.files['tokenizer.json'])),
                 'original.yaml': (len(CONFIG.encode()), digest(CONFIG.encode())),
                 'voices': {'ana': (10, digest(b'voz da ana')), 'rui': (10, digest(b'voz do rui'))}}
        for patch in (mock.patch.dict(speak_pocket.MODELS, {'pequeno': model}),
                      mock.patch.dict(speak_pocket.PROGRAMS,
                                      {('linux', 'x86_64'): ('pocket-tts-9.tar.gz', digest(self.release))}),
                      mock.patch.object(speak_pocket.platform, 'machine', return_value='x86_64')):
            patch.start()
            self.addCleanup(patch.stop)
        self.fetched = []
        self.config = CONFIG

    def fetch(self, url, dest, hook=None):
        """urlretrieve's shape: what each address gives, from this test."""
        self.fetched.append(url)
        if url.startswith(speak_pocket.PROGRAM_URL):
            data = self.release
        elif url == speak_pocket.CONFIG_URL % 'pequeno':
            data = self.config.encode()
        else:
            data = self.files[url.split('/languages/pequeno/')[1]]
        if hook:
            hook(0, 8192, len(data))
            hook(1, 8192, len(data))
        with open(dest, 'wb') as fh:
            fh.write(data)

    def install(self, fetch=None, voices=('ana', 'rui'), report=None):
        return speak_pocket.install(self.folder, 'linux', 'pequeno', voices, fetch or self.fetch,
                                    *([report] if report else []))

    def left(self):
        """Every file below the engine folder, relative to it."""
        found = []
        for base, _, names in os.walk(self.folder):
            found += [os.path.relpath(os.path.join(base, name), self.folder) for name in names]
        return sorted(found)


class Program(unittest.TestCase):
    def test_each_system_and_machine_has_its_file_and_the_others_none(self):
        for system, machine, part in (('linux', 'x86_64', 'x86_64-unknown-linux-gnu'), ('linux', 'AMD64', 'x86_64-unknown-linux'),
                                      ('linux', 'aarch64', 'aarch64-unknown-linux-gnu'), ('linux', 'arm64', 'aarch64-unknown-linux'),
                                      ('mac', 'arm64', 'aarch64-apple-darwin'), ('mac', 'x86_64', 'x86_64-apple-darwin')):
            name, sha = speak_pocket.program_file(system, machine)
            self.assertIn(part, name, (system, machine))
            self.assertRegex(sha, r'^[0-9a-f]{64}$')
        for system, machine in (('linux', 'riscv64'), ('linux', 'armv7l'), ('windows', 'x86_64')):
            self.assertIsNone(speak_pocket.program_file(system, machine))

    def test_every_file_is_pinned_to_a_version_and_checked(self):
        for name, model in speak_pocket.MODELS.items():
            self.assertRegex(model['model.safetensors'][1], r'^[0-9a-f]{64}$', name)
            self.assertRegex(model['revision'], r'^[0-9a-f]{40}$', name)
            for small in ('tokenizer.json', 'original.yaml'):
                self.assertGreater(model[small][0], 0, (name, small))
                self.assertRegex(model[small][1], r'^[0-9a-f]{64}$', (name, small))
            for voice, (size, sha) in model['voices'].items():
                self.assertGreater(size, 0, (name, voice))
                self.assertRegex(sha, r'^[0-9a-f]{64}$', (name, voice))
        for url in (speak_pocket.PROGRAM_URL, speak_pocket.CONFIG_URL, speak_pocket.FILES_URL):
            self.assertTrue(url.startswith('https://'), url)
            self.assertNotIn('/main/', url)  # never the moving tip of a branch
        self.assertRegex(speak_pocket.TOKENIZER_REVISION + speak_pocket.VOICES_REVISION, r'^[0-9a-f]{80}$')
        self.assertIn('without-voice-cloning', speak_pocket.FILES_URL)  # the model that cannot copy a voice


class Config(unittest.TestCase):
    def test_the_places_of_the_files_become_local_paths(self):
        text = speak_pocket.local_config(CONFIG, '/dados/engine')
        self.assertIn('\nweights_path_without_voice_cloning: /dados/engine/model.safetensors\n', text)
        self.assertTrue(text.startswith('weights_path: /dados/engine/model.safetensors\n'))
        self.assertIn('\n    tokenizer_path: /dados/engine/tokenizer.json\n', text)
        self.assertNotIn('hf://', text)
        self.assertIn('  #weights_path: partial.safetensors\n', text)  # a comment stays as it was
        self.assertIn('mimi:\n  sample_rate: 24000\n', text)  # and so does everything else
        self.assertEqual(len(text.splitlines()), len(CONFIG.splitlines()) + 1)  # one line more: the next test

    def test_the_end_of_a_sentence_is_asked_with_more_certainty(self):
        # with the program's own -4.0 the last syllable of a sentence was swallowed now and then ("valida...")
        text = speak_pocket.local_config(CONFIG, '/dados/engine')
        self.assertTrue(text.endswith('\ndefault_eos_threshold: -1.0\n'))
        self.assertEqual(len(text.splitlines()), len(CONFIG.splitlines()) + 1)
        again = speak_pocket.local_config(CONFIG.rstrip('\n') + '\ndefault_eos_threshold: -4.0\n', '/dados/engine')
        self.assertEqual(again.count('default_eos_threshold'), 1)  # the project's own, if it ever comes, is replaced
        self.assertTrue(again.endswith('\ndefault_eos_threshold: -1.0\n'))

    def test_a_configuration_in_a_shape_the_plugin_does_not_know_is_refused(self):
        for broken in (CONFIG.replace('weights_path', 'pesos'),
                       CONFIG.replace('tokenizer_path', 'tokenizador'),
                       CONFIG + 'outro: hf://kyutai/outro/arquivo.bin\n',
                       CONFIG + 'outro: https://exemplo.com/arquivo.bin\n',
                       CONFIG + 'outro: http://exemplo.com/arquivo.bin\n', ''):
            with self.assertRaises(ValueError):
                speak_pocket.local_config(broken, '/dados/engine')


class Samples(unittest.TestCase):
    def wav(self, pcm, rate=24000, channels=1, bits=16, kind=1):
        import struct
        return (b'RIFF' + struct.pack('<I', 2000000036) + b'WAVEfmt '
                + struct.pack('<IHHIIHH', 16, kind, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits)
                + b'data' + struct.pack('<I', 2000000000) + pcm)

    def test_the_samples_are_what_comes_after_the_data_header(self):
        self.assertEqual(speak_pocket.samples(self.wav(b'\x01\x00\x02\x00')), b'\x01\x00\x02\x00')
        self.assertEqual(speak_pocket.samples(self.wav(b'\x01\x00\x02')), b'\x01\x00')  # half a sample is left out
        self.assertEqual(speak_pocket.samples(self.wav(b'')), b'')

    def test_what_is_not_the_audio_expected_is_refused(self):
        for answer in (b'', b'{"detail": "erro"}', b'RIFF\x00\x00\x00\x00WAVE', self.wav(b'\x00\x00', rate=44100),
                       self.wav(b'\x00\x00', channels=2), self.wav(b'\x00\x00', bits=8), self.wav(b'\x00\x00', kind=3)):
            with self.assertRaises(ValueError):
                speak_pocket.samples(answer)


class Install(Base):
    def test_everything_is_fetched_checked_and_left_ready(self):
        self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))
        told = []
        self.install(report=lambda *a: told.append(a))
        self.assertEqual(self.left(), ['config.yaml', 'model.safetensors', 'original.yaml', 'pocket-tts', 'ready',
                                       'tokenizer.json', 'voices/ana.safetensors', 'voices/rui.safetensors'])
        self.assertTrue(speak_pocket.ready(self.folder, 'pequeno', ('rui', 'ana')))
        self.assertEqual(self.fetched, [
            speak_pocket.PROGRAM_URL + 'pocket-tts-9.tar.gz',
            speak_pocket.CONFIG_URL % 'pequeno',
            speak_pocket.FILES_URL % (speak_pocket.TOKENIZER_REVISION, 'pequeno', 'tokenizer.json'),
            speak_pocket.FILES_URL % ('abc123', 'pequeno', 'model.safetensors'),
            speak_pocket.FILES_URL % (speak_pocket.VOICES_REVISION, 'pequeno', 'embeddings/ana.safetensors'),
            speak_pocket.FILES_URL % (speak_pocket.VOICES_REVISION, 'pequeno', 'embeddings/rui.safetensors')])
        program = speak_pocket.program(self.folder)
        with open(program) as fh:
            self.assertEqual(fh.read(), PROGRAM)  # the program alone came out of the archive, which is gone
        self.assertTrue(os.stat(program).st_mode & stat.S_IXUSR)
        with open(speak_pocket.config(self.folder)) as fh:
            self.assertIn('weights_path: %s\n' % os.path.join(self.folder, 'model.safetensors'), fh.read())
        # each file is told with its place in the list, its size as soon as it is known and the bytes so far
        self.assertEqual(told[0], ('pocket-tts-9.tar.gz', 0, 0, 1, 6))
        self.assertIn(('model.safetensors', 8192, 600, 4, 6), told)
        self.assertEqual(told[-1][0], 'rui.safetensors')

    def test_ready_is_of_this_program_this_model_and_these_voices(self):
        self.install()
        self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana',)))
        self.assertFalse(speak_pocket.ready(self.folder, 'portuguese', ('ana', 'rui')))
        with mock.patch.object(speak_pocket, 'VERSION', '9.9.9'):
            self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))
        os.remove(speak_pocket.program(self.folder))
        self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))

    def test_a_second_install_fetches_only_what_is_missing_or_wrong(self):
        self.install()
        with open(os.path.join(self.folder, 'voices', 'ana.safetensors'), 'wb') as fh:
            fh.write(b'voz da eva')  # the size is right, the content is not
        os.remove(os.path.join(self.folder, 'tokenizer.json'))
        self.fetched.clear()
        self.install()
        self.assertEqual([url.rsplit('/', 1)[1] for url in self.fetched],
                         ['pocket-tts-9.tar.gz', 'tokenizer.json', 'ana.safetensors'])
        with open(os.path.join(self.folder, 'voices', 'ana.safetensors'), 'rb') as fh:
            self.assertEqual(fh.read(), b'voz da ana')
        self.assertTrue(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))

    def test_a_file_that_comes_different_from_expected_stops_the_install(self):
        for name, wrong in (('model.safetensors', b'modelo' * 99 + b'MODELO'), ('model.safetensors', b'curto'),
                            ('tokenizer.json', b'{}'), ('tokenizer.json', b'{"tokens": [1}'),
                            ('embeddings/rui.safetensors', b'voz do zeh'), ('release', b'outro'),
                            ('original.yaml', CONFIG.replace('24000', '48000').encode())):
            with self.subTest(name), tempfile.TemporaryDirectory() as other:
                self.folder = os.path.join(other, 'engine')
                right = (self.release if name == 'release' else self.config if name == 'original.yaml'
                         else self.files[name])
                try:
                    if name == 'release':
                        self.release = wrong
                    elif name == 'original.yaml':
                        self.config = wrong.decode()
                    else:
                        self.files[name] = wrong
                    with self.assertRaises(ValueError) as failure:
                        self.install()
                finally:
                    if name == 'release':
                        self.release = right
                    elif name == 'original.yaml':
                        self.config = right
                    else:
                        self.files[name] = right
                self.assertIn('chegou diferente do esperado', str(failure.exception))
                self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))
                self.assertEqual([n for n in self.left() if '.part' in n], [])
                self.assertNotIn(os.path.basename(name), [os.path.basename(n) for n in self.left()])  # the wrong file is not kept
                self.assertNotIn('pocket-tts', self.left())  # and no program was taken out of an archive not checked

    def test_every_failure_of_a_download_removes_its_part_file(self):
        """Whatever stops a download (the network, the progress hook, an interrupt, a failure of a later file) leaves
        no `<file>.part-<pid>`; a file already complete stays, and the install is not one to speak with."""
        def drops(url, dest, hook=None):
            open(dest, 'w').close()
            raise OSError('rede caiu')

        def hook_fails(url, dest, hook=None):
            open(dest, 'w').close()
            hook(1, 1000, 5000)

        def interrupted(url, dest, hook=None):
            open(dest, 'w').close()
            raise KeyboardInterrupt

        def later_fails(url, dest, hook=None):
            if url.endswith('rui.safetensors'):
                open(dest, 'w').close()
                raise OSError('rede caiu')
            self.fetch(url, dest, hook)

        def report_fails(name, done, total, step, steps):
            if done:
                raise OSError('disco cheio')

        for name, fetch, error, report in (('rede', drops, OSError, None), ('progresso', hook_fails, OSError, report_fails),
                                           ('interrupção', interrupted, KeyboardInterrupt, None),
                                           ('arquivo seguinte', later_fails, OSError, None)):
            with self.subTest(name), tempfile.TemporaryDirectory() as other:
                self.folder = os.path.join(other, 'engine')
                with self.assertRaises(error):
                    self.install(fetch, report=report)
                self.assertEqual([n for n in self.left() if '.part' in n], [])
                self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))
                if name == 'arquivo seguinte':
                    self.assertIn('model.safetensors', self.left())  # complete, it stays for the next try

    def test_a_failed_reinstall_takes_the_ready_mark_away(self):
        self.install()
        self.files['tokenizer.json'] = b'{"tokens": [1]}'  # what comes now is no longer what is expected
        os.remove(os.path.join(self.folder, 'tokenizer.json'))
        with self.assertRaises(ValueError):
            self.install()
        self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))

    def test_a_configuration_that_names_other_revisions_stops_the_install_before_the_big_files(self):
        """The weights checked here must be the ones the program's own configuration names: with another revision
        there (the project moved on, or this module was written wrong), nothing else is fetched."""
        for config in (CONFIG.replace('model.safetensors@abc123', 'model.safetensors@def456'),
                       CONFIG.replace('tokenizer.json@' + speak_pocket.TOKENIZER_REVISION, 'tokenizer.json@def456'),
                       CONFIG.replace('languages/pequeno/model', 'languages/outro/model')):
            self.config, self.fetched = config, []
            pinned = dict(speak_pocket.MODELS['pequeno'], **{'original.yaml': (len(config.encode()), digest(config.encode()))})
            with mock.patch.dict(speak_pocket.MODELS, {'pequeno': pinned}), self.assertRaises(ValueError) as failure:
                self.install()
            self.assertIn('aponta outra versão dos arquivos', str(failure.exception))
            self.assertEqual([url.rsplit('/', 1)[1] for url in self.fetched], ['pocket-tts-9.tar.gz', 'pequeno.yaml'])
            self.assertNotIn('original.yaml', self.left())
            self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))

    def test_a_machine_without_a_program_is_refused_before_any_download(self):
        with mock.patch.object(speak_pocket.platform, 'machine', return_value='riscv64'):
            with self.assertRaises(ValueError) as failure:
                self.install()
        self.assertIn('não tem programa para esta máquina', str(failure.exception))
        self.assertEqual(self.fetched, [])

    def test_the_archive_gives_only_the_program_and_nothing_outside_the_folder(self):
        outside = os.path.join(self.tmp.name, 'fora')
        self.release = archive([('../fora', b'escapou'), ('pocket-tts-9/pocket-tts', PROGRAM.encode()),
                                ('pocket-tts-9/outro', b'x')])
        with mock.patch.dict(speak_pocket.PROGRAMS, {('linux', 'x86_64'): ('pocket-tts-9.tar.gz', digest(self.release))}):
            self.install()
        self.assertFalse(os.path.exists(outside))
        self.assertNotIn('outro', self.left())
        self.release = archive([('pocket-tts-9/README.md', b'sem programa')])
        with mock.patch.dict(speak_pocket.PROGRAMS, {('linux', 'x86_64'): ('pocket-tts-9.tar.gz', digest(self.release))}):
            with self.assertRaises(ValueError) as failure:
                self.install()
        self.assertIn('veio sem o programa', str(failure.exception))

    def test_a_program_that_does_not_run_on_this_machine_fails_the_install(self):
        """A system older than the program was made for, or a folder where nothing may run: found out at the install,
        which says so, and not at every speech."""
        for name, program in (('sai com erro', b'#!/bin/sh\necho "GLIBC_2.34 not found" >&2\nexit 1\n'),
                              ('não é um programa', b'\x00lixo'), ('não responde', b'#!/bin/sh\nexec sleep 30\n')):
            with self.subTest(name), tempfile.TemporaryDirectory() as other:
                self.folder = os.path.join(other, 'engine')
                self.release = archive([('pocket-tts-9/pocket-tts', program)])
                with mock.patch.dict(speak_pocket.PROGRAMS, {('linux', 'x86_64'): ('pocket-tts-9.tar.gz', digest(self.release))}), \
                        mock.patch.object(speak_pocket, 'RUN_WAIT', 0.5), self.assertRaises(ValueError) as failure:
                    self.install()
                self.assertIn('o programa do motor não roda nesta máquina', str(failure.exception))
                self.assertFalse(speak_pocket.ready(self.folder, 'pequeno', ('ana', 'rui')))
                if name == 'sai com erro':
                    self.assertIn('GLIBC_2.34 not found', str(failure.exception))

    def test_the_file_of_a_voice_that_left_the_plugin_is_removed(self):
        self.install()
        self.install(voices=('rui',))  # an update in which `ana` is no longer one of the voices
        self.assertEqual([n for n in self.left() if n.startswith('voices/')], ['voices/rui.safetensors'])
        self.assertTrue(speak_pocket.ready(self.folder, 'pequeno', ('rui',)))

    def test_what_a_dead_install_left_half_downloaded_is_swept(self):
        os.makedirs(os.path.join(self.folder, 'voices'))
        for rel in ('model.safetensors.part-99999', 'voices/ana.safetensors.part-99999', 'pocket-tts.part-4'):
            with open(os.path.join(self.folder, rel), 'w') as fh:
                fh.write('metade')
        self.install()
        self.assertEqual([n for n in self.left() if '.part' in n], [])


class Server(Base):
    """The server of one speech, against a program of the test that answers as the real one."""

    def setUp(self):
        super().setUp()
        self.install()

    def start(self, voice='ana', **kw):
        server = speak_pocket.Server(self.folder, voice, **kw)
        self.addCleanup(server.close)
        return server

    def test_it_is_started_on_this_machine_alone_with_the_local_configuration_and_the_voice(self):
        server = self.start('rui')
        with open(speak_pocket.config(self.folder) + '.started') as fh:
            self.assertEqual(fh.read(), 'serve --host 127.0.0.1 --port %d --config %s --default-voice %s' % (
                server.port, speak_pocket.config(self.folder), os.path.join(self.folder, 'voices', 'rui.safetensors')))

    def test_a_piece_comes_back_as_its_samples_and_nothing_to_say_as_silence(self):
        import struct
        server = self.start()
        self.assertEqual(server.speak('Olá, é só um teste: 100%!'),
                         struct.pack('<25h', *[ord(c) % 1000 for c in 'Olá, é só um teste: 100%!']))
        self.assertEqual(server.speak('...'), struct.pack('<3h', 46, 46, 46))
        self.assertEqual(server.speak('   '), b'')  # the engine answers 400: silence, not a failure

    def test_a_text_the_engine_empties_is_silence_and_a_stream_cut_in_the_audio_is_a_failure(self):
        """The engine drops quotes and brackets by itself: for a piece made only of them it sends the header of the
        audio and ends the stream, which is no reason to lose the pieces after it."""
        import http.client
        server = self.start()
        for text in ('()', '"', '[ ]'):
            self.assertEqual(server.speak(text), b'', text)
        with self.assertRaises(http.client.IncompleteRead):
            server.speak('corta')
        self.assertEqual(len(server.speak('segue')), 10)  # and the server goes on

    def test_a_piece_that_takes_too_long_is_asked_once_more(self):
        """A speech frozen by a pause for longer than the wait finds its answer timed out when it continues."""
        with mock.patch.object(speak_pocket, 'PIECE_WAIT', 0.5):
            server = self.start()
            self.assertEqual(len(server.speak('demora')), 12)
            with self.assertRaises(OSError):
                server.speak('trava')

    def test_a_data_folder_that_moved_gets_its_configuration_written_again(self):
        moved = os.path.join(self.tmp.name, 'mudou')
        os.rename(self.folder, moved)
        self.folder = moved
        self.assertTrue(speak_pocket.ready(moved, 'pequeno', ('ana', 'rui')))
        server = self.start()
        with open(speak_pocket.config(moved)) as fh:
            text = fh.read()
        self.assertIn('weights_path: %s\n' % os.path.join(moved, 'model.safetensors'), text)
        self.assertNotIn(os.path.join(self.tmp.name, 'engine'), text)
        self.assertEqual(len(server.speak('oi')), 4)

    def test_kill_ends_the_program_at_once_and_close_still_works(self):
        server = self.start()
        proc = server.proc
        server.kill()
        self.assertEqual(proc.wait(timeout=5), -9)
        server.kill()
        server.close()

    def test_a_proxy_in_the_environment_is_never_used(self):
        with mock.patch.dict(os.environ, {'http_proxy': 'http://127.0.0.1:9', 'HTTP_PROXY': 'http://127.0.0.1:9',
                                          'all_proxy': 'http://127.0.0.1:9'}):
            server = self.start()
            self.assertEqual(len(server.speak('oi')), 4)

    def test_close_ends_the_program_and_may_be_called_again(self):
        server = self.start()
        proc = server.proc
        server.close()
        self.assertIsNotNone(proc.poll())
        server.close()

    def test_a_program_that_ends_at_once_or_never_answers_is_a_failure_and_is_not_left_running(self):
        with open(speak_pocket.program(self.folder), 'w') as fh:
            fh.write('#!/bin/sh\nexit 7\n')
        with self.assertRaises(RuntimeError) as failure:
            self.start()
        self.assertIn('encerrou ao iniciar (código 7)', str(failure.exception))
        with open(speak_pocket.program(self.folder), 'w') as fh:
            fh.write('#!/bin/sh\necho $$ > "%s"\nexec sleep 30\n' % os.path.join(self.tmp.name, 'pid'))
        with self.assertRaises(RuntimeError) as failure:
            self.start(start_wait=0.5)
        self.assertIn('não respondeu', str(failure.exception))
        with open(os.path.join(self.tmp.name, 'pid')) as fh:
            pid = int(fh.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_what_the_program_writes_goes_to_the_log_given(self):
        with open(speak_pocket.program(self.folder), 'w') as fh:
            fh.write('#!/bin/sh\necho "carregando o modelo"\necho "faltou memória" >&2\nexit 1\n')
        path = os.path.join(self.tmp.name, 'engine.log')
        with open(path, 'w') as log, self.assertRaises(RuntimeError):
            self.start(log=log)
        with open(path) as fh:
            self.assertEqual(fh.read(), 'carregando o modelo\nfaltou memória\n')


if __name__ == '__main__':
    unittest.main()
