# Teste de instalação limpa (contêiner Ubuntu 24.04)

Prova, numa máquina nova, que a instalação automática do motor de voz aparece para a pessoa. Precisa do Docker. O repositório entra no contêiner só para leitura (`/plugin:ro`); nada de `~/.claude` nem `~/.config` da sua máquina entra, e o contêiner é apagado no fim.

- `bash tests/docker/instalacao-limpa.sh auto` (padrão): monta a imagem (Ubuntu 24.04, usuário comum, `uv`, Claude Code), instala o plugin pelo Claude Code, roda o gancho de começo de sessão e confere: aviso de instalação na tela, bytes e porcentagem subindo em `speak status --json`, `install.log` crescendo, motor pronto e `install.progress` removido. Baixa cerca de 350 MB. Sai com 0 (passou) ou 1 (falhou, dizendo o quê). Prazo de 20 minutos.
- `bash tests/docker/instalacao-limpa.sh visual`: a mesma imagem com o plugin já instalado, num terminal (`docker run -it --rm`). Rode `claude`, entre na conta, abra uma sessão nova e veja a linha "🔊 Instalando a voz" embaixo do campo e o aviso "Voz pronta". Ao sair, o contêiner e o login somem.

O roteiro de dentro do contêiner é `tests/docker/dentro-do-conteiner.sh`; não o rode fora dele.
