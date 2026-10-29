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
Ao sair (exit), o contêiner e o login somem.
TXT
exec docker run -it --rm -v "$REPO":/plugin:ro "$IMAGEM" bash /plugin/tests/docker/dentro-do-conteiner.sh visual
