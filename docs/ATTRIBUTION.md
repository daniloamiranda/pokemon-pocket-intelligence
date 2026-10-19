# Atribuicoes, licencas e limites de uso

> **Licencas:** o CODIGO deste repositorio (scripts, tests, skills) e licenciado sob
> **MIT** — ver `LICENSE` na raiz. Os DADOS derivados de fontes de terceiros
> (Limitless; The Pokemon Company / DeNA / Creatures) permanecem sob os termos dos
> respectivos donos e NAO sao redistribuidos neste repositorio (politica abaixo).

## Propriedade intelectual do jogo

Pokemon e Pokemon TCG Pocket sao marcas da Nintendo / Creatures / GAME FREAK.
Textos e imagens de cartas sao (c) The Pokemon Company, DeNA Co., Ltd. e/ou Creatures, Inc..
**Este projeto nao e produzido, endossado, suportado ou afiliado a nenhum desses titulares.**

Politica do repositorio: **nao redistribuir arte de carta**. Guardamos URLs e metadados
(nome, custo, dano, texto de efeito) para uso funcional, com link para a fonte original.

## Fontes externas

| Fonte | URL | Uso | Licenca/termos | Ultima verificacao |
|---|---|---|---|---|
| Limitless TCG Pocket DB | https://pocket.limitlesstcg.com | Catalogo canonico de cartas | Conteudo (c) TPC/DeNA/Creatures; site nao afiliado | 2026-10-18 |
| Limitless Developer API | https://docs.limitlesstcg.com/developer | Torneios, decklists, matches | Sem chave exceto endpoint /decks; rate limit por header; chave so para projetos publicos | 2026-10-18 |
| TCGdex | https://api.tcgdex.net/v2 | Nomes/traducao (incl. pt-BR) | MIT (projeto comunitario) | 2026-10-18 |
| flibustier/pokemon-tcg-pocket-database | npm/jsDelivr | Raridade/pacotes (secundario) | Dataset comunitario; payload defasado (para em B1a) | 2026-10-18 |
| R4PH1/PTCGP-Data | GitHub | Modelo de schema (ataques/efeitos/evolucoes) | **Sem licenca declarada** — nao usar em massa | 2026-10-18 |

Regra: dado de fonte comunitaria nunca sobrescreve o dado canonico.
