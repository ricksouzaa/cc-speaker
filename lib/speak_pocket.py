"""Pocket TTS (Kyutai), the engine that makes the speech: a program of its own (one file, no Python), the model and
the voices beside it.

Everything is downloaded by the plugin itself at install time, each file at a fixed version and checked against its
SHA-256: the program from the GitHub release of kyutai-labs/pocket-tts (code under MIT), the model and the voices
from Hugging Face, kyutai/pocket-tts-without-voice-cloning (CC-BY-4.0). The model is told where its files are by a
configuration written here (`config.yaml`) with local paths, so a speech opens no connection to the network: left to
itself, the program asks Hugging Face about its files at every start, even with them all at hand.

While a speech lasts, the program runs as a server that answers on this machine alone (127.0.0.1) and gives the
audio of each piece of text: 16-bit samples, mono, 24 kHz.
"""
import glob
import hashlib
import http.client
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = '3.3.0'  # of the program; it comes in the release v4.0.1 of the project
PROGRAM_URL = 'https://github.com/kyutai-labs/pocket-tts/releases/download/v4.0.1/'
PROGRAMS = {  # (system, machine) -> (file of the release, its SHA-256)
    ('linux', 'x86_64'): ('pocket-tts-3.3.0-x86_64-unknown-linux-gnu.tar.gz',
                          '9abff0aa138a804e44052952d8c3bdaae247fb267ca8f4b83fe178897d1a0559'),
    ('linux', 'aarch64'): ('pocket-tts-3.3.0-aarch64-unknown-linux-gnu.tar.gz',
                           '2b9a727bffd86ea6d73370d675cbd91a7db118f11b7f5a60343c2d5da12b187a'),
    ('mac', 'arm64'): ('pocket-tts-3.3.0-aarch64-apple-darwin.tar.gz',
                       'ee9ca6c7c000ee72c5846e3a8ba01d08f56636d94a614d2259c3f12b8fd69afa'),
    ('mac', 'x86_64'): ('pocket-tts-3.3.0-x86_64-apple-darwin.tar.gz',
                        'f04baa94d4fc47a689cc9f11ca2b0ba869dc002f9e78e15d387c6ecaeb1d654b'),
}
CONFIG_URL = 'https://raw.githubusercontent.com/kyutai-labs/pocket-tts/v4.0.1/pocket_tts/config/%s.yaml'
FILES_URL = 'https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/resolve/%s/languages/%s/%s'
TOKENIZER_REVISION = '4e1e0a3e611c51c0b4ed8174fc10f32a54644303'  # of the tokenizer, the same for every model
VOICES_REVISION = 'a3055dcb533cf2ec90458008a01e7cef550bae2a'  # of the voices
RATE = 24000  # what the server gives: mono, 16 bits
START_WAIT = 60.0  # seconds for the server to load the model and answer
PIECE_WAIT = 300.0  # seconds for the audio of one piece
RUN_WAIT = 30.0  # seconds for the program to say its version, at the install
HEADER = 44  # bytes of the WAV header the server sends before the samples
# What each model is made of: the revision of its weights there, the one the project's own configuration names (the
# install checks that it does, see `check_config`), and file -> (size in bytes, SHA-256). The tokenizer and the
# configuration (`original.yaml`, from the project's tag) are small text files kept in git, with no SHA-256
# published: theirs are of the files as first fetched and heard.
MODELS = {
    'portuguese': {
        'revision': '1e08e6a23401048648a9fdcfde2f89348215c2a7',
        'model.safetensors': (219029196, '28e20f32515ba8bd0eaec69671f11f8921414fcdc375aa072fa09f46cc1057c5'),
        'tokenizer.json': (247014, 'b33e269f7f042a763080d71ba087d74d2f6759674b238a723c028e436b1a25ab'),
        'original.yaml': (1552, '80e1ad86c2e6e1ae0ba979cebc0c9b9964f2e976c9774ebe4df9cabf85787399'),
        'voices': {
            'lola': (5457720, '0169b537f8a562907eacba75bfa35ce645fa88f9f2e7da3b29aa35af8ac10bad'),
            'estelle': (7571256, '3272dfb763dab2f834357b583c603654ac6752a916fb47253c7a186591525e63'),
            'fantine': (6440760, '0934eabaa5fa5fe12535614c136bf4d073d4fe1085124495b4866011a02b4a11'),
            'rafael': (6244152, '5aadaa0adf8d4c095f8c90cd2ece0006bbd5c66325ed01af9f955ddc8a2b5236'),
            'charles': (6195000, '26654297467c0a3541a37c8e64be9cbad7a78d86bc8f8b51e58874e7eecfd800'),
            'george': (5900088, '8e37c8fd8839aab501bdc0c30c8e4d37996e62fb66c063d3e54c80c98b4b6ea5'),
            'michael': (7128888, '07b19d1897d626a8456a9c58e76461bb8d21289f42b594b9c05ec7b4091cb8b2'),
            'paul': (6833976, '08c2e7e31b232866c124c312af8e34daf35e867782b2cd5271fde4b4b3c79002'),
            'giovanni': (4130608, '8ef09c84eea9f9b8a6fbea92518815514a09f59cc63a8bb1273ac67ef00e3b73'),
            'javert': (6145848, '1c8cb25be8928811ab7632a0a915f88ef52d05447352ac5d9fee679b62715224'),
            'marius': (6244152, '9f6cc305d08f6652aa15ff0ac17c216bcd17a3fe50432afc0bcab6cd4573cbdd'),
        },
    },
    'portuguese_24l': {
        'revision': '4e1e0a3e611c51c0b4ed8174fc10f32a54644303',
        'model.safetensors': (672178676, 'ce7911fe914d055e55dcb8dcc973f735d9f51d09fe6fec4fe35d80ac2c9d9670'),
        'tokenizer.json': (247014, 'b33e269f7f042a763080d71ba087d74d2f6759674b238a723c028e436b1a25ab'),
        'original.yaml': (1565, 'fdaec3c1de6c64c5a57618275cc068d5fc14bd78bf7bb06af47e5cd0a74c122f'),
        'voices': {
            'lola': (21831000, '7fe59d61a5e2eaff4fd6fc6b36c6496236da6277372985b1649582ba105c7ae9'),
            'estelle': (30285152, '8e42e3657a6292e3fc5c0a318e1cf151fcf084faa2b1148cab0975494f54bf65'),
            'fantine': (25763160, '31a090e96b8001d239eda188f916a43ba9753070f8eaa65da1dcb872b71944a1'),
            'rafael': (24976728, 'a786e0035e6dd6655259164172e7feeb58a519bf072db83dd034a0d39c85433f'),
            'charles': (24780120, '9fe91a19e3695c89df60fe91d59bf6f4bcae5bb19b83871e7b5aeecb1f19054f'),
            'george': (23600472, '1edd2433779cd4ec0f125864dad8a493f24059e3098ec07290440cc9da654a0a'),
            'michael': (28515680, '1d7f19070f39e643b09c670e13a0447714b12a6307de3df2ceaed4b1bc2806fb'),
            'paul': (27336032, 'd7b917743ae8710bcbe8df8abda9b7bef9a1b86250b41866bd3b7a8653048597'),
            'giovanni': (16522552, 'fed44b26c70832e34861f6bbd76e24403a20f31f2d40adc00074b1c7ac24fd8d'),
            'javert': (24583512, '9001750c6dfb34505b21fad89b204185670abdad94bda1b7cf11ef1fd5b4bfb2'),
            'marius': (24976728, 'b8e6feb59bccdd2b2f661f6b23e1bc0630a8abd717e93c483b94e0ab6657df75'),
        },
    },
}


