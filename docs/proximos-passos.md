# Próximos passos e decisões

O plugin `speak` nasceu em 28/10/2026 da voz que vivia no ai-harness (versão `ee7bd73` de lá); a troca terminou no mesmo dia. Desenhos: `docs/superpowers/specs/`.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub, com licença MIT; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português, com escolha entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.
- O repositório não usa o fluxo do harness (sem quadro).

## Feito

- Plugin `speak` no catálogo `cc-speaker`, com o comando `/speak` e suas caixas de escolha no terminal (ligar, leitura, tamanho, voz, alcance), pedidos em palavras e o motor instalado sozinho na primeira sessão.
- Mac: o código está pronto (peça por sistema em `lib/speak_os.py`, som pelo `sounddevice` com `afplay` de reserva) e o fluxo do GitHub roda os testes no Ubuntu e no macOS. Falta o teste num Mac de verdade.
- Tamanho do resumo (pequeno, médio, grande) e escolha da voz (dora, alex, santa).

## Pendências

- **Vazamento de threads nos testes**: `synthesize_ahead.<locals>.work` e `StreamPlayer.bounded.<locals>.work` ficam vivas depois de alguns testes.
- **Teste no contêiner, modo visual** (`bash tests/docker/instalacao-limpa.sh visual`): a ser feito pelo Ricardo.
- **Mac de verdade**: confirmar som, microfone e achar a sessão (`speak check`).

## Pedidos para depois

- **Filtrar melhor o que se narra.** Exemplo real: na linha de sincronização do pickup a voz leu "HEAD 93a66bd" e o ramo "fix/fila-da-voz". Não narrar códigos de commit (sequências hexadecimais de 7 a 40 caracteres com dígitos), a palavra HEAD, nomes de ramo com barra e separadores como o ponto médio; revisar as outras regras de limpeza com exemplos de respostas reais.
- **Outros narradores** pesquisados em 28/10/2026, para escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- **Voz no estilo do Jarvis**, ideia do Ricardo. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator nem o nome como marca.

## Retirado

- Modo celular (mp3 enviado pelo controle remoto): retirado em 28/10/2026, porque o botão de ler em voz alta do próprio app (celular e web, no controle remoto) cobre o caso.
