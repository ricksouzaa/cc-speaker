# cc-speaker

Plugin `speak` do Claude Code: lê em voz alta, em português do Brasil, as respostas, com o motor local Kokoro. Linux e Mac (o Mac nunca foi testado num Mac de verdade). Projeto solo do Ricardo, público no GitHub.

- **Comece por `docs/proximos-passos.md`**: decisões, o que foi feito, o que foi recusado e as pendências. O que está lá como decidido não se reabre.
- **Não usa o fluxo do harness** (sem quadro, sem `/harness-init`), por decisão do Ricardo.
- **Git e versões**: `.claude/rules/git-workflow.md`. Todo ajuste termina com versão nova publicada (marca, página no GitHub e plugin atualizado), sem esperar pedido.
- **Testes**: `unset CLAUDE_SPEAK_DATA CLAUDE_PLUGIN_DATA; python3 -m unittest discover -s tests` (rodar sempre por `discover`, e com essas variáveis soltas). Também `claude plugin test .` e `claude plugin validate .`.
- **Onde fica cada coisa**: `bin/speak` é o programa; `lib/speak_os.py` isola o que depende do sistema (som, microfone, processos); `lib/speak_paths.py` decide a pasta de dados; `hooks/` tem os ganchos e o módulo do painel; `rules/speak.md` é a regra que o Claude lê para escrever a linha 🔊.
- **Texto**: tudo para o usuário em português do Brasil, com acentos; o CHANGELOG é escrito para quem usa o plugin.