def program_file(system, machine=None):
    """(file, SHA-256) of the program for this machine, or None when the project publishes none for it."""
    machine = (machine or platform.machine()).lower()
    machine = {'amd64': 'x86_64', 'arm64': 'arm64' if system == 'mac' else 'aarch64'}.get(machine, machine)
    return PROGRAMS.get((system, machine))


def program(folder):
    return os.path.join(folder, 'pocket-tts')


def config(folder):
    return os.path.join(folder, 'config.yaml')


def voice_file(folder, voice):
    return os.path.join(folder, 'voices', voice + '.safetensors')


def wanted(folder, system, model, voices):
    """Every file an install leaves in `folder`, in the order it is fetched: (path, url, size, SHA-256). The size of
    the program is not known ahead (0)."""
    spec = MODELS[model]
    found = program_file(system)
    files = []
    if found:
        files.append((os.path.join(folder, found[0]), PROGRAM_URL + found[0], 0, found[1]))
    files.append((os.path.join(folder, 'original.yaml'), CONFIG_URL % model) + spec['original.yaml'])
    for name, revision in (('tokenizer.json', TOKENIZER_REVISION), ('model.safetensors', spec['revision'])):
        size, digest = spec[name]
        files.append((os.path.join(folder, name), FILES_URL % (revision, model, name), size, digest))
    for voice in voices:
        size, digest = spec['voices'][voice]
        files.append((voice_file(folder, voice),
                      FILES_URL % (VOICES_REVISION, model, 'embeddings/%s.safetensors' % voice), size, digest))
    return files


