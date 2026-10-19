"""F13+ · TDD: nomes de conjunto promocional poluidos com comentario HTML.

parse_set_metadata no fallback <title> (paginas /cards/P-A e /cards/P-B sem
infobox) capturava o comentario do GTM porque a regex [^(]+ atravessava
</title> ate o primeiro '(' do bloco 'Google tag (gtag.js)'. O INSERT OR
IGNORE do upsert fossilizou o valor errado no catalogo (mesma classe do F7c).

Fix (3 camadas):
  1. strip de comentarios HTML <!--...--> ANTES de qualquer extracao de nome;
  2. fallback <title> delimitado ao ELEMENTO (<title>...</title>), sem vazar;
  3. sufixo de fonte '– Limitless TCG Pocket Database' removido do nome.
Semantica legada preservada: no fallback, corte no primeiro '(' (drop do
codigo do conjunto, ex. 'Genetic Apex (A1) – ...' -> 'Genetic Apex').
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "integrations" / "limitlesstcg-pocket"))

import parser as P  # noqa: E402

# Shape real da pagina /cards/P-A em cache (era F4): sem infobox-heading,
# <title> limpo seguido do snippet GTM com o primeiro '(' do documento.
HTML_PROMO_SET = """<html><head>
<title>Promo-A – Limitless TCG Pocket Database</title>
    <meta name="description" content="All 117 cards from Promo-A in our Pokémon TCG Pocket card database.">
            <!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXX"></script>
</head><body></body></html>"""


class TestF13PlusPromoNames(unittest.TestCase):
    """Nome do conjunto sai LIMPO: sem comentario HTML, sem sufixo da fonte."""

    def test_title_fallback_promo_limpo(self):
        """REGRESSAO F13+: 'Promo-A – ... <!-- Google tag' -> 'Promo-A'."""
        meta = P.parse_set_metadata(HTML_PROMO_SET)
        self.assertEqual("Promo-A", meta["name"])

    def test_title_fallback_corte_parenteses_legado_preservado(self):
        # title de pagina de set COM codigo: corte no '(' continua (drop do
        # codigo), agora dentro do elemento <title> — comentario GTM nao vaza.
        html = ("<html><head><title>Genetic Apex (A1) – Limitless TCG Pocket "
                "Database</title><!-- Google tag (gtag.js) --></head></html>")
        self.assertEqual("Genetic Apex", P.parse_set_metadata(html)["name"])

    def test_comentario_com_parenteses_nao_interfere(self):
        # antes: '(' dentro de comentario truncava/contaminava o nome
        html = ("<html><head><title>Set X – Limitless TCG Pocket Database</title>"
                "<!-- sujeira (qualquer) --></head></html>")
        self.assertEqual("Set X", P.parse_set_metadata(html)["name"])

    def test_infobox_name_tambem_sanitizado(self):
        # caminho primario (infobox) nao pode carregar comentario/sufixo tambem;
        # shape minimo real: infobox-heading seguido de infobox-line com data/contagem
        html = ("<html><div class=\"infobox-heading\">Promo-A – Limitless TCG "
                "Pocket Database <!-- Google tag --></div>"
                "<div class=\"infobox-line\">1st January 2026 • 117 Cards</div></html>")
        meta = P.parse_set_metadata(html)
        self.assertEqual("Promo-A", meta["name"])

    def test_infobox_sem_comentario_nem_sufixo_inalterado(self):
        # set regular via infobox: codigo ALL-CAPS no fim continua sendo removido
        # (legado; codigos com minusculas tipo (B2b) ficam — convencao fosilizada
        # no catalogo, fora do escopo F13+)
        html = ("<html><div class=\"infobox-heading\">Genetic Apex (A1)</div>"
                "<div class=\"infobox-line\">17th July 2025 • 117 Cards</div></html>")
        meta = P.parse_set_metadata(html)
        self.assertEqual("Genetic Apex", meta["name"])
        self.assertEqual("2025-07-17", meta["release_date"])
        self.assertEqual(117, meta["card_count"])


if __name__ == "__main__":
    unittest.main()
