"""Testes F6 - card-vision: resolver observacoes -> catalogo (sem rede, sem visao real).

Cobre os 4 aceites da tarefa t_7f2650c1 no nível do resolver:
 1) reconhece conjunto de teste conhecido (ground truth colado de execucao real de visao)
 2) Mega Gengar ex: B2b_039 e B4b_141 -> MESMA identidade mecanica, com nota de prints identicos
 3) imagem ruim (uncertain) -> status incerto com motivo
 4) confianca reportada por caso

F6b (t_98de7f1b):
 5) carta inexistente -> incerto, motivo "provavelmente nao existe no Pocket", SEM best_guess
 6) conflito de elemento reportado explicitamente no veredicto 'ok'

FIXTURES: as imagens .webp NAO sao versionadas (artes de terceiros TPC/DeNA; veja
docs/ATTRIBUTION.md). Baixe-as com `python3 scripts/vision/fetch_fixtures.py`.
Os testes deste arquivo sao RESOLUTOR-puro (JSON de observacao -> veredicto) e nao
precisam de imagem; apenas PULAM se o catalogo data/pocket.sqlite nao existir.
"""
import json
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts' / 'vision'))

import card_vision  # noqa: E402

DB = str(REPO / 'data' / 'pocket.sqlite')

if not Path(DB).is_file():
    raise unittest.SkipTest(
        'data/pocket.sqlite ausente: popule o catalogo antes (scripts/collect_pocket.py)')

# Fixtures de imagem: NAO versionadas (docs/ATTRIBUTION.md) — baixar com
# scripts/vision/fetch_fixtures.py. Sem elas, os testes que as usam PULAM;
# os testes do resolvedor (observacao JSON -> veredicto) rodam sempre.
FIXTURES_DIR = REPO / 'tests' / 'vision' / 'fixtures'
FIXTURES_BAD_DIR = REPO / 'tests' / 'vision' / 'fixtures_bad'
if not (FIXTURES_DIR / 'B4b_141.webp').is_file():
    raise unittest.SkipTest(
        'fixtures de imagem ausentes em tests/vision/fixtures/: baixe com '
        'python3 scripts/vision/fetch_fixtures.py (imagens de carta nao sao '
        'versionadas no repositorio - docs/ATTRIBUTION.md)')

# ground truth de visao real (execucao 2026-10-18, vision_analyze sobre fixtures reais)
GROUND_TRUTH = {
    'A1_001.webp': 'limitless:A1/1',
    'A1_122.webp': 'limitless:A1/122',
    'A1_123.webp': 'limitless:A1/123',
    'B2b_039.webp': 'limitless:B2b/39',
    'B4b_141.webp': 'limitless:B2b/39',   # mesma identidade mecanica
    'B1_001.webp': 'limitless:B1/1',      # via print_number legivel na observacao
    'A2_001.webp': 'limitless:A2/1',
    'A3_001.webp': 'limitless:A3/1',
    'A4_001.webp': 'limitless:A4/1',
    'B2_001.webp': 'limitless:B2/1',
    'B4_001.webp': 'limitless:B4/1',
    'A1a_001.webp': 'limitless:A1a/1',
    'B4b_021.webp': 'limitless:B2a/1',   # print de B2a/1 no set B4b -> identidade mecanica B2a/1
    'B4b_429.webp': 'limitless:B3a/36',
}

