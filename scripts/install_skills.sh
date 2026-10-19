#!/usr/bin/env bash
# F12 - install_skills.sh: instala as skills do projeto na copia canonica do Hermes
# (/home/hermes/.hermes/skills/) e nos perfis-alvo (/home/hermes/.hermes/profiles/<perfil>/skills/).
#
# FIX DE RAIZ (F12, t_f8f12581 — DEV-02 da F10): a versao anterior herdava
# HERMES_HOME do shell. O shell dos agentes exporta HERMES_HOME apontando para o
# PERFIL (ex.: ~/.hermes/profiles/tony_stark), entao as instalacoes das fases
# F7-F9 foram parar numa ARVORE FANTASMA ~/.hermes/profiles/tony_stark/profiles/
# <perfil>/skills/ — "instalacao ok" na raiz errada, skill invisivel para os
# outros operadores. A raiz canonica agora e FIXA e nunca herdada do ambiente;
# override so pela variavel dedicada HERMES_ROOT_SKILLS (uso: testes/instalacao
# em maquina alternativa). Falha clara (rc=3) se a raiz nao existir.
#
# BUG DE RAIZ (F6b, t_98de7f1b): skill existente APENAS em skills/<nome>/SKILL.md NO
# repositorio NAO e skill instalada — skill_view nao a carrega. Isso aconteceu 2x
# (F3 e F6) e ganhou a variante "instalada na raiz errada" (F7-F9): toda skill nova
# do projeto PRECISA passar por este script no aceite, e o aceite das proximas fases
# so vale com "hash unico verificado: ok".
#
# F12: a verificacao deixou de ser so o SKILL.md e passou a cobrir a ARVORE
# COMPLETA de arquivos de cada skill (ex.: references/, weights.json) — drift em
# arquivo auxiliar tambem e instalacao parcial.
#
# Uso:
#   bash scripts/install_skills.sh                     # instala todas as skills do repo
#   bash scripts/install_skills.sh --verify            # so verifica (hash unico)
#   bash scripts/install_skills.sh --subdir pokemon-pocket-card-vision
#   PERFIS="tony_stark,c3po" bash scripts/install_skills.sh
#   HERMES_ROOT_SKILLS=/tmp/raiz-teste bash scripts/install_skills.sh --verify
#
# Veredicto: o MESMO hash sha256 de CADA arquivo deve existir na copia canonica,
# nos perfis-alvo e no repo — divergencia = instalacao parcial = exit 1.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="$REPO/skills"
# FIX F12: raiz canonica FIXA — NUNCA herdar HERMES_HOME do shell (causa-raiz do
# DEV-02: shell do agente exporta HERMES_HOME do proprio perfil).
HERMES_ROOT="/home/hermes/.hermes"
if [[ -n "${HERMES_ROOT_SKILLS:-}" ]]; then
    HERMES_ROOT="$HERMES_ROOT_SKILLS"   # override explicito e dedicado (nunca HERMES_HOME)
fi
if [[ ! -d "$HERMES_ROOT" ]]; then
    echo "ERRO: raiz canonica do Hermes nao existe: $HERMES_ROOT" >&2
    echo "      Instale o Hermes ou defina HERMES_ROOT_SKILLS=<raiz> explicitamente." >&2
    exit 3
fi
CANON="$HERMES_ROOT/skills"
PERFIS="${PERFIS:-tony_stark,hermione_granger,leia_organa,c3po}"
ONLY_SUBDIR=""
VERIFY_ONLY=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verify) VERIFY_ONLY=1; shift ;;
        --subdir) ONLY_SUBDIR="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | head -30; exit 0 ;;
        *) echo "arg desconhecido: $1" >&2; exit 2 ;;
    esac
done

hash_of() { sha256sum "$1" | cut -d' ' -f1; }

