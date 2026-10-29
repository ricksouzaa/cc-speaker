# Passagem: do ai-harness para o cc-speaker

Este repositório nasceu em 28/10/2026 de uma cópia das peças da voz do ai-harness (repositório privado `ricksouzaa/ai-harness`, versão `ee7bd73`). O histórico de mudanças ficou lá, de propósito: as mensagens antigas citam outros projetos.

## O que veio

- `bin/speak`: o comando (liga, desliga, modo, fila, motor Kokoro, instalação do motor).
- `hooks/speak-stop.py`: gancho de fim de resposta, entrega a resposta ao `speak`.
- `hooks/speak-cut.sh`: gancho de mensagem nova, avisa quando a voz está desligada para a resposta não trazer a linha 🔊.
- `rules/speak.md`: a regra da linha 🔊 que o Claude segue.
- `skills/speak/SKILL.md`: o comando de barra `/speak`.
- `prompts/`: gerador de um texto que instala a voz em qualquer Claude Code sem plugin (`build-speak-prompt.py`, com `--check`). Com o plugin pronto, decidir se ainda faz sentido.
- `tests/`: `python3 -m unittest discover -s tests` passa aqui sozinho (98 testes em 28/10/2026).

No ai-harness, hoje, o instalador liga `bin/speak` em `~/.local/bin/speak`, e os ganchos são registrados por `harness/hooks_install.py` (linhas dos ganchos `speak-stop.py` e `speak-cut.sh`). A regra vai para `~/.claude/rules/speak.md`. O motor fica em `~/.local/share/claude-speak/`, a configuração em `~/.config/claude-speak/` e o estado em `~/.local/state/claude-speak/`.

## Ordem combinada com o Ricardo

1. **Primeiro**: transformar isto num plugin do Claude Code que funciona exatamente como a voz de hoje, no Linux. O repositório serve também de catálogo de plugins para ser instalado. Num plugin, a regra da linha 🔊 não pode ser um arquivo de regras: entra por um gancho no começo da sessão (ou outro meio que o plugin permita).
2. **Troca sem buraco**: a voz do ai-harness só sai quando este plugin estiver instalado e falando. Quando estiver pronto, avise o Ricardo; a sessão do ai-harness tira de lá o comando, os ganchos, a regra e o `/speak` e instala o plugin como global, num só passo, para nunca haver duas vozes nem nenhuma.
3. **Depois**: as evoluções abaixo.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português; opção de trocar a voz entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema; o gancho em script do terminal passa a Python. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.

## Pedidos para depois da primeira etapa

- Nível de detalhe do resumo falado configurável em pequeno, médio ou grande (hoje sai sucinto demais).
- Filtrar melhor o que se narra. Exemplo real: na linha de sincronização do pickup a voz leu "HEAD 93a66bd" e o ramo "fix/fila-da-voz". Não narrar códigos de commit (sequências hexadecimais de 7 a 40 caracteres com dígitos), a palavra HEAD, nomes de ramo com barra e separadores como o ponto médio; revisar as outras regras de limpeza com exemplos de respostas reais.
- Estudar os outros narradores pesquisados em 28/10/2026 e escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- Modo remoto: num teste no controle remoto, um mp3 de 52 quilobytes gerado pelo motor e enviado pela ferramenta de envio de arquivo ao usuário chegou ao celular e tocou no aplicativo. Limites: só o modelo envia arquivo (os ganchos não), custa tokens a cada resposta e não toca sozinho. Estudar um modo remoto e alternativas sem o modelo.
  - Pedido do Ricardo (28/10/2026), próxima evolução: um modo "celular" que ele liga quando está no controle remoto (dirigindo, fora do computador). Nele o computador não toca nada; cada resposta vira um mp3 que chega ao celular para ele dar o play. Respeita o modo (inteira ou resumo) e o tamanho do resumo, igual à fala local.
  - Primeiro desenho (a discutir com ele): `speak phone on|off` (e `/speak:phone`). O gancho de fim de resposta, nesse modo, gera o mp3 com o mesmo texto que seria falado e devolve ao Claude um pedido de continuar ("envie este arquivo com a ferramenta de envio ao usuário e não escreva mais nada"); o Claude envia, e o gancho não repete na volta (campo de parada já ativa). Custa uma volta curta por resposta. Alternativa: o próprio Claude gera e envia o mp3 do resumo antes de terminar (mais barato, só serve para o resumo).
- Ideia do Ricardo: uma voz no estilo do Jarvis do Homem de Ferro. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator.

## Estado em 28/10/2026 (fim da primeira etapa, à espera da revisão do Ricardo)

- Ramo `feat/plugin`, sem push e sem merge. Desenho em `docs/superpowers/specs/2026-10-28-plugin-design.md`.
- Plugin `speak` instalado no escopo do usuário a partir do catálogo local `cc-speaker` (esta pasta), ligado.
- Tamanho do resumo e escolha da voz entraram já nesta etapa, por pedido do Ricardo.
- Enquanto existirem `~/.claude/hooks/speak-stop.py` ou `~/.claude/hooks/speak-cut.sh`, os ganchos do plugin ficam mudos (guarda temporária).
- Neste repositório toda sessão começa muda (`.claude/settings.local.json`, fora do git).

### Troca, pela sessão do ai-harness (depois do sim do Ricardo)

1. Tirar do ai-harness o comando (`~/.local/bin/speak`), os ganchos `speak-stop.py` e `speak-cut.sh` (arquivos em `~/.claude/hooks/` e linhas no `settings.json`), a regra `~/.claude/rules/speak.md` e o `/speak`.
2. Nada mais: na sessão seguinte, a guarda não vê mais a voz antiga e o plugin assume. Motor, escolhas e estado continuam nas mesmas pastas.
3. Conferir: sessão nova, `/speak:status`, uma resposta falada.
4. Volta, se falhar: reinstalar a voz antiga pelo ai-harness; o plugin volta a ficar mudo sozinho.

Depois da troca: tirar a guarda, mudar o catálogo para o GitHub (`ricksouzaa/cc-speaker`) depois do push.

## Pendente de decidir

- ~~Licença~~: MIT, decidida pelo Ricardo em 28/10/2026.
- Se este repositório usa o fluxo do harness (`/harness-init`): o Ricardo decide.
