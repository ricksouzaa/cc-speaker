#!/usr/bin/env python3
"""Generates prompts/speak-claude-code.txt: a self-contained prompt that sets up the spoken replies in any Claude Code.

The code in the prompt is read from bin/speak, hooks/speak-stop.py and hooks/speak-cut.sh, with the mentions of this
repository made neutral. Without arguments it writes the file; with --check it exits 1 when the file is stale.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'prompts', 'speak-claude-code.txt')
FENCE = '~~~~'  # four tildes: the embedded code has triple backticks

NEUTRAL = (
    (' (rules/speak.md)', ''),
    ('used by hooks/speak-stop.py', 'used by the end-of-reply hook'),
    ('used by hooks/speak-cut.sh', 'used by the new-message hook'),
)

HEAD = """Configure no meu Claude Code a narração em voz alta das respostas, com um motor de voz que roda localmente, sem rede e sem custo.

Contexto: quero que cada resposta do Claude Code seja lida em voz alta, em português do Brasil, logo que ela termina. A voz vem do Kokoro (modelo de voz aberto) rodando na minha máquina. O texto lido é a prosa e as tabelas da resposta, sem blocos de código, caminhos, links e nomes de arquivo. Há também um modo que lê só a última linha da resposta, que começa com 🔊. Uma fala nova, de qualquer sessão, não corta a que está tocando: espera a vez numa fila. Só começar a ditar pelo microfone corta a leitura, e se eu já estiver ditando quando chega a vez de uma fala, ela espera o microfone ficar livre. Posso calar ou ligar a voz de uma sessão sem mexer nas outras, e com a voz desligada a resposta não traz a linha 🔊, para não gastar texto à toa.

Requisitos da máquina: Linux com áudio pelo PipeWire, PulseAudio ou ALSA (um destes comandos: pw-play, paplay ou aplay), python3, e o uv (gerenciador de Python da Astral). O motor ocupa perto de 350 megabytes. Nada precisa de sudo.

Faça nesta ordem, e me mostre o resultado de cada passo:

1. Confira os requisitos. Se faltar o uv, me diga como instalá-lo (https://docs.astral.sh/uv/) e pare. Se faltar tocador de áudio, me diga e pare.
"""

CLEAN = (
    "2. Limpe a instalação do prompt antigo (o comando se chamava `voz`), se existir. Apague, sem erro se faltarem, "
    "`~/.local/bin/voz`, `~/.claude/hooks/voz-stop.py` e `~/.claude/hooks/voz-parar.sh`. Depois, se "
    "~/.claude/settings.json existir, retire dele as entradas de gancho cujo comando cita `voz-stop.py` ou "
    "`voz-parar.sh`, deixando todas as demais. Por exemplo:")

CLEAN_CODE = r"""rm -f ~/.local/bin/voz ~/.claude/hooks/voz-stop.py ~/.claude/hooks/voz-parar.sh
f=~/.claude/settings.json
[ -f "$f" ] && python3 - "$f" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as fh:
    data = json.load(fh)
old = ('voz-stop.py', 'voz-parar.sh')
hooks = data.get('hooks', {})
for event in list(hooks):
    groups = []
    for group in hooks[event]:
        group['hooks'] = [h for h in group.get('hooks', []) if not any(n in h.get('command', '') for n in old)]
        if group['hooks']:
            groups.append(group)
    if groups:
        hooks[event] = groups
    else:
        del hooks[event]
with open(path, 'w') as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
PY
exit 0"""

STEPCMD = '3. Crie a pasta com `mkdir -p ~/.local/bin`. Depois crie o comando `speak` em ~/.local/bin/speak com exatamente o conteúdo abaixo e torne-o executável (chmod +x). Confira que ~/.local/bin está no PATH; se não estiver, me avise.'

STEP3 = ("4. Crie a pasta com `mkdir -p ~/.claude/hooks`. Depois crie o gancho de fim de resposta em "
         "~/.claude/hooks/speak-stop.py com exatamente este conteúdo:")
STEP4 = ("5. Com a pasta ~/.claude/hooks já criada (`mkdir -p ~/.claude/hooks`, sem erro se ela existir), crie o "
         "gancho de mensagem nova em ~/.claude/hooks/speak-cut.sh com exatamente este conteúdo e "
         "torne-o executável:")

STEP5 = """6. Registre os dois ganchos em ~/.claude/settings.json (crie o arquivo com {} se não existir). Não apague nem substitua nada que já esteja lá: acrescente as duas entradas abaixo às listas "Stop" e "UserPromptSubmit" dentro de "hooks", criando as chaves que faltarem. Se já houver uma entrada com o mesmo comando, não duplique. Faça uma cópia de segurança do arquivo antes de mudar e confira depois que ele continua sendo JSON válido."""

SETTINGS = r"""{
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command", "timeout": 5,
        "command": "f=\"$HOME/.claude/hooks/speak-stop.py\"; [ -f \"$f\" ] && python3 -I \"$f\"; exit 0"}]}
    ],
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "timeout": 5,
        "command": "f=\"$HOME/.claude/hooks/speak-cut.sh\"; [ -f \"$f\" ] && bash \"$f\"; exit 0"}]}
    ]
  }
}"""

STEP6 = "7. Acrescente ao fim de ~/.claude/CLAUDE.md (crie se não existir) a seção abaixo, sem mexer no resto do arquivo. Se já houver uma seção `# Resposta falada` ou `# Spoken reply`, substitua-a inteira pelo conteúdo abaixo, em vez de acrescentar outra."

SECTION = """# Spoken reply