# arquivos de trabalho ignorados na comparacao de arvore (nunca fazem parte da skill)
ignore_file() {
    case "$1" in
        *__pycache__/*|*.pyc|.DS_Store) return 0 ;;
        *) return 1 ;;
    esac
}

# tree_check <srcdir> <destdir> <rotulo>  -> imprime FALHAs, seta FALHA_ARB=1
FALHA_ARB=0
tree_check() {
    local src="${1%/}" dst="${2%/}" label="$3" rel f dh sh
    if [[ ! -d "$dst" ]]; then
        echo "FALHA $label (destino ausente: $dst)"
        FALHA_ARB=1
        return
    fi
    while IFS= read -r -d '' f; do
        rel="${f#"$src"/}"
        ignore_file "$rel" && continue
        sh="$(hash_of "$f")"
        if [[ ! -f "$dst/$rel" ]]; then
            echo "FALHA $label ($rel: ausente no destino)"
            FALHA_ARB=1
        else
            dh="$(hash_of "$dst/$rel")"
            if [[ "$dh" != "$sh" ]]; then
                echo "FALHA $label ($rel: $dh != $sh)"
                FALHA_ARB=1
            fi
        fi
    done < <(find "$src" -type f -print0 | sort -z)
    # arquivo EXTRA no destino (nao existe no repo) tambem e divergencia
    while IFS= read -r -d '' f; do
        rel="${f#"$dst"/}"
        ignore_file "$rel" && continue
        if [[ ! -f "$src/$rel" ]]; then
            echo "FALHA $label ($rel: EXTRA no destino, nao existe no repo)"
            FALHA_ARB=1
        fi
    done < <(find "$dst" -type f -print0 | sort -z)
}

fail=0
n_installed=0
IFS=',' read -ra PERFIS_ARR <<< "$PERFIS"
for p in "${PERFIS_ARR[@]}"; do
    [[ "$p" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "ERRO: perfil invalido: $p" >&2; exit 3; }
done

for srcdir in "$SKILLS_SRC"/*/; do
    skill="$(basename "$srcdir")"
    [[ -n "$ONLY_SUBDIR" && "$skill" != "$ONLY_SUBDIR" ]] && continue
    ref="$srcdir/SKILL.md"
    if [[ ! -f "$ref" ]]; then
        echo "SKIP  $skill (sem SKILL.md)"
        continue
    fi
    ref_hash="$(hash_of "$ref")"

    # 1) copia canonica (cp -R: skills podem ter references/, data/, scripts/)
    dest="$CANON/$skill"
    if [[ $VERIFY_ONLY -eq 0 ]]; then
        mkdir -p "$dest"
        cp -R -f "$srcdir/." "$dest/"
        n_installed=$((n_installed+1))
    fi
    FALHA_ARB=0
    SKILL_FAIL=0
    tree_check "$srcdir" "$dest" "$skill copia canonica"
    if [[ $FALHA_ARB -ne 0 ]]; then fail=1; SKILL_FAIL=1; fi

    # 2) perfis-alvo
    for p in "${PERFIS_ARR[@]}"; do
        pdest="$HERMES_ROOT/profiles/$p/skills/$skill"
        if [[ $VERIFY_ONLY -eq 0 ]]; then
            mkdir -p "$pdest"
            cp -R -f "$srcdir/." "$pdest/"
        fi
        FALHA_ARB=0
        tree_check "$srcdir" "$pdest" "$skill@$p"
        if [[ $FALHA_ARB -ne 0 ]]; then fail=1; SKILL_FAIL=1; fi
    done

    if [[ $SKILL_FAIL -eq 0 ]]; then
        echo "ok    $skill (${ref_hash:0:12}: repo = canonica = ${PERFIS_ARR[*]})"
    else
        echo "DIVERGE $skill (${ref_hash:0:12}: ver FALHAS acima)"
    fi
done

echo
if [[ $n_installed -gt 0 ]]; then
    echo "instaladas $n_installed skill(s)"
fi
if [[ $fail -eq 0 ]]; then
    echo "hash unico verificado: ok (readiness: available)"
    exit 0
fi
echo "VERIFICACAO FALHOU: hashes divergentes ou SKILL.md ausente em algum destino" >&2
exit 1