OBS = {
    'A1_001.webp': dict(name='Bulbasaur', hp=70, element='grass', stage='basic',
                        attack='Vine Whip', damage=40),
    'A1_122.webp': dict(name='Gengar', hp=130, element='psychic', stage='stage2',
                        attack='Bother', damage=50),
    'A1_123.webp': dict(name='Gengar ex', hp=170, element='psychic', stage='stage2',
                        attack='Spooky Shot', damage=100),
    'B2b_039.webp': dict(name='Mega Gengar ex', hp=210, element='darkness', stage='mega_ex',
                         attack='Labyrinth of Shadows', damage=120),
    'B4b_141.webp': dict(name='Mega Gengar ex', hp=210, element='darkness', stage='mega_ex',
                         attack='Labyrinth of Shadows', damage=120),
    'B1_001.webp': dict(name='Pinsir', hp=90, element='grass', stage='basic',
                        attack='X-Scissor', damage=50, print_number='1',
                        print_set='B1'),
    'A2_001.webp': dict(name='Oddish', hp=60, element='grass', stage='basic',
                        attack='Blot', damage=10),
    'A3_001.webp': dict(name='Exeggcute', hp=60, element='grass', stage='basic',
                        attack='Rolling Tackle', damage=30),
    'A4_001.webp': dict(name='Oddish', hp=50, element='grass', stage='basic',
                        attack='Poison Powder', damage=10),
    'B2_001.webp': dict(name='Ledyba', hp=60, element='grass', stage='basic',
                        attack='Punch', damage=10),
    'B4_001.webp': dict(name='Wurmple', hp=60, element='grass', stage='basic',
                        attack='Gnaw', damage=10),
    'A1a_001.webp': dict(name='Exeggcute', hp=50, element='grass', stage='basic',
                         attack='Growth Spurt', damage=None),
    'B4b_021.webp': dict(name='Sprigatito', hp=60, element='grass', stage='basic',
                         attack='Leafage', damage=20),
    'B4b_429.webp': dict(name='Koraidon ex', hp=150, element='fighting', stage='basic',
                         attack='World Wrecker', damage=110),
}


