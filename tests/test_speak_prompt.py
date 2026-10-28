import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(ROOT, 'prompts', 'build-speak-prompt.py')


def build():
    spec = importlib.util.spec_from_file_location('build_speak_prompt', GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


def blocks(text, lang):
    return re.findall(r'^~~~~%s\n(.*?)^~~~~$' % lang, text, re.S | re.M)


class SpeakPromptTest(unittest.TestCase):
    def test_prompt_is_up_to_date(self):
        done = subprocess.run([sys.executable, '-I', GENERATOR, '--check'], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_prompt_explains_the_microphone_behavior(self):
        text = build()
        self.assertIn('começar a ditar', text)
        self.assertIn('o microfone já estiver gravando', text)
        self.assertIn('chamada de vídeo', text)
        self.assertIn('/speak status', text)

    def test_prompt_has_nothing_of_this_repository(self):
        # Only the three exact paths where the prompt installs the hooks and the skill on the other machine are allowed; they are
        # replaced by a marker before the search, and `hooks/speak` is then banned without exception.
        text = build()
        for allowed in ('.claude/hooks/speak-stop.py', '.claude/hooks/speak-cut.sh', '.claude/skills/speak/SKILL.md'):
            self.assertIn(allowed, text)
            text = re.sub(re.escape(allowed) + r'(?![\w.])', '<permitido>', text)
        for pattern in (r'harness', r'ricardo', r'souza', r'rules/', r'hooks/speak'):
            found = re.search(pattern, text, re.I)
            self.assertIsNone(found, '%s: %r' % (pattern, found and text[max(0, found.start() - 40):found.end() + 40]))

    def test_embedded_code_is_valid(self):
        text = build()
        py = blocks(text, 'python')
        self.assertEqual(len(py), 2)
        for code in py:
            compile(code, 'bloco', 'exec')
        import json
        js = blocks(text, 'json')
        self.assertEqual(len(js), 1)
        hooks = json.loads(js[0])['hooks']
        self.assertEqual(sorted(hooks), ['Stop', 'UserPromptSubmit'])
        for event, script, runner in (('Stop', 'speak-stop.py', 'python3 -I'),
                                      ('UserPromptSubmit', 'speak-cut.sh', 'bash')):
            hook = hooks[event][0]['hooks'][0]
            self.assertIn(script, hook['command'])
            self.assertIn(runner, hook['command'])
            self.assertEqual(hook['timeout'], 5)
        sh = blocks(text, 'bash')
        self.assertEqual(len(sh), 1)
        with tempfile.NamedTemporaryFile('w', suffix='.sh') as fh:
            fh.write(sh[0])
            fh.flush()
            self.assertEqual(subprocess.run(['bash', '-n', fh.name]).returncode, 0)

    def test_prompt_creates_the_folders_and_calls_speak_by_path(self):
        text = build()
        self.assertIn('mkdir -p ~/.local/bin', text)
        self.assertIn('mkdir -p ~/.claude/hooks', text)
        for call in ('~/.local/bin/speak install', '~/.local/bin/speak test', '~/.local/bin/speak status'):
            self.assertIn(call, text)

    def test_prompt_leaves_the_line_out_when_the_voice_is_off(self):
        text = build()
        self.assertIn('Com a voz desligada, deixe a linha de fora', text)
        self.assertNotIn('A linha existe mesmo com a voz desligada', text)
        self.assertIn('speak silent', text)

    def test_prompt_teaches_per_session(self):
        text = build()
        self.assertIn('speak off all', text)
        self.assertIn('todas as sessões', text)
        self.assertIn('espera a vez', text)  # a new speech waits its turn; a new message cuts nothing
        self.assertNotIn('speak stop --mine`); uma sessão', text)

    def test_prompt_installs_the_skill(self):
        text = build()
        self.assertIn('~/.claude/skills/speak/SKILL.md', text)
        self.assertIn('/speak', text)
        with open(os.path.join(ROOT, 'skills', 'speak', 'SKILL.md'), encoding='utf-8') as fh:
            skill = fh.read().rstrip('\n')
        self.assertIn('~~~~markdown\n' + skill + '\n~~~~', text)

    def test_prompt_replaces_old_section(self):
        text = build()
        step7 = [l for l in text.splitlines() if l.startswith('7. ')][0]
        self.assertIn('# Resposta falada', step7)
        self.assertIn('# Spoken reply', step7)
        self.assertIn('# Spoken reply\n', text)

    def test_prompt_cleans_the_old_install(self):
        text = build()
        for old in ('~/.local/bin/voz', '~/.claude/hooks/voz-stop.py', '~/.claude/hooks/voz-parar.sh'):
            self.assertIn(old, text)
        self.assertIn('entradas de gancho cujo comando cita `voz-stop.py` ou `voz-parar.sh`', text)
        self.assertLess(text.index('~/.claude/hooks/voz-stop.py'), text.index('~/.local/bin/speak com exatamente'))
        snippet = re.search(r'^~~~~sh\n(.*?)^~~~~$', text, re.S | re.M).group(1)
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, '.claude', 'hooks'))
            os.makedirs(os.path.join(home, '.local', 'bin'))
            for rel in ('.local/bin/voz', '.claude/hooks/voz-stop.py', '.claude/hooks/voz-parar.sh'):
                open(os.path.join(home, rel), 'w').close()
            cmd = lambda c: {'hooks': [{'type': 'command', 'command': c}]}
            settings = {'x': 1, 'hooks': {'Stop': [cmd('python3 $HOME/.claude/hooks/voz-stop.py'), cmd('outro')],
                                           'UserPromptSubmit': [cmd('bash voz-parar.sh')]}}
            path = os.path.join(home, '.claude', 'settings.json')
            with open(path, 'w') as fh:
                json.dump(settings, fh)
            done = subprocess.run(['bash', '-c', snippet], env={'HOME': home, 'PATH': '/usr/bin:/bin'},
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            for rel in ('.local/bin/voz', '.claude/hooks/voz-stop.py', '.claude/hooks/voz-parar.sh'):
                self.assertFalse(os.path.exists(os.path.join(home, rel)), rel)
            with open(path) as fh:
                self.assertEqual(json.load(fh), {'x': 1, 'hooks': {'Stop': [cmd('outro')]}})


if __name__ == '__main__':
    unittest.main()