def mark(folder):
    """The file that says the install in `folder` finished: it holds what was installed (see `stamp`)."""
    return os.path.join(folder, 'ready')


def stamp(model, voices):
    return '%s %s %s\n' % (VERSION, model, ' '.join(sorted(voices)))


def ready(folder, model, voices):
    """True when `folder` holds a finished install of this program version, this model and these voices."""
    try:
        with open(mark(folder)) as fh:
            return fh.read() == stamp(model, voices) and os.path.exists(program(folder))
    except OSError:
        return False


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def good(path, size, digest):
    """True when the file at `path` is the one wanted: the size, when known, and the SHA-256, when published."""
    try:
        if size and os.path.getsize(path) != size:
            return False
        return os.path.getsize(path) > 0 and (not digest or sha256(path) == digest)
    except OSError:
        return False


def check_config(text, model):
    """Raises ValueError unless the project's configuration names, for the weights and for the tokenizer, the very
    revisions this module fetches: the files checked here must be the ones the program was made to speak with."""
    base = 'hf://kyutai/pocket-tts-without-voice-cloning/languages/%s/' % model
    for line in ('weights_path_without_voice_cloning: %smodel.safetensors@%s' % (base, MODELS[model]['revision']),
                 'tokenizer_path: %stokenizer.json@%s' % (base, TOKENIZER_REVISION)):
        if not re.search(r'(?m)^\s*%s\s*$' % re.escape(line), text):
            raise ValueError('a configuração do modelo aponta outra versão dos arquivos que o plugin confere')


def local_config(text, folder):
    """The project's configuration of a model with the places of its files written as paths in `folder`. The lines
    that named Hugging Face are the ones that made the program ask the network at each start."""
    weights = os.path.join(folder, 'model.safetensors')
    text, found = re.subn(r'(?m)^(weights_path(?:_without_voice_cloning)?:)[ \t]*\S.*$',
                          lambda m: '%s %s' % (m.group(1), weights), text)
    text, tokenizer = re.subn(r'(?m)^(\s+tokenizer_path:)[ \t]*\S.*$',
                              lambda m: '%s %s' % (m.group(1), os.path.join(folder, 'tokenizer.json')), text)
    if not found or not tokenizer or re.search(r'\b(?:hf|https?)://', text):
        raise ValueError('a configuração do modelo veio num formato que o plugin não conhece')
    return text


def write_config(folder):
    """Writes the local configuration of `folder` from the project's own, kept beside it."""
    with open(os.path.join(folder, 'original.yaml'), encoding='utf-8') as fh:
        text = local_config(fh.read(), folder)
    part = '%s.part-%d' % (config(folder), os.getpid())
    try:
        with open(part, 'w', encoding='utf-8') as fh:
            fh.write(text)
        os.replace(part, config(folder))
    finally:
        if os.path.exists(part):
            os.remove(part)