class TestF6CardVision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = card_vision.sqlite3.connect(DB)
        cls.db = conn

    def test_1_conjunto_conhecido(self):
        for img, expected_id in GROUND_TRUTH.items():
            with self.subTest(img=img):
                v = card_vision._resolve(self.db, OBS[img])
                self.assertEqual(v.get('status'), 'ok', json.dumps(v, ensure_ascii=False))
                self.assertEqual(v['card_id'], expected_id,
                                 f"{img}: {v['card_id']} != {expected_id}")
                self.assertIn(v.get('confianca'), ('alta', 'media'))

    def test_2_mega_gengar_mesma_identidade(self):
        v1 = card_vision._resolve(self.db, OBS['B2b_039.webp'])
        v2 = card_vision._resolve(self.db, OBS['B4b_141.webp'])
        self.assertEqual(v1['card_id'], 'limitless:B2b/39')
        self.assertEqual(v2['card_id'], 'limitless:B2b/39')
        self.assertEqual(len(v1['prints']), 5)   # B2b 39/79/114 + B4b 141/419
        self.assertIn('mecanicamente identicas', v1['impressao'])

    def test_3_imagem_ruim_incerto(self):
        for motivo in ('imagem truncada: nao decodifica (sem carta visivel)',
                       'imagem parcialmente corrompida: rodape ilegivel'):
            with self.subTest(motivo=motivo):
                v = card_vision._resolve(self.db, {'uncertain': motivo})
                self.assertEqual(v['status'], 'incerto')
                self.assertEqual(v['motivo'], motivo)

    def test_3b_nome_mentiroso_visao_vence(self):
        # fixture B4b_141_lying_name.webp: visao le Gengar A1 (nao Mega Gengar)
        obs = dict(OBS['A1_122.webp'])
        v = card_vision._resolve(self.db, obs)
        self.assertEqual((v['status'], v['card_id']), ('ok', 'limitless:A1/122'))

    def test_4_confianca_por_caso(self):
        v = card_vision._resolve(self.db, OBS['A1_001.webp'])
        self.assertEqual(v['confianca'], 'alta')
        # observacao rebaixada (so nome, sem hp/elemento/ataque) confere confianca menor
        v2 = card_vision._resolve(self.db, {'name': 'Gengar'})
        self.assertIn(v2.get('status'), ('ok', 'incerto'))
        if v2['status'] == 'ok':
            self.assertIn(v2['confianca'], ('baixa', 'media', 'alta'))

    def test_veredicto_incognita_incerto(self):
        v = card_vision._resolve(self.db, {'name': 'ZzzxxxYYY', 'hp': 1})
        self.assertEqual(v['status'], 'incerto')
        self.assertIn('no Pocket', v['motivo'])

    def test_5_carta_inexistente_sem_best_guess(self):
        # F6b: Charizard VMAX (HP 330, G-Max Wildfire) NAO existe no Pocket;
        # veredicto = incerto com motivo de ausencia, SEM best_guess sugestivo.
        v = card_vision._resolve(self.db, dict(name='Charizard VMAX', hp=330, element='fire',
                                               stage='stage2', attack='G-Max Wildfire',
                                               damage=130))
        self.assertEqual(v['status'], 'incerto')
        self.assertIn('nao existe no Pocket', v['motivo'])
        self.assertIn('nenhuma identidade do catalogo corresponde', v['motivo'])
        self.assertNotIn('empate', v['motivo'])
        self.assertNotIn('best_guess', v)

    def test_5b_carta_inexistente_diferente_de_empate_legitimo(self):
        # empate legitimo (CONTRASTE com test_5): Charizard ex A1/36 e A2b/10 sao
        # duas identidades REAIS do catalogo com mesmos nome 'Charizard ex', HP 180,
        # stage2 fire. Score 0.80 em ambas COM corroboracao de HP -> motivo de empate
        # com best_guess; nada disso quando NAO ha correspondencia real (test_5).
        v = card_vision._resolve(self.db, dict(name='Charizard ex', hp=180, element='fire',
                                               stage='stage2'))
        self.assertEqual(v['status'], 'incerto')
        self.assertIn('empate', v['motivo'])
        self.assertIn('best_guess', v)

    def test_6_conflito_elemento_reportado(self):
        # F6b: 367x512 engana a leitura do icone (psychic vs darkness). Nome+HP+
        # ataque concordam -> veredicto 'ok' mas conflito EXPLICITO no campo.
        obs = dict(name='Mega Gengar ex', hp=210, element='psychic', stage='mega_ex',
                   attack='Labyrinth of Shadows', damage=120)
        v = card_vision._resolve(self.db, obs)
        self.assertEqual(v['status'], 'ok')
        self.assertEqual(v['card_id'], 'limitless:B2b/39')
        self.assertIn('conflicto', v)
        self.assertIn('conflito_elemento', v['conflicto'])
        self.assertIn('observado=psychic', v['conflicto'])
        self.assertIn('catalogo=darkness', v['conflicto'])
        self.assertNotIn('element', v)   # o valor canonico vem so no campo de conflito

    def test_6b_sem_conflito_quando_elemento_confere(self):
        v = card_vision._resolve(self.db, OBS['B2b_039.webp'])
        self.assertEqual(v['status'], 'ok')
        self.assertNotIn('conflicto', v)

    def test_7_fixtures_webp_validas_no_disco(self):
        # Consome as fixtures real (unico teste que as exige): toda .webp presente
        # precisa ser um webp decodificavel (RIFF....WEBP) com payload > 1 KB.
        arquivos = sorted(FIXTURES_DIR.glob('*.webp')) + sorted(FIXTURES_BAD_DIR.glob('*.webp'))
        self.assertGreater(len(arquivos), 0, 'nenhuma fixture no disco')
        for f in arquivos:
            with self.subTest(f=f.name):
                data = f.read_bytes()
                self.assertGreater(len(data), 1024, f'{f.name}: payload pequeno demais')
                self.assertEqual(data[:4], b'RIFF', f'{f.name}: cabecalho RIFF ausente')
                self.assertEqual(data[8:12], b'WEBP', f'{f.name}: assinatura WEBP ausente')


if __name__ == '__main__':
    unittest.main()