O gancho de fim de resposta lê cada resposta em voz alta: por padrão a prosa e as tabelas inteiras, sem blocos de código, caminhos, links e nomes de arquivo (`speak mode full`); ou só a última linha `🔊 <resumo>` (`speak mode summary`).

- Enquanto a voz está ligada, toda resposta ao humano termina com a linha `🔊`: uma ou duas frases curtas em português do Brasil simples, dizendo o que foi feito ou o que o humano precisa decidir. A leitura completa pula essa linha.
- Nela não entram código, nomes de arquivo, caminhos, comandos, saída de comandos, números de linha, links nem siglas: ela é ouvida, não lida.
- Quando um bloco de código precisa de explicação, a prosa diz em palavras o que ele faz, para que a leitura faça sentido sem o bloco.
- A voz não fala quando o microfone já está gravando (ditado, chamada de vídeo) e é cortada se uma gravação começar enquanto ela fala; só isso interrompe uma leitura, e uma fala nova espera a vez.
- Com a voz desligada, deixe a linha de fora, para não escrever texto à toa: o gancho de mensagem nova avisa numa nota `speak:` que vale para aquela mensagem (voz desligada nesta sessão ou em todas, ou motor não instalado), e um `speak off` que você acabou de rodar também vale. Sem a nota, ou depois de um `speak on`, a linha volta.
- Quando o humano pedir em palavras, falando ou digitando, para parar, calar, desligar ou ligar a voz ou o áudio, rode `speak off` ou `speak on` pelo Bash: isso vale só para esta sessão. Quando ele disser todas as sessões, tudo ou geral ("todas as sessões", "tudo", "geral"), rode `speak off all` ou `speak on all`. Confirme em uma frase o que passou a valer.
- Quando ele pedir em palavras para ler só o resumo ou a resposta inteira, rode `speak mode summary` ou `speak mode full` (com `all` quando ele disser todas as sessões, tudo ou geral). Confirme em uma frase.
- O comando de barra `/speak` existe para o humano (ligar, desligar, modo, status, parar; `all` no fim de ligar, desligar e modo vale para todas as sessões).
- Relatórios de subagentes não levam essa linha; só a sessão que conversa com o humano a escreve."""

SKILL_STEP = "8. Crie a pasta com `mkdir -p ~/.claude/skills/speak`. Depois crie o comando de barra /speak em ~/.claude/skills/speak/SKILL.md com exatamente este conteúdo:"

TAIL = """9. Instale o motor de voz rodando `~/.local/bin/speak install`. Ele cria um Python 3.12 isolado pelo uv, instala o pacote kokoro-onnx e baixa os dois arquivos do modelo. Pode levar alguns minutos.