def settle_config(folder):
    """The configuration holds whole paths: when the data folder moved (another home, another CLAUDE_CONFIG_DIR) it
    is written again for where the files are now. Without the files to do it, it stays as it is."""
    try:
        with open(config(folder), encoding='utf-8') as fh:
            if os.path.join(folder, 'model.safetensors') in fh.read():
                return
        write_config(folder)
    except (OSError, ValueError):
        pass


def check_program(folder):
    """Raises ValueError unless the program runs here: it needs a system as new as it was built for (on Linux, glibc
    2.34: Ubuntu 22.04, Debian 12) and a folder programs may run from."""
    why = ''
    try:
        done = subprocess.run([program(folder), '--version'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=RUN_WAIT)
        if done.returncode == 0:
            return
        said = (done.stderr or done.stdout).decode('utf-8', 'replace').strip().splitlines()
        why = said[-1] if said else 'código %d' % done.returncode
    except subprocess.TimeoutExpired:
        why = 'não respondeu em %d segundos' % RUN_WAIT
    except OSError as error:
        why = str(error)
    raise ValueError('o programa do motor não roda nesta máquina (%s); no Linux ele pede a glibc 2.34 ou mais nova '
                     '(Ubuntu 22.04, Debian 12)' % why)


def unpack(archive, dest):
    """Takes the program (the member named `pocket-tts`, a plain file) out of the release archive into `dest`."""
    with tarfile.open(archive) as tar:
        member = next((m for m in tar.getmembers() if m.isfile() and os.path.basename(m.name) == 'pocket-tts'), None)
        if member is None:
            raise ValueError('o pacote do motor veio sem o programa')
        source = tar.extractfile(member)
        part = '%s.part-%d' % (dest, os.getpid())
        try:
            with open(part, 'wb') as fh:
                for block in iter(lambda: source.read(1 << 20), b''):
                    fh.write(block)
            os.chmod(part, 0o755)
            os.replace(part, dest)
        finally:
            if os.path.exists(part):
                os.remove(part)


def install(folder, system, model, voices, fetch, report=lambda name, done, total, step, steps: None):
    """Leaves in `folder` the program, the model, its tokenizer, the voices and the local configuration, fetching
    only what is missing or wrong. `fetch(url, dest, hook)` downloads one file (urlretrieve's shape); `report` is
    told the step in course. Raises ValueError when a file does not match what was expected, or when the project
    has no program for this machine."""
    if not program_file(system):
        raise ValueError('o motor não tem programa para esta máquina (%s, %s)' % (system, platform.machine()))
    os.makedirs(os.path.join(folder, 'voices'), exist_ok=True)
    left = glob.glob(os.path.join(folder, '*.part-*')) + glob.glob(os.path.join(folder, 'voices', '*.part-*'))
    for path in [mark(folder)] + left:  # until the end, the install is not one to speak with; `left` is what an
        try:                            # install that died half way left (one install runs at a time)
            os.remove(path)
        except OSError:
            pass
    files = wanted(folder, system, model, voices)
    for step, (path, url, size, digest) in enumerate(files, 1):
        name = os.path.basename(path)
        if size and good(path, size, digest):
            continue
        report(name, 0, size, step, len(files))
        part = '%s.part-%d' % (path, os.getpid())  # one per process: two installs never share a file
        try:
            fetch(url, part, lambda blocks, block, total, name=name, size=size, step=step:
                  report(name, blocks * block, size or max(total, 0), step, len(files)))
            if not good(part, size, digest):
                raise ValueError('o arquivo %s chegou diferente do esperado' % name)
            if name == 'original.yaml':  # before the big files: they are fetched only if they are the right ones
                with open(part, encoding='utf-8') as fh:
                    check_config(fh.read(), model)
            os.replace(part, path)
        finally:
            if os.path.exists(part):
                os.remove(part)
    archive = files[0][0]
    unpack(archive, program(folder))
    os.remove(archive)
    check_program(folder)
    write_config(folder)
    with open(mark(folder), 'w') as fh:
        fh.write(stamp(model, voices))


def samples(wav):
    """The 16-bit samples inside what the server answers: a WAV that says 24 kHz, mono, 16 bits, with the samples
    after the `data` header (the size written there is a placeholder: the audio is sent as it is made)."""
    if wav[:4] != b'RIFF' or wav[8:12] != b'WAVE':
        raise ValueError('o motor não respondeu com áudio')
    fmt, data = wav.find(b'fmt '), wav.find(b'data')
    if fmt < 0 or data < 0 or len(wav) < fmt + 24:
        raise ValueError('o motor respondeu com um áudio sem cabeçalho')
    kind, channels = int.from_bytes(wav[fmt + 8:fmt + 10], 'little'), int.from_bytes(wav[fmt + 10:fmt + 12], 'little')
    rate, bits = int.from_bytes(wav[fmt + 12:fmt + 16], 'little'), int.from_bytes(wav[fmt + 22:fmt + 24], 'little')
    if (kind, channels, rate, bits) != (1, 1, RATE, 16):
        raise ValueError('o motor respondeu com um áudio de outro formato (%d Hz, %d canais, %d bits)'
                         % (rate, channels, bits))
    pcm = wav[data + 8:]
    return pcm[:len(pcm) - len(pcm) % 2]


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def _die_with_parent():
    """Linux: the server gets SIGTERM when the speech that started it dies, whatever killed it."""
    try:
        _LIBC.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


_LIBC = None


class Server:
    """The program serving one speech: started with the model and one voice, asked piece by piece, ended at the
    close. It listens on 127.0.0.1 alone, on a port the system gave."""

    def __init__(self, folder, voice, log=None, start_wait=START_WAIT):
        global _LIBC
        settle_config(folder)
        self.port = free_port()
        before = None
        if sys.platform.startswith('linux'):
            try:
                import ctypes
                _LIBC = _LIBC or ctypes.CDLL(None)
                before = _die_with_parent
            except Exception:
                before = None
        self.proc = subprocess.Popen(
            [program(folder), 'serve', '--host', '127.0.0.1', '--port', str(self.port), '--config', config(folder),
             '--default-voice', voice_file(folder, voice)],
            stdin=subprocess.DEVNULL, stdout=log or subprocess.DEVNULL, stderr=log or subprocess.DEVNULL,
            preexec_fn=before)
        self.direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never through a proxy
        try:
            self._wait(start_wait)
        except BaseException:
            self.close()
            raise

    def _url(self, path):
        return 'http://127.0.0.1:%d%s' % (self.port, path)

    def _wait(self, limit):
        deadline = time.monotonic() + limit
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError('o motor encerrou ao iniciar (código %s)' % self.proc.returncode)
            try:
                with self.direct.open(self._url('/health'), timeout=2) as answer:
                    if answer.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError('o motor não respondeu em %d segundos' % limit)
            time.sleep(0.05)

    def speak(self, text):
        """The 16-bit samples (bytes) of `text` in the voice the server was started with; none for a text the engine
        finds nothing to say in. A piece whose answer takes longer than PIECE_WAIT is asked once more: a speech
        frozen by a pause finds the wait run out when it continues."""
        try:
            return self._ask(text)
        except socket.timeout:
            return self._ask(text)
        except urllib.error.URLError as error:
            if not isinstance(error.reason, socket.timeout):
                raise
            return self._ask(text)

    def _ask(self, text):
        body = urllib.parse.urlencode({'text': text}).encode()
        try:
            with self.direct.open(urllib.request.Request(self._url('/tts'), data=body), timeout=PIECE_WAIT) as answer:
                return samples(answer.read())
        except urllib.error.HTTPError as error:
            if error.code == 400:  # an empty text: silence, not a failure
                return b''
            raise
        except http.client.IncompleteRead as cut:
            # a text the engine empties by itself (it drops quotes and brackets): it sends the header of the audio
            # and ends the stream. Silence too; cut after that, it is a failure
            if len(cut.partial) <= HEADER:
                return b''
            raise

    def kill(self):
        """Ends the program at once, without waiting for it: for a speech that is itself ending this instant."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass

    def close(self):
        proc, self.proc = self.proc, None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
