# Próximos passos e decisões

O plugin `speak` nasceu em 28/10/2026 da voz que vivia no ai-harness (versão `ee7bd73` de lá); a troca terminou no mesmo dia. Desenhos: `docs/superpowers/specs/`.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub, com licença MIT; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português, com escolha entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.
- O repositório não usa o fluxo do harness (sem quadro).

## Feito

- Plugin `speak` no catálogo `cc-speaker`, com o comando `/speak`: um painel com listas nativas (ligar, leitura, tamanho, voz, alcance) que fica aberto até Esc, pedidos em palavras e o motor instalado sozinho na primeira sessão.
- Alcance guardado: "só esta sessão" e "todas as sessões" são coisas distintas; todas as sessões apaga as exceções em vez de copiar o valor.
- Pasta de dados na do plugin (`.../plugins/data/speak-cc-speaker`, ou a que o Claude Code der): motor, escolhas e estado juntos, e `claude plugin uninstall` apaga tudo (a menos que use `--keep-data`). As pastas antigas (`~/.local/share/claude-speak` e as outras) se mudam sozinhas, uma de cada vez.
- Mac: peça por sistema em `lib/speak_os.py`; som em fluxo pelo `sounddevice` (com prazo para abrir, escrever e parar) e `afplay` de reserva; microfone lido pelo CoreAudio. O fluxo do GitHub roda os testes no Ubuntu e no macOS (também no Python 3.9 do Mac). Falta o teste num Mac de verdade.
- A linha 🔊 do resumo só é pedida no modo resumo (o padrão); no modo leitura inteira o modelo é avisado de que não deve escrevê-la.
- Fim de sessão corta a fala daquela sessão (`speak stop here`), sem mexer nas outras.
- Instalação do motor visível: progresso na linha de status, no `/speak status` e no menu, com aviso ao fim ou na falha (issue #1).
- Teste de instalação limpa em contêiner (`tests/docker/`).
- Tamanho do resumo (pequeno, médio, grande) e escolha da voz (dora, alex, santa).
- Testes que não tocam a pasta de dados real: um só ajudante de isolamento (`tests/isolation.py`) e um guarda-costas que compara a pasta real antes e depois da bateria.

## Recusado

- Um comando por ação (`/speak-on`, `/speak-off` e outros), pedido pela sessão do smart-platform: recusado pelo Ricardo em 29/10/2026; `/speak on` e os demais já bastam (desenho em `docs/superpowers/specs/2026-10-29-menu-dados-mac-design.md`).

## Pendências

- **Teste no contêiner, modo visual** (`bash tests/docker/instalacao-limpa.sh visual`): a ser feito pelo Ricardo.
- **Mac de verdade**: confirmar som, microfone e achar a sessão (`speak check`). A classe `_CoreAudio` (`lib/speak_os.py`) não tem cobertura de teste e suas constantes foram escritas de memória.
- **Microfone embutido sempre ligado no Mac**: se a escuta da Siri (ou outro programa) deixar a entrada embutida em uso o tempo todo, a fila pode achar que alguém grava e a voz esperar para sempre. A ver no teste do Mac.
- **Ramo do `.part` sem teste**: o caminho em que o arquivo temporário (`<arquivo>.part-<pid>`, no download em `bin/speak` e na cópia entre discos em `lib/speak_paths.py`) é removido depois de um erro no meio não tem teste próprio para cada falha possível.
- **Arquivo de ambiente binário sem teste**: `share_root` (`hooks/speak-start.py`) não é testado com um `CLAUDE_ENV_FILE` que tenha bytes que não são texto.
- **`plugin_version()` duplicado**: existe em `bin/speak` e em `hooks/speak-start.py`; deveria viver em `lib/`.
- **Limpeza única sem trava**: `_drop_copied_fields_once` (`bin/speak`) não toma trava; duas sessões que comecem juntas podem rodá-la ao mesmo tempo (o efeito é o mesmo, mas não há garantia).
- **Corrida de microssegundos na primeira instalação**: a sonda da trava no gancho de começo e a do `speak install` podem se cruzar; o segundo `install` espera e acha tudo instalado, mas dois filhos podem nascer.
- **Módulo e ganchos com pastas diferentes**: com `--plugin-dir` (cópia de desenvolvimento) o módulo do painel e os ganchos podem derivar pastas de dados diferentes.
- **`CLAUDE_PLUGIN_DATA` vence `CLAUDE_SPEAK_DATA`** em `lib/speak_paths.py:25`: se um outro plugin exportar a sua `CLAUDE_PLUGIN_DATA` no mesmo shell, o `speak` usaria a pasta errada; o gancho exporta só a `CLAUDE_SPEAK_DATA` (veja o plano) para não vazar.
- **Folga curta do `test_fim_rapido`** (1,5 s para o gancho de fim de sessão): pode falhar numa máquina muito carregada.
- **Vazamento de threads nos testes**: `synthesize_ahead.<locals>.work` e `StreamPlayer.bounded.<locals>.work` ficam vivas depois de alguns testes.

## Pedidos para depois

- **Filtrar melhor o que se narra.** Exemplo real: na linha de sincronização do pickup a voz leu "HEAD 93a66bd" e o ramo "fix/fila-da-voz". Não narrar códigos de commit (sequências hexadecimais de 7 a 40 caracteres com dígitos), a palavra HEAD, nomes de ramo com barra e separadores como o ponto médio; revisar as outras regras de limpeza com exemplos de respostas reais.
- **Outros narradores** pesquisados em 28/10/2026, para escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- **Voz no estilo do Jarvis**, ideia do Ricardo. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator nem o nome como marca.

## Retirado

- Modo celular (mp3 enviado pelo controle remoto): retirado em 28/10/2026, porque o botão de ler em voz alta do próprio app (celular e web, no controle remoto) cobre o caso.
