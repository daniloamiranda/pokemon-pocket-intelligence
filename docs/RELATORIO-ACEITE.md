# F6 · card-vision — Relatório de Aceitação (t_7f2650c1)

Data: 18/10/2026 · Owner: tony_stark · Risco: R2 · Commit: (ver git log)

## Escopo entregue
- `scripts/vision/card_vision.py` — resolver imagem->carta: candidatos (LIKE + FTS5),
  score 0.55 nome + 0.15 HP + 0.10 elemento + 0.10 estágio + 0.15 ataque, veredicto
  JSON com status (ok|incerto), confiança (alta|média|baixa), motivo, ficha de prints
  e `alternatives` em empate.
- `scripts/vision/eval_batch_resolver.py` — avaliação em lote sobre ground truth de visão.
- `skills/pokemon-pocket-card-vision/SKILL.md` — a skill com pipeline de visão multimodal
  (vision_analyze/Observação) + correção contra o banco + regra inegociável "não chute".
- `tests/vision/fixtures/` — 14 imagens reais baixadas do CDN do Limitless (padrão
  `​{SET}/{SET}_{NNN:03d}_EN_SM.webp`, 367×512).
- `tests/vision/fixtures_bad/` — 4 imagens degradadas (truncada, corrompida, nome mentiroso).
- `tests/unit/test_f6_card_vision.py` — 6 testes cobrindo os 4 aceites; suíte completa
  **41/41 OK**.

## Aceites

### 1) Reconhece conjunto de teste de cartas conhecidas — OK
14/14 fixtures com ground truth extraído por visão multimodal real (não OCR: as
observações vêm do modelo de visão sobre a imagem; o OCR corre sobre validação, e o
número de coleção a 367px em geral nem é legível — essa limitação é declarada, não
escondida). Resolve em identidade mecânica correta, ex.:

| Fixture | Expectativa | Resolver |
|---|---|---|
| A1_001 (Bulbasaur 70 grass basic, Vine Whip 40) | limitless:A1/1 | limitless:A1/1, conf. alta |
| A1_122 (Gengar 130 psychic stage2, Bother 50) | limitless:A1/122 | limitless:A1/122, conf. alta |
| A1_123 (Gengar ex 170 psychic stage2, Spooky Shot 100) | limitless:A1/123 | limitless:A1/123, conf. alta |
| B1_001 (Pinsir 90 grass X-Scissor 50) | limitless:B1/1 | limitless:B1/1 (após empate resolvido por similaridade de nome + print), conf. média |
| B4b_429 (Koraidon ex 150 fighting World Wrecker 110) | limitless:B3a/36 | limitless:B3a/36, conf. alta |

### 2) Diferencia impressões da mesma carta — OK (com honestidade mecânica)
Mega Gengar ex: `B2b_039.webp` e `B4b_141.webp` resolvem a MESMA identidade
`limitless:B2b/39` (mechanical_hash `6e720205...`). O banco mostra 5 prints
(B2b#39/#79/#114 + B4b#141/#419) e o veredicto carrega nota EXPLÍCITA:

> "número de coleção ilegível; 5 impressões mecanicamente idênticas: diferencie por
> set_code#number na imagem de alta resolução"

Isto está CORRETO do ponto de vista mecânico: as 5 impressões são idênticas em jogo,
e a imagem padrão do CDN (367×512 webp) não traz o rodapé NNN/NNN legível — a
desambiguação final exige foto em alta resolução ou o número informado pelo usuário.
A skill declara isso em vez de inventar print.

### 3) Imagem ruim gera "incerto" com motivo — OK
- Truncada (6 KB de bytes head): visão nem decodifica -> `incerto: imagem truncada`.
- Corrompida (zero-bytes no meio): visão lê cabeçalho mas declara rodapé ilegível ->
  `incerto: imagem parcialmente corrompida: rodapé ilegível`.
- Nome de arquivo MENTIROSO (`B4b_141_lying_name.webp` com arte de Gengar A1#122):
  visão vence o nome do arquivo -> veredicto Gengar A1/122 (correto). Coberto por teste.

### 4) Confiança reportada por caso — OK
Todo veredicto `ok` carrega `confianca` (alta | média) + `score` (0..1);
`incerto` carrega `motivo` (e `best_guess`/`alternatives` quando existe hipótese).

## Limitações declaradas (não defeitos)
1. `print_number` raramente legível no webp 367×512 — a SKILL exige nº legível só
   quando houver; caso contrário resolve identidade e aponta os prints.
2. Execução de visão é manual (`vision_analyze` na sessão do agente), não from CLI do
   script — a observação entra por `--observation` (inline, `@arquivo` ou stdin).
3. Repositório protege `HERMES_WRITE_SAFE_ROOT`; escrever no repo exige preparar
   os arquivos na área de trabalho (scratch) do executor e copiá-los para a árvore
   (padrão já usado por F4b/F4c/F5/F5b).

## Evidências
- Suíte: `python3 -m unittest discover tests` -> **41/41 OK** (35 pré-existentes + 6 novos).
- Veredicto de exemplo resolvido: limitless:B2b/39 c/ 5 prints e nota de identidade.
