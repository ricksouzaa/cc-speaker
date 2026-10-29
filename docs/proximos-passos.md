# Próximos passos e decisões

O plugin `speak` nasceu em 28/10/2026 da voz que vivia no ai-harness (versão `ee7bd73` de lá); a troca terminou no mesmo dia. Desenhos: `docs/superpowers/specs/`.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub, com licença MIT; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português, com escolha entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.
- O repositório não usa o fluxo do harness (sem quadro).

## Decisões de 29/10/2026 que valem daqui em diante

- **Menu do `/speak`:** painel com uma lista nativa (`Select`) por linha e um botão Fechar, aberto com o foco (`$.ui.open({ focus: true, closeOnEscape: true })`). Recusados: o `Client` desenhado à mão (só recebe teclas depois de um clique, o Esc nunca chega e não abre no VS Code) e a caixa de pergunta `$.ui.ask` (vira um assistente de perguntas, sempre com a opção "Other"). Navegar com Tab é limite do Claude Code, aceito. O lugar do painel é do Claude Code: ao lado da conversa em tela cheia com 110 colunas ou mais, acima do campo nos outros casos.
- **Sessão do `speak`:** a chave vem do processo `claude` ancestral (`<pid>-<início>`), não do `session_id` do Claude Code; o gancho de fim de sessão a acha do mesmo jeito. `SessionEnd` sem filtro de motivo, então `/clear` e `resume` também cortam a fala da conversa que sai.
- **Instalação do motor:** a regra do início automático vive só em `speak autoinstall`, chamado pelo gancho de começo e pelo módulo (ao ativar o plugin no meio da sessão, o Claude Code roda o módulo, mas não o gancho `SessionStart` de comando). A trava `state/install.lock` fica dentro do `speak install`; o progresso só vale com ela presa. Uma falha não tenta de novo sozinha na mesma versão do plugin.
- **Pasta de dados no shell:** o gancho de começo exporta `CLAUDE_SPEAK_DATA`, nunca `CLAUDE_PLUGIN_DATA`, que outros plugins leriam como a pasta deles.
- **Microfone no Mac:** a conta ignora a saída padrão e a saída do sistema, para o próprio som não parecer gravação. Limite: ditar no microfone do mesmo aparelho em que a voz toca não corta a fala.
- **Opção do microfone:** `wait`, `play` e `auto`. O `auto` volta a `wait` quando o microfone passa de ocupado para livre, visto na espera pela vez, na vigia da fala e no gancho de mensagem nova (`speak _mictick`), sem processo novo em segundo plano. Limite: sem fala e sem mensagem nova, a volta espera a próxima.
- **Versão e envio:** todo ajuste sobe a versão e é enviado na hora (`.claude/rules/git-workflow.md`).

## Feito

