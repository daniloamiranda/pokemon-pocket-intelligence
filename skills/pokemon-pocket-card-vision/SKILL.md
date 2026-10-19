---
name: pokemon-pocket-card-vision
description: "Use ao reconhecer cartas do Pokemon TCG Pocket a partir de imagem (foto/print/webp) e resolver contra o catalogo SQLite: pipeline de visao multimodal + FTS5, desambiguacao de impressoes e grau de confianca."
license: MIT
---

# Skill: card-vision (imagem -> carta)

Owner: tony_stark (CTO) · Card: t_7f2650c1 · Risco: R2

## Objetivo
Reconhecer uma carta do Pocket a partir de imagem e resolver contra o catalogo
(`data/pocket.sqlite`): identidade mecanica + impressao (set#number) + ficha + grau de confianca.

## Pipeline (4 estagios)

1. **Observacao (visao multimodal - NAO OCR puro).** Enviar a imagem a um modelo de visao
   pedindo JSON: `{"name", "hp", "element", "stage", "attack", "damage", "print_number", "uncertain"}`.
   - `element`: grass|fire|water|lightning|psychic|fighting|darkness|metal|dragon|colorless
   - `stage`: basic|stage1|stage2|mega_ex
   - `print_number`: so preencher se o numero NNN/NNN estiver LEGIVEL; senao omitir
   - imagem ilegivel/corrompida -> preencher `uncertain` com o motivo e PARAR o pipeline
   - Padrao de imagem catalogada: `limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/{SET}/{SET}_{NNN:03d}_EN_SM.webp` (367x512 — numero de colecao no rodape costuma ficar ILEGIVEL nessa resolucao; nao force)

2. **Resolucao contra catalogo** (`scripts/vision/card_vision.py`, veredicto JSON):
   - candidatos por LIKE em `cards.canonical_name`; fallback FTS5 (`cards_fts`)
   - score = 0.55 similaridade de nome (SequenceMatcher) + 0.15 HP + 0.10 elemento
     + 0.10 estagio + 0.15 ataque (nome >0.85 OU dano exato)
   - limiar: score < 0.60 OU score < 0.70 sem corroboracao de HP nem de ataque
     -> `incerto` "provavelmente nao existe no Pocket" (SEM best_guess sugestivo)
   - empate >= 0.95*max ENTRE identidades fortes (score >= 0.60) -> `incerto`
     "empate entre identidades mecanicas: escolha por arte/moldura/set impresso"
   - nome+HP+ataque conferem mas elemento diverge -> `status ok` com campo
     `conflito_elemento: observado=X catalogo=Y` (nao perde score silenciosamente)

Fixtures de imagem NAO sao versionadas: baixar com
`python3 scripts/vision/fetch_fixtures.py` (docs/ATTRIBUTION.md).

3. **Desambiguacao de impresscao.** Identidade mecanica primeiro (`mechanical_hash`);
   impressao so com numero legivel. Prints da mesma identidade sao MECANICAMENTE
   identicos (ex.: Mega Gengar ex = 1 identidade / 5 prints: B2b 39/79/114, B4b 141/419) —
   a diferenciacao por imagem 367x512 normalmente e impossivel; declare isso em vez de chutar.

4. **Veredicto.** `status` (ok|incerto) + `confianca` (alta|media|baixa) + motivo +
   ficha (`card_id`, prints, resolucao) + `alternatives` quando houver empate.

## Uso

```bash
# observacao inline
python3 scripts/vision/card_vision.py carta.webp \
  --observation '{"name":"Mega Gengar ex","hp":210,"element":"darkness","stage":"mega_ex"}'

# observacao de arquivo
python3 scripts/vision/card_vision.py carta.webp --observation @obs.json
```

## Regras inegociaveis (da F6 do card)

- NAO chutar identificacao com imagem ilegivel: `status=incerto` com motivo, e pedir
  esclarecimento/foto melhor ao humano.
- NAO depender so de OCR: observacao vem do modelo de visao; OCR rushe em validacao de numero.
- Nunca alterar o catalogo por aqui (R2): apenas leitura de `data/pocket.sqlite`.

## Evidencia de aceitacao (experimento F6, 2026-10-18)

- 14 fixtures reais (limitlesstcg CDNs, `tests/vision/fixtures/`) observadas por visao:
  nome/HP/elemento/ataque conferem com o catalogo 14/14.
- Mega Gengar ex: `B2b_039.webp` e `B4b_141.webp` resolvem a MESMA identidade
  `limitless:B2b/39` (mechanical_hash 6e720205...), com nota explicita de que os 5 prints
  sao mecanicamente identicos e diferenciaveis apenas por set#number impresso.
- Fixtures degradadas (`tests/vision/fixtures_bad/`): truncada (nao decodifica),
  corrompida (rodape ilegivel) -> `incerto` com motivo; nome de arquivo mentiroso ->
  visao vence (arquivo `B4b_141_lying_name.webp` resolve como Gengar A1#122, correto).
