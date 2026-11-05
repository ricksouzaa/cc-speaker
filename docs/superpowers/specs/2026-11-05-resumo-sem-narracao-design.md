# Resumo sem narração e resumo em mensagem própria: desenho

Data: 05/11/2026. Pedido do Ricardo (palavras dele em `docs/proximos-passos.md`, "Pedidos para depois"), desenhado em conversa no mesmo dia. Decisões dele marcadas como dele; o resto são escolhas minhas, para a revisão dele.

## Intenção e porquê

Hoje "desligar a voz" apaga duas coisas de uma vez: o som e a linha `🔊` escrita ao fim da resposta. O Ricardo descobriu que a linha vale por si: numa reunião ele quer ler a resposta sem ouvir nada, e o resumo é o que deixa acompanhar rápido; no celular a leitura da tela é difícil, e muitas vezes só o resumo já explica a resposta inteira. Então são dois pedidos:

1. **Calar só a voz e manter o resumo escrito.** Com a voz calada, a linha `🔊` continua a sair ao fim de cada resposta, e os botões "Ouvir de novo" continuam funcionando, como hoje já funcionam com a voz desligada.
2. **O resumo numa mensagem própria.** No celular, o app do Claude Code tem o próprio botão de ler em voz alta, mas ele lê a mensagem inteira; com a linha `🔊` numa mensagem separada ao fim da resposta, o play toca só o resumo. O alvo principal do plugin continua sendo o terminal, onde não há play nativo; o celular usa o play do app.

Os dois saem em versões separadas (0.18.0 e 0.19.0), porque o segundo depende de um teste que só o Ricardo pode fazer (no celular, noutro repositório e noutra conta: a conta corporativa dele não tem o controle remoto).

## Objetivos, não objetivos e anti-objetivos

- Objetivos: três estados para a voz (ligada, só o resumo escrito, desligada); uma escolha, desligada por padrão, que põe a linha `🔊` numa mensagem própria; tudo no painel, por escrito e em palavras, com o alcance "só esta sessão" ou "todas", como as escolhas de hoje.
- Não objetivos: mandar áudio ao celular (retirado em 28/10/2026); mudar o que a voz lê ou como lê; tocar a linha `🔊` no celular pelo plugin.
- Anti-objetivos (seria um fracasso mesmo funcionando): a mensagem separada custando uma volta a mais em quem não a pediu; um pedido de permissão a cada resposta no celular; a linha `🔊` sumindo ou aparecendo duas vezes; quebrar quem usa `speak on` e `speak off` hoje.

## Restrições