- Plugin `speak` no catálogo `cc-speaker`, com o comando `/speak`: um painel com listas nativas (ligar, leitura, tamanho, voz, alcance) que fica aberto até Esc, pedidos em palavras e o motor instalado sozinho na primeira sessão.
- Alcance guardado: "só esta sessão" e "todas as sessões" são coisas distintas; todas as sessões apaga as exceções em vez de copiar o valor.
- Pasta de dados na do plugin (`.../plugins/data/speak-cc-speaker`, ou a que o Claude Code der): motor, escolhas e estado juntos, e `claude plugin uninstall` apaga tudo (a menos que use `--keep-data`). As pastas antigas (`~/.local/share/claude-speak` e as outras) se mudam sozinhas, uma de cada vez.
- Mac: peça por sistema em `lib/speak_os.py`; som em fluxo pelo `sounddevice` (com prazo para abrir, escrever e parar) e `afplay` de reserva; microfone lido pelo CoreAudio. O fluxo do GitHub roda os testes no Ubuntu e no macOS (também no Python 3.9 do Mac). Falta o teste num Mac de verdade.
- A linha 🔊 do resumo só é pedida no modo resumo (o padrão); no modo leitura inteira o modelo é avisado de que não deve escrevê-la.
- Fim de sessão corta a fala daquela sessão (`speak stop here`), sem mexer nas outras.
- Instalação do motor visível: progresso na linha de status, no `/speak status` e no menu, com aviso ao fim ou na falha (issue #1).
- Teste de instalação limpa em contêiner (`tests/docker/`).
- Plugin ativado no meio da sessão instala o motor ali mesmo, com aviso na conversa e progresso (issue #2, testada pelo Ricardo numa máquina limpa).
- Opção do microfone (espera, toca, toca nesta reunião), no menu, por escrito e em palavras.
- README reorganizado em tabelas, com os padrões de cada opção.
- Tamanho do resumo (pequeno, médio, grande) e escolha da voz (dora, alex, santa).
- Filtro do que se narra: a voz não lê nomes de ramo, códigos de commit, HEAD nem código entre crases com hífen, sublinhado ou número (0.7.4).
- Testes que não tocam a pasta de dados real: um só ajudante de isolamento (`tests/isolation.py`) e um guarda-costas que compara a pasta real antes e depois da bateria.

## Recusado

- Um comando por ação (`/speak-on`, `/speak-off` e outros), pedido pela sessão do smart-platform: recusado pelo Ricardo em 29/10/2026; `/speak on` e os demais já bastam.

## Pendências

- **Mac de verdade**: confirmar som, microfone e achar a sessão (`speak check`). A classe `_CoreAudio` (`lib/speak_os.py`) não tem cobertura de teste e suas constantes foram escritas de memória.
- **Microfone embutido sempre ligado no Mac**: se a escuta da Siri (ou outro programa) deixar a entrada embutida em uso o tempo todo, a fila pode achar que alguém grava e a voz esperar para sempre. A ver no teste do Mac.
- **Ramo do `.part` sem teste**: o caminho em que o arquivo temporário (`<arquivo>.part-<pid>`, no download em `bin/speak` e na cópia entre discos em `lib/speak_paths.py`) é removido depois de um erro no meio não tem teste próprio para cada falha possível.
- **Arquivo de ambiente binário sem teste**: `share_root` (`hooks/speak-start.py`) não é testado com um `CLAUDE_ENV_FILE` que tenha bytes que não são texto.
- **`plugin_version()` duplicado**: existe em `bin/speak` e em `hooks/speak-start.py`; deveria viver em `lib/`.
- **Limpeza única sem trava**: `_drop_copied_fields_once` (`bin/speak`) não toma trava; duas sessões que comecem juntas podem rodá-la ao mesmo tempo (o efeito é o mesmo, mas não há garantia).
- **Aviso de instalação repetido**: numa corrida rara em que o módulo e o gancho de começo chamam o `speak autoinstall` no mesmo instante, a linha "Instalando a voz" pode aparecer duas vezes.
- **Módulo e ganchos com pastas diferentes**: com `--plugin-dir` (cópia de desenvolvimento) o módulo do painel e os ganchos podem derivar pastas de dados diferentes.
- **`CLAUDE_PLUGIN_DATA` vence `CLAUDE_SPEAK_DATA`** em `lib/speak_paths.py:25`: se um outro plugin exportar a sua `CLAUDE_PLUGIN_DATA` no mesmo shell, o `speak` usaria a pasta errada; o gancho exporta só a `CLAUDE_SPEAK_DATA` (veja o plano) para não vazar.
- **Folga curta do `test_fim_rapido`** (1,5 s para o gancho de fim de sessão): pode falhar numa máquina muito carregada.
- **Vazamento de threads nos testes**: `synthesize_ahead.<locals>.work` e `StreamPlayer.bounded.<locals>.work` ficam vivas depois de alguns testes.

## Pedidos para depois

- **Outros narradores** pesquisados em 28/10/2026, para escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- **Voz no estilo do Jarvis**, ideia do Ricardo. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator nem o nome como marca.

## Retirado

- Modo celular (mp3 enviado pelo controle remoto): retirado em 28/10/2026, porque o botão de ler em voz alta do próprio app (celular e web, no controle remoto) cobre o caso.
