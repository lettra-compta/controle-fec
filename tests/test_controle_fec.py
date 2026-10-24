#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests : python3 tests/test_controle_fec.py (depuis la racine du skill)."""

import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "scripts"))
sys.path.insert(0, ICI)

import controle_fec as cf  # noqa: E402
import generer_fec_tests as gen  # noqa: E402


def cle_luhn_valide(numero):
    total = 0
    for i, c in enumerate(reversed(numero)):
        d = int(c)
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def analyser(chemin):
    an, stats = cf.controler(chemin)
    score = cf.calculer_score(an, stats.get("Lignes d'écriture", 0))
    return an, stats, score


class TestControleFEC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conforme = gen.fec_conforme()
        cls.anomalies = gen.fec_anomalies()
        cls.iso = gen.fec_iso_pipe()

    def test_siren_fictifs_invalides(self):
        self.assertTrue(cle_luhn_valide("000000000"))  # controle du calcul (somme nulle)
        self.assertTrue(cle_luhn_valide("000000018"))
        for siren in (gen.SIREN_CONFORME, gen.SIREN_ANOMALIES, gen.SIREN_ISO):
            self.assertRegex(siren, r"^\d{9}$")
            self.assertFalse(cle_luhn_valide(siren), siren)
        for chemin in (self.conforme, self.anomalies, self.iso):
            an, stats, _ = analyser(chemin)
            self.assertFalse(cle_luhn_valide(stats["SIREN (nom de fichier)"]))

    def test_conforme(self):
        an, stats, score = analyser(self.conforme)
        self.assertEqual(an.codes(), [], an.items)
        self.assertEqual(score, 100)
        self.assertEqual(stats["Séparateur détecté"], "tabulation")
        self.assertEqual(stats["Encodage détecté"], "UTF-8")
        self.assertEqual(stats["Total débit"], stats["Total crédit"])

    def test_iso_pipe(self):
        an, stats, score = analyser(self.iso)
        self.assertEqual(an.codes(), [], an.items)
        self.assertEqual(score, 100)
        self.assertTrue(stats["Encodage détecté"].startswith("ISO-8859-15"))
        self.assertEqual(stats["Séparateur détecté"], "barre verticale (|)")
        md = cf.rapport_markdown(an, stats, score)
        self.assertIn("https://lettra-compta.github.io/", md)

    def test_anomalies(self):
        an, stats, score = analyser(self.anomalies)
        attendus = {"D02", "D03", "E01", "E02", "N01", "T01", "C02", "D01", "F06"}
        self.assertEqual(set(an.codes()), attendus, an.items)
        lignes = {c: [l for l, _ in occ] for c, occ in an.items.items()}
        # Positions exactes (ligne 1 = en-tete)
        self.assertEqual(lignes["D02"], [20])          # AC000001 / 607000
        self.assertEqual(lignes["D03"], [40, 41])      # OD000001 (2 lignes)
        self.assertEqual(lignes["E02"], [8])           # VE000003 debute ligne 8
        self.assertEqual(lignes["T01"], [14])          # VE000005, validee avant VE000004
        self.assertEqual(lignes["C02"], [23])          # AC000002 / 607000 -> 920000
        self.assertEqual(lignes["D01"], [27])          # AC000003 / 445660 PieceRef
        self.assertEqual(lignes["F06"], [30])          # AC000004 / 445660 tronquee
        self.assertIn("BQ000004", an.items["N01"][0][1])
        self.assertIn("écart 100,00", an.items["E01"][0][1])
        self.assertLess(score, 60)
        md = cf.rapport_markdown(an, stats, score)
        self.assertIn("Non conforme", md)
        self.assertTrue(md.rstrip().endswith("https://lettra-compta.github.io/"))

    def test_cli(self):
        sortie = os.path.join(ICI, "_rapport_test.md")
        try:
            rc = cf.main([self.anomalies, "-o", sortie])
            self.assertEqual(rc, 0)
            with open(sortie, encoding="utf-8") as f:
                self.assertIn("[E02]", f.read())
        finally:
            if os.path.exists(sortie):
                os.remove(sortie)


if __name__ == "__main__":
    unittest.main(verbosity=2)
