#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genere les 3 FEC synthetiques (donnees entierement fictives) utilises par les tests."""

import os

ICI = os.path.dirname(os.path.abspath(__file__))

# SIREN fictifs : 9 chiffres dont la cle de Luhn est FAUSSE, donc impossibles
# comme vrais SIREN (aucun risque de designer une entreprise existante).
SIREN_CONFORME = "900000002"
SIREN_ANOMALIES = "900000003"
SIREN_ISO = "900000004"

ENTETE = ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
          "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate",
          "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate",
          "Montantdevise", "Idevise"]

JOURNAUX = {"AC": "Achats", "VE": "Ventes", "BQ": "Banque", "OD": "Opérations diverses"}
COMPTES = {
    "401000": "Fournisseurs", "411000": "Clients", "512000": "Banque",
    "607000": "Achats de marchandises", "445660": "TVA déductible sur ABS",
    "706000": "Prestations de services", "445710": "TVA collectée",
    "641000": "Rémunérations du personnel", "421000": "Personnel - rémunérations dues",
    "626000": "Frais postaux et télécommunications",
}


def ligne(j, num, d, compte, aux, piece, lib, debit, credit, valid, let="", dlet=""):
    auxnum, auxlib = aux if aux else ("", "")
    return [j, JOURNAUX[j], num, d, compte, COMPTES.get(compte, "Compte divers"),
            auxnum, auxlib, piece, d, lib, debit, credit, let, dlet, valid, "", ""]


def base_ecritures():
    """Exercice 2025 equilibre, numerotation continue, validations chronologiques."""
    L = []
    # Ventes VE000001 a VE000006
    for i in range(1, 7):
        d = "2025%02d15" % (i * 2 - 1 if i * 2 - 1 <= 12 else 12)
        v = "2025%02d20" % (i * 2 - 1 if i * 2 - 1 <= 12 else 12)
        ht = 1000 * i
        tva = ht // 5
        num = "VE%06d" % i
        lib = "Facture client F%03d" % i
        L.append(ligne("VE", num, d, "411000", ("C001", "Client Alpha"), "F%03d" % i, lib, "%d,00" % (ht + tva), "0,00", v))
        L.append(ligne("VE", num, d, "706000", None, "F%03d" % i, lib, "0,00", "%d,00" % ht, v))
        L.append(ligne("VE", num, d, "445710", None, "F%03d" % i, lib, "0,00", "%d,00" % tva, v))
    # Achats AC000001 a AC000004
    for i in range(1, 5):
        d = "2025%02d10" % (i * 3)
        v = "2025%02d12" % (i * 3)
        ht = 400 * i
        tva = ht // 5
        num = "AC%06d" % i
        lib = "Facture fournisseur A%03d" % i
        L.append(ligne("AC", num, d, "607000", None, "A%03d" % i, lib, "%d,00" % ht, "0,00", v))
        L.append(ligne("AC", num, d, "445660", None, "A%03d" % i, lib, "%d,00" % tva, "0,00", v))
        L.append(ligne("AC", num, d, "401000", ("F001", "Fournisseur Beta"), "A%03d" % i, lib, "0,00", "%d,00" % (ht + tva), v))
    # Banque BQ000001 a BQ000004 (encaissements et reglements)
    for i in range(1, 5):
        d = "2025%02d25" % (i * 3)
        v = "2025%02d28" % (i * 3)
        num = "BQ%06d" % i
        lib = "Encaissement client %d" % i
        m = 1200 * i
        L.append(ligne("BQ", num, d, "512000", None, "R%03d" % i, lib, "%d,00" % m, "0,00", v))
        L.append(ligne("BQ", num, d, "411000", ("C001", "Client Alpha"), "R%03d" % i, lib, "0,00", "%d,00" % m, v))
    # OD : paie
    for i in range(1, 4):
        d = "2025%02d28" % (i * 4)
        v = "2025%02d30" % (i * 4)
        num = "OD%06d" % i
        lib = "Salaires mois %d" % (i * 4)
        L.append(ligne("OD", num, d, "641000", None, "P%03d" % i, lib, "2500,00", "0,00", v))
        L.append(ligne("OD", num, d, "421000", None, "P%03d" % i, lib, "0,00", "2500,00", v))
    return L


def ecrire(nom, lignes, sep, encodage):
    chemin = os.path.join(ICI, nom)
    with open(chemin, "w", encoding=encodage, newline="") as f:
        f.write(sep.join(ENTETE) + "\r\n")
        for l in lignes:
            f.write(sep.join(l) + "\r\n")
    return chemin


def fec_conforme():
    return ecrire(SIREN_CONFORME + "FEC20251231.txt", base_ecritures(), "\t", "utf-8")


def fec_anomalies():
    """8 anomalies injectees, une par famille de controle."""
    L = base_ecritures()

    def trouve(num, compte=None):
        for i, l in enumerate(L):
            if l[2] == num and (compte is None or l[4] == compte):
                return i
        raise KeyError(num)

    # 1. D02 date invalide (30 fevrier) sur PieceDate
    L[trouve("AC000001", "607000")][9] = "20250230"
    # 2. D03 montant avec separateur de milliers (les deux lignes : ecriture restee equilibree)
    L[trouve("OD000001", "641000")][11] = "2 500,00"
    L[trouve("OD000001", "421000")][12] = "2 500,00"
    # 3. E02 + E01 ecriture desequilibree (credit 706 minore de 100)
    L[trouve("VE000003", "706000")][12] = "2900,00"
    # 4. N01 trou de numerotation : BQ000004 renumerotee BQ000005
    for i, l in enumerate(L):
        if l[2] == "BQ000004":
            L[i][2] = "BQ000005"
    # 5. T01 chronologie : VE000004 validee le 05/10/2025, apres VE000005 (20/09/2025)
    for i, l in enumerate(L):
        if l[2] == "VE000004":
            L[i][15] = "20251005"
    # 6. C02 compte de classe 9 (analytique)
    i = trouve("AC000002", "607000")
    L[i][4], L[i][5] = "920000", "Section analytique atelier"
    # 7. D01 champ obligatoire vide (PieceRef)
    L[trouve("AC000003", "445660")][8] = ""
    # 8. F06 ligne tronquee (dernier champ Idevise absent)
    L[trouve("AC000004", "445660")] = L[trouve("AC000004", "445660")][:17]
    return ecrire(SIREN_ANOMALIES + "FEC20251231.txt", L, "\t", "utf-8")


def fec_iso_pipe():
    L = base_ecritures()
    # Libelles avec accents et symbole euro (0xA4 en ISO-8859-15)
    for l in L:
        if l[0] == "AC":
            l[10] = l[10].replace("Facture fournisseur", "Achat matériel 100 € élève")
    return ecrire(SIREN_ISO + "FEC20251231.txt", L, "|", "iso-8859-15")


if __name__ == "__main__":
    for p in (fec_conforme(), fec_anomalies(), fec_iso_pipe()):
        print("genere :", p)
