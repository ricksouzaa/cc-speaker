# Próximos passos e decisões

O plugin `speak` nasceu em 28/10/2026 da voz que vivia no ai-harness (versão `ee7bd73` de lá); a troca terminou no mesmo dia. Desenhos: `docs/superpowers/specs/`.

## Decisões do Ricardo (28/10/2026)

- Repositório aberto no GitHub, com licença MIT; público para quem ele escolher compartilhar (amigos e o time do trabalho), sem compromisso com pedidos de terceiros.
- Narração só em português, com escolha entre as vozes masculinas e femininas que o motor tem em português.
- Linux e Mac (um conhecido com Mac instala e testa). Windows fora por agora (há dual boot para testar depois). O que depende do sistema (tocar o som, saber se o microfone grava, achar a sessão e parar processos, travas de arquivo) fica isolado numa peça trocável por sistema. Microfone no Mac: ler pelo sistema de áudio da Apple se algum dispositivo de entrada está em uso. Testes automáticos podem rodar em máquinas Mac do GitHub; som e microfone de verdade, só com o testador.
- O repositório não usa o fluxo do harness (sem quadro).

## Feito

- Plugin `speak` no catálogo `cc-speaker`, com comandos de barra por ação e menus de setas (voz, modo, tamanho, saída).
- Tamanho do resumo (pequeno, médio, grande) e escolha da voz (dora, alex, santa).
- Modo celular (0.2.0): mp3 enviado ao celular pelo controle remoto, sem som no computador. Falta o teste de ponta a ponta com o Ricardo no controle remoto.

## Pedidos para depois

- **Mac**, pela peça trocável por sistema descrita acima.
- **Filtrar melhor o que se narra.** Exemplo real: na linha de sincronização do pickup a voz leu "HEAD 93a66bd" e o ramo "fix/fila-da-voz". Não narrar códigos de commit (sequências hexadecimais de 7 a 40 caracteres com dígitos), a palavra HEAD, nomes de ramo com barra e separadores como o ponto médio; revisar as outras regras de limpeza com exemplos de respostas reais.
- **Outros narradores** pesquisados em 28/10/2026, para escolher o que trazer: uma voz por sessão (do kokoro-tts do voiys); avisos falados durante o trabalho (do claude-voice do adjit).
- **Modo celular sem o modelo**: hoje só o modelo envia arquivo (os ganchos não), o que custa uma volta curta por resposta e não toca sozinho. Estudar alternativas.
- **Voz no estilo do Jarvis**, ideia do Ricardo. Combinado: um estilo inspirado (voz masculina grave e calma, tratamento formal, talvez um leve efeito metálico no áudio), não uma cópia da voz do ator nem o nome como marca.