10. Rode `~/.local/bin/speak test` e me pergunte se eu ouvi a frase de teste. Depois rode `~/.local/bin/speak status` e me mostre a saída.

11. No fim, me explique em poucas linhas como usar:
   - `/speak` é o comando de barra: `/speak on`, `/speak off`, `/speak mode summary`, `/speak mode full`, `/speak status` e `/speak stop`, com `all` no fim de on, off e mode para valer em todas as sessões; sem argumentos mostra o estado;
   - `speak off` e `speak on`, rodados dentro de uma sessão do Claude Code, calam e ligam a voz só daquela sessão; `speak off all` e `speak on all` valem para todas as sessões (fora do Claude Code, `speak off` e `speak on` já valem para todas);
   - uma fala nova, de qualquer sessão, espera a vez numa fila e não corta a que está tocando; `speak stop` corta a que toca e esvazia a fila, e `speak off` numa sessão tira só as falas dela; uma sessão muda não fala;
   - a voz também é cortada se eu começar a ditar ou gravar pelo microfone enquanto ela fala, e a fala espera, sem descartar, se o microfone já estiver gravando na sua vez (por exemplo durante um ditado ou uma chamada de vídeo);
   - o modo (`speak mode summary` ou `speak mode full`) e o liga e desliga (`speak on` e `speak off`) valem só para a sessão em que foram dados, ou para todas com `all` no fim;
   - também posso pedir em palavras ao Claude Code, na sessão, para calar ou ligar a voz; ele roda o comando certo (esta sessão, ou todas se eu disser "todas as sessões");
   - `speak mode summary` passa a ler só a linha 🔊, e `speak mode full` volta a ler a resposta inteira;
   - com a voz desligada (nesta sessão ou em todas) ou sem o motor instalado, o gancho de mensagem nova avisa o Claude Code, e a resposta vem sem a linha 🔊;
   - abrir o Claude Code com `CLAUDE_SPEAK=0 claude` faz só aquela sessão começar muda; um `speak on` dado depois nela vence;
   - `CLAUDE_SPEAK_VOICE` troca a voz (padrão pf_dora) e `CLAUDE_SPEAK_SPEED` muda a velocidade (padrão 1.1);
   - os erros de uma fala vão para ~/.local/state/claude-speak/error.log.
   Diga também que os ganchos só passam a valer numa sessão nova do Claude Code."""


def source(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        text = fh.read()
    for old, new in NEUTRAL:
        text = text.replace(old, new)
    return text.rstrip('\n')


def fenced(lang, code):
    return '%s%s\n%s\n%s' % (FENCE, lang, code.rstrip('\n'), FENCE)


def build():
    return '\n\n'.join([
        HEAD.rstrip('\n'),
        CLEAN,
        fenced('sh', CLEAN_CODE),
        STEPCMD,
        fenced('python', source('bin', 'speak')),
        STEP3,
        fenced('python', source('hooks', 'speak-stop.py')),
        STEP4,
        fenced('bash', source('hooks', 'speak-cut.sh')),
        STEP5,
        fenced('json', SETTINGS),
        STEP6,
        fenced('markdown', SECTION),
        SKILL_STEP,
        fenced('markdown', source('skills', 'speak', 'SKILL.md')),
        TAIL,
    ]) + '\n'


def main(argv):
    text = build()
    if argv[:1] == ['--check']:
        try:
            with open(OUT, encoding='utf-8') as fh:
                current = fh.read()
        except OSError:
            current = None
        if current != text:
            print('prompts/speak-claude-code.txt está desatualizado; rode: python3 prompts/build-speak-prompt.py', file=sys.stderr)
            return 1
        return 0
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
