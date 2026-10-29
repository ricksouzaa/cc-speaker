#!/usr/bin/env bash
# Prova, numa máquina nova (contêiner Ubuntu 24.04), que a instalação automática do motor de voz aparece para a pessoa.
#   bash tests/docker/instalacao-limpa.sh [auto|visual]
# auto (padrão): roda tudo sozinho e sai com 0 (passou) ou 1 (falhou). visual: abre um terminal para ver a tela.
# O repositório entra no contêiner só para leitura (/plugin:ro); nada de ~/.claude nem ~/.config da máquina entra.
set -u
MODO="${1:-auto}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$AQUI/../.." && pwd)"
IMAGEM="cc-speaker-instalacao-limpa"

case "$MODO" in auto | visual) ;; *)
    echo "uso: bash tests/docker/instalacao-limpa.sh [auto|visual]" >&2
    exit 2
    ;;
esac
command -v docker > /dev/null || { echo "FALHOU: docker não encontrado" >&2; exit 1; }

echo "== Montando a imagem $IMAGEM (Ubuntu 24.04, uv, Claude Code)"
docker build -t "$IMAGEM" "$AQUI" || { echo "FALHOU: a imagem não montou" >&2; exit 1; }

if [ "$MODO" = auto ]; then
    echo "== Subindo o contêiner (repositório em /plugin:ro; apagado no fim)"
    docker run --rm -v "$REPO":/plugin:ro "$IMAGEM" bash /plugin/tests/docker/dentro-do-conteiner.sh auto
    code=$?
    if [ "$code" -eq 0 ]; then
        echo "== RESULTADO: PASSOU"
    else
        echo "== RESULTADO: FALHOU (código $code)"
    fi
    exit "$code"
fi

cat << 'TXT'
== Modo visual
O plugin será instalado no contêiner e você cai num terminal comum dentro dele. Então:
  1. rode:  claude
  2. entre na conta (o login vale só dentro deste contêiner);
  3. abra uma sessão nova (ou /reload-plugins): embaixo do campo de texto aparece a linha
     "🔊 Instalando a voz: NN% (X de Y MB)";
  4. espere o aviso "Voz pronta".
Para o plugin ativado no meio da sessão (issue #2), em vez dos passos 3 e 4, e com o plugin ainda não instalado
(rode "claude plugin uninstall speak@cc-speaker" e "claude plugin marketplace remove cc-speaker" antes de abrir o claude):
  a. dentro do claude, já logado e com a sessão aberta: /plugin marketplace add /plugin
  b. /plugin install speak@cc-speaker
  c. sem abrir outra sessão: aparece a linha "Instalando a voz (cerca de 350 MB...)" na conversa, a linha
     "🔊 Instalando a voz: NN% (X de Y MB)" embaixo do campo e, no fim, "Voz pronta";
  d. se faltar o uv, a linha fixa "🔊 Voz não instalada: falta o uv; instale-o e rode /speak install" fica na tela.
Ao sair (exit), o contêiner e o login somem.
TXT
exec docker run -it --rm -v "$REPO":/plugin:ro "$IMAGEM" bash /plugin/tests/docker/dentro-do-conteiner.sh visual
