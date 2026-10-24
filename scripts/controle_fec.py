#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_fec.py - Controle de conformite de format d'un Fichier des Ecritures
Comptables (FEC) francais.

References publiques :
  - Livre des procedures fiscales, article L47 A et article A47 A-1
  - Notice / description technique du FEC publiee par la DGFiP
  - Plan comptable general (PCG), classes de comptes 1 a 7

Bibliotheque standard Python uniquement (3.8+). Licence MIT.

Usage :
  python3 controle_fec.py FICHIER_FEC [-o rapport.md] [--json resultat.json]
                          [--cloture AAAAMMJJ] [--max-lignes 20]
"""

import argparse
import json
import math
import os
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

VERSION = "1.0.0"

# --------------------------------------------------------------------------
# Referentiel (article A47 A-1, VII 1 et 2)
# --------------------------------------------------------------------------

COLONNES_DC = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
    "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate",
    "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate",
    "Montantdevise", "Idevise",
]
# Variante Montant / Sens (champs 12 et 13 remplaces)
COLONNES_MS = COLONNES_DC[:11] + ["Montant", "Sens"] + COLONNES_DC[13:]

OBLIGATOIRES = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
    "CompteLib", "PieceRef", "PieceDate", "EcritureLib", "ValidDate",
]
CHAMPS_DATE_OBLIG = ["EcritureDate", "PieceDate", "ValidDate"]
CHAMPS_DATE_FACULT = ["DateLet"]

GRAVITES = ["Critique", "Majeure", "Mineure", "Information"]
POIDS = {"Critique": 25, "Majeure": 10, "Mineure": 3, "Information": 0}

# Catalogue des regles : code -> (gravite, titre, explication)
REGLES = OrderedDict([
    ("F01", ("Critique", "Fichier vide ou illisible",
             "Le fichier ne contient aucune ligne exploitable.")),
    ("F02", ("Critique", "Séparateur non reconnu",
             "Ni tabulation ni barre verticale (|) détectée dans l'en-tête.")),
    ("F03", ("Critique", "Nombre de colonnes de l'en-tête différent de 18",
             "L'article A47 A-1 impose 18 champs, dans un ordre fixe.")),
    ("F04", ("Critique", "Libellé ou ordre de colonne non conforme",
             "Les noms de champs de la première ligne doivent reprendre exactement ceux de l'article A47 A-1, dans l'ordre.")),
    ("F05", ("Mineure", "Casse ou espaces des libellés de colonnes",
             "Le libellé est reconnu mais ne respecte pas la graphie exacte de la norme.")),
    ("F06", ("Majeure", "Nombre de champs incorrect sur une ligne",
             "La ligne ne comporte pas le même nombre de champs que l'en-tête (séparateur parasite dans un libellé, champ manquant).")),
    ("F07", ("Mineure", "Marque d'ordre des octets (BOM) en début de fichier",
             "Accepté par la plupart des outils mais source de rejet du premier libellé de colonne par certains.")),
    ("F08", ("Mineure", "Nom de fichier non conforme",
             "Le nom attendu est SirenFECAAAAMMJJ (SIREN sur 9 chiffres, puis FEC, puis date de clôture).")),
    ("F09", ("Mineure", "Lignes vides dans le fichier",
             "Des lignes vides ont été ignorées.")),
    ("D01", ("Majeure", "Champ obligatoire vide",
             "Ce champ ne peut pas être vide selon l'article A47 A-1.")),
    ("D02", ("Majeure", "Date invalide (format AAAAMMJJ attendu)",
             "Les dates doivent être au format AAAAMMJJ sans séparateur et correspondre à une date réelle.")),
    ("D03", ("Majeure", "Montant invalide",
             "Les montants doivent être numériques, virgule décimale, sans séparateur de milliers ; le signe est admis en premier ou dernier caractère.")),
    ("D04", ("Mineure", "Point utilisé comme séparateur décimal",
             "La norme impose la virgule comme séparateur décimal. Le montant a été interprété malgré tout.")),
    ("D05", ("Majeure", "Champ Sens invalide",
             "Dans la variante Montant/Sens, Sens doit valoir D ou C, ou +1 ou -1.")),
    ("D06", ("Mineure", "Débit et crédit renseignés sur la même ligne",
             "Une ligne d'écriture porte normalement un montant soit au débit, soit au crédit.")),
    ("D07", ("Information", "Montants négatifs",
             "Admis par la norme (montant signé) mais à vérifier : une contrepassation s'inscrit en principe dans le sens opposé.")),
    ("D08", ("Mineure", "Ligne à montant nul",
             "Débit et crédit nuls sur la ligne.")),
    ("D09", ("Majeure", "Devise renseignée sans montant en devise (ou inversement)",
             "Montantdevise et Idevise doivent être renseignés ensemble.")),
    ("D10", ("Mineure", "Date de lettrage sans code de lettrage (ou inversement)",
             "EcritureLet et DateLet vont de pair.")),
    ("C01", ("Majeure", "Numéro de compte non conforme au PCG",
             "Les trois premiers caractères de CompteNum doivent être numériques (article A47 A-1, VII 1).")),
    ("C02", ("Majeure", "Compte hors des classes 1 à 7 du PCG",
             "Seuls les comptes des classes 1 à 7 (bilan et gestion) sont attendus dans un FEC. Les classes 8 (comptes spéciaux) et 9 (analytique) n'y ont pas leur place.")),
    ("C03", ("Mineure", "Même numéro de compte avec plusieurs libellés",
             "Un numéro de compte devrait porter un libellé unique sur l'exercice.")),
    ("E01", ("Critique", "Déséquilibre global débit / crédit",
             "Le total des débits doit égaler le total des crédits.")),
    ("E02", ("Critique", "Écriture déséquilibrée",
             "Pour un même couple JournalCode + EcritureNum, le total des débits doit égaler le total des crédits.")),
    ("E03", ("Majeure", "Dates d'écriture différentes au sein d'une même écriture",
             "Toutes les lignes d'une écriture doivent porter la même EcritureDate.")),
    ("E04", ("Mineure", "Écriture fractionnée dans le fichier",
             "Les lignes d'une même écriture ne sont pas contiguës.")),
    ("E05", ("Mineure", "Écriture à une seule ligne",
             "Une écriture comptable mouvemente au moins deux comptes.")),
    ("T01", ("Majeure", "Chronologie des dates de validation non respectée",
             "Dans un journal, les écritures doivent être validées dans l'ordre de leur numérotation : une date de validation antérieure à celle de l'écriture précédente signale une rupture de chronologie.")),
    ("T02", ("Mineure", "Date de validation antérieure à la date d'écriture",
             "ValidDate est antérieure à EcritureDate.")),
    ("T03", ("Majeure", "Date d'écriture postérieure à la date de clôture",
             "EcritureDate est postérieure à la date de clôture de l'exercice.")),
    ("T04", ("Mineure", "Période couverte supérieure à 24 mois",
             "L'écart entre la première et la dernière EcritureDate dépasse 24 mois.")),
    ("N01", ("Majeure", "Trous dans la numérotation des écritures",
             "Dans un journal, la numérotation des écritures doit être continue et sans rupture.")),
    ("N02", ("Majeure", "Numéro d'écriture réutilisé à des dates différentes",
             "Un même EcritureNum est employé pour des écritures distinctes dans le même journal.")),
    ("N03", ("Mineure", "Numérotation non exploitable pour le contrôle de continuité",
             "Le numéro d'écriture ne se termine pas par une partie numérique ; la continuité n'a pas pu être vérifiée.")),
    ("J01", ("Mineure", "Code journal avec plusieurs libellés",
             "Un code journal devrait porter un libellé unique.")),
])


# --------------------------------------------------------------------------
# Collecte des anomalies
# --------------------------------------------------------------------------

class Anomalies:
    def __init__(self):
        self.items = OrderedDict()  # code -> list of (ligne, detail)

    def add(self, code, ligne=None, detail=""):
        self.items.setdefault(code, []).append((ligne, detail))

    def codes(self):
        return list(self.items.keys())


# --------------------------------------------------------------------------
# Lecture du fichier
# --------------------------------------------------------------------------

def decoder(octets):
    """Retourne (texte, encodage, bom)."""
    bom = False
    if octets.startswith(b"\xef\xbb\xbf"):
        bom = True
        octets = octets[3:]
    try:
        return octets.decode("utf-8"), "UTF-8", bom
    except UnicodeDecodeError:
        pass
    # ISO-8859-15 decode toujours ; on signale les octets 0x80-0x9F (Windows-1252)
    texte = octets.decode("iso-8859-15")
    if any(0x80 <= b <= 0x9F for b in octets):
        return texte, "ISO-8859-15 (octets 0x80-0x9F présents : probable Windows-1252)", bom
    return texte, "ISO-8859-15", bom


def detecter_separateur(entete):
    tab, pipe = entete.count("\t"), entete.count("|")
    if tab == 0 and pipe == 0:
        return None
    return "\t" if tab >= pipe else "|"


def norm(nom):
    return re.sub(r"\s+", "", nom).lower()


# --------------------------------------------------------------------------
# Parsing des valeurs
# --------------------------------------------------------------------------

RE_MONTANT = re.compile(r"^([+-]?)(\d+)(?:([,.])(\d+))?([+-]?)$")


def parse_montant(brut):
    """Retourne (Decimal ou None, point_decimal: bool, erreur: str|None)."""
    s = brut.strip()
    if s == "":
        return Decimal(0), False, None
    m = RE_MONTANT.match(s)
    if not m:
        return None, False, "valeur '%s'" % brut
    sig_g, ent, sep, dec, sig_d = m.groups()
    if sig_g and sig_d:
        return None, False, "double signe '%s'" % brut
    signe = sig_g or sig_d
    txt = ent + ("." + dec if dec else "")
    try:
        v = Decimal(txt)
    except InvalidOperation:
        return None, False, "valeur '%s'" % brut
    if signe == "-":
        v = -v
    return v, sep == ".", None


def parse_date(brut):
    s = brut.strip()
    if not re.fullmatch(r"\d{8}", s):
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


RE_NUM = re.compile(r"^(.*?)(\d+)$")


def split_num(num):
    m = RE_NUM.match(num.strip())
    if not m:
        return None
    return m.group(1), int(m.group(2)), len(m.group(2))


# --------------------------------------------------------------------------
# Controle principal
# --------------------------------------------------------------------------

def controler(chemin, cloture=None):
    an = Anomalies()
    stats = OrderedDict()
    nom_fichier = os.path.basename(chemin)
    stats["Fichier"] = nom_fichier

    with open(chemin, "rb") as f:
        octets = f.read()
    texte, encodage, bom = decoder(octets)
    stats["Encodage détecté"] = encodage
    if bom:
        an.add("F07", 1, "BOM UTF-8 présent")

    # Nom de fichier : SirenFECAAAAMMJJ
    base = os.path.splitext(nom_fichier)[0]
    m_nom = re.fullmatch(r"(\d{9})FEC(\d{8})", base, flags=re.IGNORECASE)
    if m_nom:
        stats["SIREN (nom de fichier)"] = m_nom.group(1)
        d = parse_date(m_nom.group(2))
        if d is None:
            an.add("F08", None, "date de clôture '%s' invalide" % m_nom.group(2))
        elif cloture is None:
            cloture = d
    else:
        an.add("F08", None, "nom reçu : '%s'" % nom_fichier)
    if cloture:
        stats["Date de clôture retenue"] = cloture.strftime("%d/%m/%Y")

    lignes = texte.splitlines()
    if not lignes or not lignes[0].strip():
        an.add("F01", 1, "première ligne vide")
        return an, stats

    entete_brut = lignes[0]
    sep = detecter_separateur(entete_brut)
    if sep is None:
        an.add("F02", 1, "en-tête : '%s'" % entete_brut[:80])
        return an, stats
    stats["Séparateur détecté"] = "tabulation" if sep == "\t" else "barre verticale (|)"

    entete = [c.strip() for c in entete_brut.split(sep)]
    # tolerance : separateur final en fin de ligne
    if entete and entete[-1] == "" and len(entete) == 19:
        entete = entete[:-1]
        sep_final = True
    else:
        sep_final = False

    # Variante Montant/Sens ?
    variante_ms = len(entete) > 12 and norm(entete[11]) == "montant" and norm(entete[12]) == "sens"
    reference = COLONNES_MS if variante_ms else COLONNES_DC
    stats["Variante"] = "Montant / Sens" if variante_ms else "Débit / Crédit"

    if len(entete) != 18:
        an.add("F03", 1, "%d colonnes trouvées" % len(entete))
    for i, attendu in enumerate(reference):
        if i >= len(entete):
            an.add("F04", 1, "colonne %d '%s' absente" % (i + 1, attendu))
            continue
        recu = entete[i]
        if recu == attendu:
            continue
        if norm(recu) == norm(attendu):
            an.add("F05", 1, "colonne %d : '%s' au lieu de '%s'" % (i + 1, recu, attendu))
        else:
            an.add("F04", 1, "colonne %d : '%s' au lieu de '%s'" % (i + 1, recu, attendu))
    for i in range(len(reference), len(entete)):
        an.add("F04", 1, "colonne supplémentaire %d : '%s'" % (i + 1, entete[i]))

    # Index des colonnes par nom normalise (pour poursuivre le controle
    # meme si l'ordre est faux)
    idx = {}
    for i, c in enumerate(entete):
        idx.setdefault(norm(c), i)
    manquantes = [c for c in reference if norm(c) not in idx]
    if manquantes:
        stats["Colonnes introuvables"] = ", ".join(manquantes)

    def champ(vals, nom):
        i = idx.get(norm(nom))
        if i is None or i >= len(vals):
            return ""
        return vals[i].strip()

    # ---------------- Lecture ligne a ligne ----------------
    tot_d = Decimal(0)
    tot_c = Decimal(0)
    ecritures = OrderedDict()  # (journal, num) -> dict
    comptes_lib = defaultdict(set)
    journaux_lib = defaultdict(set)
    nb_lignes = 0
    vides = []
    dates_ecr = []
    precedente_cle = None
    cles_vues = set()

    for no, ligne in enumerate(lignes[1:], start=2):
        if ligne.strip() == "":
            vides.append(no)
            continue
        nb_lignes += 1
        vals = ligne.split(sep)
        if sep_final and len(vals) == len(entete) + 1 and vals[-1].strip() == "":
            vals = vals[:-1]
        if len(vals) != len(entete):
            an.add("F06", no, "%d champs au lieu de %d" % (len(vals), len(entete)))

        # Champs obligatoires
        for nom in OBLIGATOIRES:
            if norm(nom) in idx and champ(vals, nom) == "":
                an.add("D01", no, nom)
        if variante_ms:
            for nom in ("Montant", "Sens"):
                if norm(nom) in idx and champ(vals, nom) == "":
                    an.add("D01", no, nom)
        else:
            for nom in ("Debit", "Credit"):
                if norm(nom) in idx and champ(vals, nom) == "":
                    an.add("D01", no, nom + " (mettre 0,00 si nul)")

        # Dates
        d_vals = {}
        for nom in CHAMPS_DATE_OBLIG + CHAMPS_DATE_FACULT:
            v = champ(vals, nom)
            if v == "":
                d_vals[nom] = None
                continue
            d = parse_date(v)
            if d is None:
                an.add("D02", no, "%s = '%s'" % (nom, v))
            d_vals[nom] = d

        # Montants
        debit = credit = Decimal(0)
        montant_ok = True
        if variante_ms:
            v, point, err = parse_montant(champ(vals, "Montant"))
            if err:
                an.add("D03", no, "Montant : " + err)
                montant_ok = False
            else:
                if point:
                    an.add("D04", no, "Montant = '%s'" % champ(vals, "Montant"))
                sens = champ(vals, "Sens").upper()
                if sens in ("D", "+1"):
                    debit = v
                elif sens in ("C", "-1"):
                    credit = v
                else:
                    if sens != "":
                        an.add("D05", no, "Sens = '%s'" % champ(vals, "Sens"))
                    montant_ok = False
        else:
            for nom in ("Debit", "Credit"):
                brut = champ(vals, nom)
                v, point, err = parse_montant(brut)
                if err:
                    an.add("D03", no, "%s : %s" % (nom, err))
                    montant_ok = False
                    continue
                if point:
                    an.add("D04", no, "%s = '%s'" % (nom, brut))
                if nom == "Debit":
                    debit = v
                else:
                    credit = v
            if montant_ok and debit != 0 and credit != 0:
                an.add("D06", no, "Débit %s / Crédit %s" % (debit, credit))
        if montant_ok:
            if debit < 0 or credit < 0:
                an.add("D07", no, "Débit %s / Crédit %s" % (debit, credit))
            if debit == 0 and credit == 0:
                an.add("D08", no, "")
            tot_d += debit
            tot_c += credit

        # Devise
        md, idv = champ(vals, "Montantdevise"), champ(vals, "Idevise")
        if md != "":
            v, _, err = parse_montant(md)
            if err:
                an.add("D03", no, "Montantdevise : " + err)
            elif v != 0 and idv == "":
                an.add("D09", no, "Montantdevise '%s' sans Idevise" % md)
        if idv != "" and md == "":
            an.add("D09", no, "Idevise '%s' sans Montantdevise" % idv)

        # Lettrage
        let, dlet = champ(vals, "EcritureLet"), champ(vals, "DateLet")
        if (let == "") != (dlet == ""):
            an.add("D10", no, "EcritureLet '%s' / DateLet '%s'" % (let, dlet))

        # Comptes
        compte = champ(vals, "CompteNum")
        if compte:
            if not re.fullmatch(r"\d{3}", compte[:3]):
                an.add("C01", no, "CompteNum = '%s'" % compte)
            elif compte[0] not in "1234567":
                an.add("C02", no, "CompteNum = '%s' (classe %s)" % (compte, compte[0]))
            lib = champ(vals, "CompteLib")
            if lib:
                comptes_lib[compte].add(lib)

        jc, jl = champ(vals, "JournalCode"), champ(vals, "JournalLib")
        if jc and jl:
            journaux_lib[jc].add(jl)

        # Regroupement par ecriture
        num = champ(vals, "EcritureNum")
        if num:
            cle = (jc, num)
            e = ecritures.get(cle)
            if e is None:
                e = {"lignes": [], "d": Decimal(0), "c": Decimal(0),
                     "dates": set(), "valid": [], "première": no}
                ecritures[cle] = e
            elif cle != precedente_cle and cle in cles_vues:
                an.add("E04", no, "%s / %s (debut ligne %d)" % (jc, num, e["première"]))
            cles_vues.add(cle)
            precedente_cle = cle
            e["lignes"].append(no)
            if montant_ok:
                e["d"] += debit
                e["c"] += credit
            if d_vals.get("EcritureDate"):
                e["dates"].add(d_vals["EcritureDate"])
            if d_vals.get("ValidDate"):
                e["valid"].append(d_vals["ValidDate"])
        if d_vals.get("EcritureDate"):
            dates_ecr.append(d_vals["EcritureDate"])
            if cloture and d_vals["EcritureDate"] > cloture:
                an.add("T03", no, "EcritureDate %s > clôture %s" % (
                    d_vals["EcritureDate"].strftime("%Y%m%d"), cloture.strftime("%Y%m%d")))
        if d_vals.get("ValidDate") and d_vals.get("EcritureDate") \
                and d_vals["ValidDate"] < d_vals["EcritureDate"]:
            an.add("T02", no, "ValidDate %s < EcritureDate %s" % (
                d_vals["ValidDate"].strftime("%Y%m%d"),
                d_vals["EcritureDate"].strftime("%Y%m%d")))

    if vides:
        for v in vides:
            an.add("F09", v, "")

    stats["Lignes d'écriture"] = nb_lignes
    stats["Écritures (JournalCode + EcritureNum)"] = len(ecritures)
    stats["Journaux"] = len({k[0] for k in ecritures})
    stats["Total débit"] = fmt(tot_d)
    stats["Total crédit"] = fmt(tot_c)
    if dates_ecr:
        stats["Période couverte (EcritureDate)"] = "%s au %s" % (
            min(dates_ecr).strftime("%d/%m/%Y"), max(dates_ecr).strftime("%d/%m/%Y"))
        if (max(dates_ecr) - min(dates_ecr)).days > 731:
            an.add("T04", None, stats["Période couverte (EcritureDate)"])

    # ---------------- Controles de synthese ----------------
    if tot_d != tot_c:
        an.add("E01", None, "Débit %s - Crédit %s = écart %s" % (fmt(tot_d), fmt(tot_c), fmt(tot_d - tot_c)))

    for (jc, num), e in ecritures.items():
        ref = lignes_ref(e["lignes"])
        if e["d"] != e["c"]:
            an.add("E02", e["première"], "%s / %s : débit %s, crédit %s, écart %s (lignes %s)" % (
                jc, num, fmt(e["d"]), fmt(e["c"]), fmt(e["d"] - e["c"]), ref))
        if len(e["dates"]) > 1:
            an.add("E03", e["première"], "%s / %s : %s" % (
                jc, num, ", ".join(sorted(d.strftime("%Y%m%d") for d in e["dates"]))))
        if len(e["lignes"]) == 1:
            an.add("E05", e["première"], "%s / %s" % (jc, num))

    # Numerotation et chronologie par journal
    par_journal = defaultdict(list)
    for (jc, num), e in ecritures.items():
        par_journal[jc].append((num, e))
    for jc, liste in par_journal.items():
        numeriques = []
        for num, e in liste:
            sp = split_num(num)
            if sp is None:
                an.add("N03", e["première"], "%s / '%s'" % (jc, num))
            else:
                numeriques.append((sp, num, e))
        # Doublons a dates differentes : meme cle mais plusieurs dates deja en E03 ;
        # ici on detecte la reutilisation via E04 + dates distinctes
        for num, e in liste:
            if len(e["dates"]) > 1 and len(lignes_blocs(e["lignes"])) > 1:
                an.add("N02", e["première"], "%s / %s" % (jc, num))
        # Trous par prefixe
        par_prefixe = defaultdict(list)
        largeurs = {}
        for (prefixe, n, larg), num, e in numeriques:
            par_prefixe[prefixe].append(n)
            largeurs[prefixe] = max(largeurs.get(prefixe, 0), larg)
        for prefixe, ns in par_prefixe.items():
            w = largeurs[prefixe]
            s = sorted(set(ns))
            manquants = []
            for a, b in zip(s, s[1:]):
                if b - a > 1:
                    manquants.append((a + 1, b - 1))
            if manquants:
                desc = ", ".join(
                    (prefixe + str(a).zfill(w)) if a == b
                    else (prefixe + str(a).zfill(w) + " à " + prefixe + str(b).zfill(w))
                    for a, b in manquants[:15])
                nb = sum(b - a + 1 for a, b in manquants)
                if len(manquants) > 15:
                    desc += ", ..."
                an.add("N01", None, "journal %s : %d numéro(s) manquant(s) : %s" % (jc, nb, desc))
        # Chronologie des ValidDate dans l'ordre de numerotation
        tri = sorted(numeriques, key=lambda t: (t[0][0], t[0][1]))
        max_valid = None
        max_num = None
        for (prefixe, n, larg), num, e in tri:
            if not e["valid"]:
                continue
            v = min(e["valid"])
            if max_valid and v < max_valid:
                an.add("T01", e["première"], "journal %s : écriture %s validée le %s, après l'écriture %s validée le %s" % (
                    jc, num, v.strftime("%d/%m/%Y"), max_num, max_valid.strftime("%d/%m/%Y")))
            if max_valid is None or max(e["valid"]) > max_valid:
                max_valid = max(e["valid"])
                max_num = num

    for compte, libs in comptes_lib.items():
        if len(libs) > 1:
            an.add("C03", None, "%s : %s" % (compte, " / ".join(sorted(libs))))
    for jc, libs in journaux_lib.items():
        if len(libs) > 1:
            an.add("J01", None, "%s : %s" % (jc, " / ".join(sorted(libs))))

    return an, stats


def lignes_blocs(nums):
    blocs = []
    for n in nums:
        if blocs and n == blocs[-1][1] + 1:
            blocs[-1][1] = n
        else:
            blocs.append([n, n])
    return blocs


def lignes_ref(nums):
    return ", ".join(str(a) if a == b else "%d-%d" % (a, b) for a, b in lignes_blocs(nums))


def fmt(d):
    q = d.quantize(Decimal("0.01"))
    signe = "-" if q < 0 else ""
    ent, dec = ("%.2f" % abs(q)).split(".")
    groupes = []
    while len(ent) > 3:
        groupes.insert(0, ent[-3:])
        ent = ent[:-3]
    groupes.insert(0, ent)
    return signe + " ".join(groupes) + "," + dec


# --------------------------------------------------------------------------
# Score et rapport
# --------------------------------------------------------------------------

def calculer_score(an, nb_lignes):
    """100 moins une penalite par regle declenchee, ponderee par la gravite et
    modulee par la proportion de lignes touchees (de 60 % a 100 % du poids)."""
    penalite = 0.0
    for code, occ in an.items.items():
        grav = REGLES[code][0]
        poids = POIDS[grav]
        if poids == 0:
            continue
        ratio = min(1.0, len(occ) / max(1, nb_lignes))
        penalite += poids * (0.6 + 0.4 * math.sqrt(ratio))
    score = max(0, int(round(100 - penalite)))
    if any(REGLES[c][0] == "Critique" for c in an.items):
        score = min(score, 59)
    return score


def niveau(score):
    if score >= 90:
        return "Conforme"
    if score >= 75:
        return "Conforme avec réserves"
    if score >= 60:
        return "À corriger"
    return "Non conforme"


def rapport_markdown(an, stats, score, max_lignes=20):
    out = []
    out.append("# Rapport de contrôle de format FEC")
    out.append("")
    out.append("**Fichier :** `%s`  " % stats.get("Fichier", ""))
    out.append("**Score de conformité : %d / 100 (%s)**" % (score, niveau(score)))
    out.append("")
    compte = {g: 0 for g in GRAVITES}
    for code in an.items:
        compte[REGLES[code][0]] += 1
    out.append("| Gravité | Règles en anomalie | Occurrences |")
    out.append("|---|---:|---:|")
    for g in GRAVITES:
        occ = sum(len(v) for c, v in an.items.items() if REGLES[c][0] == g)
        out.append("| %s | %d | %d |" % (g, compte[g], occ))
    out.append("")
    out.append("## Caractéristiques du fichier")
    out.append("")
    out.append("| Élément | Valeur |")
    out.append("|---|---|")
    for k, v in stats.items():
        if k == "Fichier":
            continue
        out.append("| %s | %s |" % (k, str(v).replace("|", "\\|")))
    out.append("")
    out.append("## Anomalies par gravité")
    out.append("")
    if not an.items:
        out.append("Aucune anomalie de format détectée.")
        out.append("")
    for g in GRAVITES:
        codes = [c for c in REGLES if c in an.items and REGLES[c][0] == g]
        if not codes:
            continue
        out.append("### %s" % g)
        out.append("")
        for code in codes:
            _, titre, expl = REGLES[code]
            occ = an.items[code]
            out.append("#### [%s] %s (%d)" % (code, titre, len(occ)))
            out.append("")
            out.append("_%s_" % expl)
            out.append("")
            for ligne, detail in occ[:max_lignes]:
                pos = ("Ligne %d" % ligne) if ligne else "Fichier"
                out.append("- %s%s" % (pos, (" : " + detail) if detail else ""))
            if len(occ) > max_lignes:
                reste = [str(l) for l, _ in occ[max_lignes:] if l]
                extrait = ", ".join(reste[:50])
                out.append("- ... et %d autre(s) occurrence(s)%s" % (
                    len(occ) - max_lignes, (" (lignes %s%s)" % (extrait, ", ..." if len(reste) > 50 else "")) if reste else ""))
            out.append("")
    out.append("---")
    out.append("")
    out.append("_Contrôle de format réalisé selon l'article A47 A-1 du LPF et la description "
               "technique du FEC publiée par la DGFiP. Ce contrôle porte sur la structure du "
               "fichier et ne constitue ni un audit, ni une revue des comptes, ni une garantie "
               "d'acceptation par l'administration. Numéros de ligne = lignes physiques du "
               "fichier, en-tête = ligne 1. controle-fec v%s._" % VERSION)
    out.append("")
    out.append("Une version complète (revue analytique, anomalies métier, note de synthèse client) existe : https://lettra-compta.github.io/")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Contrôle de conformité de format d'un FEC (article A47 A-1 LPF).")
    p.add_argument("fichier", help="chemin du FEC (texte, tabulation ou |)")
    p.add_argument("-o", "--sortie", help="écrire le rapport Markdown dans ce fichier")
    p.add_argument("--json", help="écrire aussi le résultat brut en JSON dans ce fichier")
    p.add_argument("--cloture", help="date de clôture AAAAMMJJ (sinon déduite du nom de fichier)")
    p.add_argument("--max-lignes", type=int, default=20, help="occurrences détaillées par règle (défaut 20)")
    a = p.parse_args(argv)

    if not os.path.isfile(a.fichier):
        print("Fichier introuvable : %s" % a.fichier, file=sys.stderr)
        return 2
    cloture = None
    if a.cloture:
        cloture = parse_date(a.cloture)
        if cloture is None:
            print("Date de clôture invalide (AAAAMMJJ attendu) : %s" % a.cloture, file=sys.stderr)
            return 2

    an, stats = controler(a.fichier, cloture)
    nb = stats.get("Lignes d'écriture", 0) or 0
    score = calculer_score(an, nb)
    md = rapport_markdown(an, stats, score, a.max_lignes)

    if a.sortie:
        with open(a.sortie, "w", encoding="utf-8") as f:
            f.write(md)
        print("Rapport écrit : %s (score %d/100)" % (a.sortie, score))
    else:
        sys.stdout.write(md)
    if a.json:
        data = {
            "score": score, "niveau": niveau(score), "stats": stats,
            "anomalies": [
                {"code": c, "gravite": REGLES[c][0], "titre": REGLES[c][1],
                 "occurrences": [{"ligne": l, "detail": d} for l, d in occ]}
                for c, occ in an.items.items()
            ],
        }
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