- O Claude Code só separa mensagens quando algo acontece entre dois textos do modelo: uma chamada de ferramenta ou uma volta a mais pedida por um gancho. Qualquer separação custa uma chamada a mais do modelo por resposta.
- Uma chamada de ferramenta antes da linha (testada na conversa de 05/11/2026 com um `true` no Bash) separa a mensagem, mas no celular cada chamada do Bash pode pedir permissão: recusada por isso. Fica como reserva (ver a parte 2) se o gancho não separar a mensagem no app.
- O gancho de parada (`Stop`) pode devolver `{"decision": "block", "reason": "..."}`: o modelo continua a resposta lendo o motivo, e o gancho roda de novo com `stop_hook_active: true` na entrada (conferido em 05/11/2026 em https://code.claude.com/docs/en/hooks e https://code.claude.com/docs/en/hooks-guide). A documentação também diz que `hookSpecificOutput.additionalContext` na saída do `Stop` é um retorno sem erro que mantém a conversa, rotulado "Stop hook feedback" no transcript e sem aviso de erro de gancho na tela, enquanto o `block` aparece como erro de bloqueio. O construtor experimenta primeiro o `additionalContext`; se ele não fizer o modelo continuar, usa o `block`. Depois de oito bloqueios seguidos o Claude Code encerra a rodada de qualquer jeito; aqui nunca passa de um. A documentação diz que `last_assistant_message` é o texto da resposta final, sem dizer se é só o último bloco de texto, e recomenda usá-lo em vez do transcript; o gancho já faz isso.
- Som, microfone e processos continuam em `lib/speak_os.py`; nada aqui depende do sistema.

## Parte 1: a voz com três estados (versão 0.18.0)

### Estados

| Estado | Comando | Som | Linha `🔊` | No painel e no `status` |
|---|---|---|---|---|
| ligada | `speak on` | fala | escrita | "Ligada" / `ligada` |
| só o resumo escrito | `speak quiet` | não fala | escrita | "Só o resumo escrito" / `só o resumo escrito` |
| desligada | `speak off` | não fala | não escrita | "Desligada" / `desligada` |

Decisão do Ricardo: os três estados, inclusive "desligar os dois". O nome `quiet` e os rótulos são escolha minha.

- `speak quiet [all]` tem o mesmo alcance e a mesma forma de `on` e `off`: sem `all`, só esta sessão; com `all` (ou fora de uma sessão), o valor geral, apagando as exceções das sessões, como `off all` faz hoje. Como `off`, corta a fala em curso do alcance (`stop_if_mine` ou `stop_current`).
- Em palavras, o modelo escolhe `quiet` quando o pedido fala em calar, silenciar ou desligar a voz **e** manter, deixar ou continuar com o resumo escrito ("cala a voz mas deixa o resumo", "só o resumo escrito", "sem áudio, só o texto"); "silêncio", "desliga a voz", "desliga tudo" continuam sendo `off`. A regra (`rules/speak.md`) ganha esse item ao lado de ligar e desligar.
- No modo leitura inteira (`speak mode full`) o estado `quiet` cala a voz e, como hoje nesse modo, nenhuma linha é escrita: na prática é o mesmo que desligada. O painel já esconde a linha do tamanho nesse modo; nada mais a mostrar. O README diz isso numa frase.

### Como se guarda

- Valor geral: hoje é a existência do arquivo `conf/off`. Passa a ser um valor com três estados. O construtor escolhe o arquivo (minha sugestão: `conf/power` com `on`, `quiet` ou `off`, e o `conf/off` antigo migrado em `migrate()` e apagado; `conf/voice` já guarda a voz de leitura), desde que uma pasta de dados antiga com o `conf/off` continue a ler "desligada" sem perder nada.
- Campo `voice` da sessão: hoje `speaking` ou `muted`; ganha `quiet`. `CLAUDE_SPEAK=0` continua semeando `muted`.
- `is_on()` continua a responder se a voz **fala**; nasce uma função que responde o estado (`on`, `quiet`, `off`), com a mesma precedência de hoje (variável de ambiente, sessão, geral).

### O que muda nos ganchos e na regra

- `speak silent` (lido pelo gancho de mensagem nova, `hooks/speak-cut.py`) passa a responder "não escreva a linha" só quando o estado é `off`, ou quando ele é `on` sem motor (instalando ou faltando), como hoje. No estado `quiet` a linha é pedida mesmo sem motor: quem a pediu quer lê-la.
- No estado `quiet` o gancho de mensagem nova age como com a voz ligada: avisa a volta da linha quando o modelo tinha sido avisado para omiti-la (`told` em `silent` ou `full`) e repete o lembrete enquanto a última resposta guardada estiver sem a linha (`speak forgot`). O texto do lembrete deixa de dizer "a voz está ligada" e passa a dizer que a linha `🔊` está pedida (vale nos dois estados).
- `speak say -` (gancho de parada) guarda a última resposta como hoje e, em `quiet`, não fala. `speak again` e os botões "Ouvir de novo" tocam, como já tocam com a voz desligada.
- Na regra, o item "When the voice is off, leave the line out" ganha a frase: com `speak quiet` a voz cala mas a linha fica, escrita como com a voz ligada; um `speak quiet` que você acabou de rodar traz a linha de volta.

### `status`, `status --json` e o painel

- `speak status`: `voz: só o resumo escrito` na primeira linha de estado; `geral:` com os três valores; `esta sessão:` com `falando`, `só o resumo`, `muda` ou `segue a geral`.
- `status --json`: `on` continua booleano (falso em `quiet` e `off`, para o módulo não quebrar) e nasce `power` com `on`, `quiet` ou `off`; `scope.on` como hoje.
- Painel (`hooks/register.tsx`): a linha "Voz" lista Ligada / Só o resumo escrito / Desligada; a escolha do meio roda `speak quiet` (com `all` conforme "Mudar em"). `/speak quiet [all]` escrito funciona como `/speak on`. A frase do rodapé: "A voz está calada nesta sessão; o resumo continua escrito." (ou "em todas as sessões"). O `USAGE` e o `argumentHint` listam `quiet`.
- README: a tabela de ligar/desligar ganha a linha do meio; CHANGELOG em "Adicionado".

## Parte 2: o resumo numa mensagem própria (versão 0.19.0)

### A escolha

- `speak split on|off [all]`: desligada por padrão; alcance e guarda como `mode` (campo `split` na sessão, arquivo geral `conf/split`). Nome e rótulos são escolha minha.
- Painel: linha "Resumo em mensagem própria" com Sim / Não, mostrada só com a leitura em "só o resumo" (como a linha do tamanho). `/speak split on|off [all]` escrito. Rodapé: "O resumo passa a vir numa mensagem própria nesta sessão." / "O resumo volta a fechar a própria resposta nesta sessão."
- Em palavras: "manda o resumo numa mensagem separada", "resumo em mensagem própria", "resumo junto com a resposta de novo".
- Vale sempre que a linha `🔊` é pedida: estados `on` e `quiet`, modo resumo. Com a voz desligada ou na leitura inteira não faz nada. Decisão do Ricardo: é uma escolha, não o padrão, porque custa uma volta a mais e no terminal não serve para nada.

### Como a mensagem se separa

Pelo gancho de parada (`hooks/speak-stop.py`), sem ferramenta e sem permissão:

1. A resposta termina sem a linha `🔊` (o modelo é avisado disso, abaixo). O gancho roda: com `split` ligado, a linha pedida (não `silent`, modo resumo), a resposta sem a linha e **sem corpo pendente** da sessão, ele guarda o corpo da resposta como pendente (`state/pending/<sessão>`, ou o que o construtor preferir) e devolve `{"decision": "block", "reason": "speak: escreva agora, como mensagem própria, só a linha 🔊 com o resumo da resposta que acabou de dar (<tamanho em vigor>); nada mais."}`. A marca de "já pedi a linha" é o corpo pendente, não o `stop_hook_active`: outro gancho de parada que bloqueie na mesma sessão (o do ai-harness, por exemplo) pode deixar esse campo verdadeiro já na primeira parada. O campo serve só de segurança a mais: verdadeiro, nunca bloquear.
2. O modelo escreve só a linha. O gancho roda de novo: a resposta é só a linha `🔊` (nenhum outro texto) e há corpo pendente, então junta os dois (`corpo + "\n\n" + linha`), guarda isso como a última resposta (para "Ouvir de novo → Resposta inteira" ler a resposta toda), apaga o pendente e fala a linha como hoje.
3. Se mesmo assim a resposta vier sem a linha, o gancho não bloqueia de novo (há pendente: nunca mais de uma volta a mais por resposta): guarda o que há, apaga o pendente, não fala, e o lembrete de `speak forgot` cuida do resto na mensagem seguinte. Se a resposta vier com corpo e linha juntos (o modelo não separou, ou é uma resposta nova depois de um pendente que ficou para trás), ele usa só essa resposta, apaga o pendente e fala a linha sem separar nada dessa vez.
4. Um corpo pendente que ficar para trás é descartado pelo item 3 na parada seguinte, ou pela poda das sessões mortas. O gancho de mensagem nova não mexe no pendente: a documentação diz que `UserPromptSubmit` também dispara em rodadas que o Claude Code começa sozinho, sem dizer se a volta pedida por um bloqueio é uma delas, e o construtor confere isso num gancho de registro antes de escrever a nota do `split` (se disparar ali, a nota não pode sair nessa volta: com pendente na sessão, o gancho de mensagem nova não imprime nota nenhuma).

O que o modelo é avisado: com `split` ligado e a linha pedida, o gancho de mensagem nova imprime a cada mensagem (como faz com a leitura inteira) uma nota `speak:` dizendo para não terminar a resposta com a linha `🔊`, porque o gancho de parada a pedirá logo depois, e para então responder só com ela. Quando `split` desliga, a nota de volta ("termine com a linha") sai uma vez, como na volta do modo resumo. Com `split` ligado a nota de lembrete (`speak forgot`) não é usada: a nota do `split` já diz o que fazer. A regra (`rules/speak.md`) explica o mesmo em um item.

Custo: uma chamada a mais do modelo por resposta, só com `split` ligado; o README diz isso na linha da tabela.

### O que fica a ver no teste do Ricardo

- No app do celular, a segunda mensagem (só a linha) aparece com um play próprio? Se não aparecer, a reserva é o modelo fazer uma chamada leve antes da linha (`speak mark`, um comando que não faz nada), aceitando o pedido de permissão ou liberando o comando nas permissões; isso seria uma versão nova, decidida com ele.
- No terminal, como o Claude Code mostra o motivo do bloqueio (se mostra). Aceitável como vier; registrar em `docs/proximos-passos.md`.

## Verificação

- `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests`: testes novos em `tests/test_speak.py` para os três estados (`quiet` nesta sessão e em todas; `status` e `--json`; `silent` em `quiet` com e sem motor; `say -` em `quiet` guarda e não fala; `again` toca; a migração do `conf/off`), para as notas do gancho de mensagem nova (`quiet` pede a linha, `split` pede a mensagem própria, a volta de cada um) e para o gancho de parada com `split` (bloqueia uma vez, junta corpo e linha, nunca bloqueia duas vezes, fala a linha já presente, descarta o pendente).
- `claude plugin test .`: `hooks/register.test.tsx` cobre a linha "Voz" com três valores e `/speak quiet`, e a linha "Resumo em mensagem própria" (só no modo resumo) com `/speak split`.
- `claude plugin validate .`.
- Duas versões, cada uma pelo fluxo de `.claude/rules/git-workflow.md`: 0.18.0 (parte 1) e 0.19.0 (parte 2). `docs/proximos-passos.md` registra as decisões e o teste que fica com o Ricardo.

## O que fica com o construtor

- O arquivo e a migração do valor geral da voz; o nome do arquivo do corpo pendente.
- O texto exato das notas `speak:` e dos rótulos, dentro do que está acima.
- Onde, em `hooks/speak-stop.py`, entra a leitura de `stop_hook_active` e a escrita da saída JSON (hoje o gancho não escreve nada na saída).
- Conferir, com um gancho de registro numa rodada de teste, o que `last_assistant_message` traz na segunda parada (só a linha, ou a rodada inteira; se vier a rodada inteira, a junção do item 2 não pode duplicar o corpo) e se `UserPromptSubmit` dispara na volta pedida pelo bloqueio.
