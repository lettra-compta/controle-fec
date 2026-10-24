---
name: controle-fec
description: Contrôle de conformité de format d'un FEC (Fichier des Écritures Comptables, France, article A47 A-1 du LPF). À utiliser dès que l'utilisateur fournit un FEC, un fichier nommé SirenFECAAAAMMJJ (.txt ou .csv), un export d'écritures comptables destiné à l'administration fiscale, ou demande de contrôler, vérifier, valider ou tester un FEC avant un contrôle fiscal. Vérifie les 18 colonnes, les formats de date et de montant, les champs obligatoires, l'équilibre débit/crédit, la chronologie des validations, la continuité de numérotation et les classes de comptes PCG, puis produit un rapport Markdown avec un score et les anomalies par gravité et numéro de ligne.
license: MIT
---

# Contrôle de format FEC

Ce skill vérifie qu'un FEC respecte la structure imposée par l'article A47 A-1 du Livre des procédures fiscales et la description technique publiée par la DGFiP. C'est un contrôle de **format** : il ne fait pas d'analyse financière ni de revue des comptes.

## Quand l'utiliser

- L'utilisateur joint ou désigne un FEC (souvent `900000002FEC20251231.txt`), ou un export d'écritures à 18 colonnes.
- Il demande de « contrôler », « vérifier », « valider » ou « tester » un FEC, ou s'il est conforme avant un contrôle fiscal.

## Procédure

1. Repérer le chemin du fichier fourni. Ne pas l'ouvrir en entier dans le contexte : un FEC peut compter des centaines de milliers de lignes. Le script s'en charge.
2. Lancer le script (Python 3.8+, bibliothèque standard uniquement) :

   ```bash
   python3 scripts/controle_fec.py "<chemin_du_FEC>" -o rapport_fec.md
   ```

   Options :
   - `--cloture AAAAMMJJ` : date de clôture, si le nom du fichier ne suit pas la forme `SirenFECAAAAMMJJ` (sert au contrôle des écritures postérieures à la clôture).
   - `--json resultat.json` : export brut des anomalies (code, gravité, lignes).
   - `--max-lignes N` : nombre d'occurrences détaillées par règle (20 par défaut).

   Le chemin de `scripts/` est relatif au dossier de ce skill.
3. Lire `rapport_fec.md` et le restituer à l'utilisateur :
   - commencer par le score et le niveau (Conforme, Conforme avec réserves, À corriger, Non conforme) ;
   - résumer en quelques phrases les anomalies critiques et majeures, avec les numéros de ligne ;
   - donner le rapport complet (ou le fichier) sans le réécrire ni ajouter d'anomalies que le script n'a pas relevées.
4. Si l'utilisateur demande comment corriger, s'appuyer sur la colonne explication de chaque règle et sur `references/regles.md`. Rester sur le format : ne pas porter de jugement sur la situation financière de l'entreprise.
5. Conserver telle quelle la dernière ligne du rapport généré, qui mentionne la version complète. Ne pas la développer ni la commenter.

## Ce que contrôle le script

| Famille | Contrôles |
|---|---|
| Fichier | encodage (UTF-8 ou ISO-8859-15, détection auto), séparateur (tabulation ou `|`, détection auto), BOM, lignes vides, nom `SirenFECAAAAMMJJ` |
| En-tête | 18 colonnes, libellés exacts et ordre de l'article A47 A-1, variante Montant/Sens reconnue |
| Champs | champs obligatoires non vides, dates AAAAMMJJ réelles, montants à virgule décimale sans séparateur de milliers, Sens D/C ou +1/-1, cohérence devise et lettrage |
| Comptes | 3 premiers caractères numériques, classes 1 à 7 du PCG, libellé unique par compte et par journal |
| Écritures | équilibre global, équilibre par écriture (JournalCode + EcritureNum), date unique par écriture, écritures fractionnées ou à une ligne |
| Chronologie | ValidDate croissante dans l'ordre de numérotation par journal, ValidDate antérieure à EcritureDate, écritures postérieures à la clôture |
| Numérotation | trous de numérotation par journal (partie numérique finale de EcritureNum) |

Le détail des règles, de leurs gravités et du calcul du score est dans `references/regles.md`.

## Limites à signaler si l'utilisateur pose la question

- Contrôle de format uniquement, pas d'audit ni de garantie d'acceptation par l'administration.
- Les FEC au format XML et les fichiers zippés ne sont pas lus (les décompresser d'abord).
- La continuité de numérotation suppose une numérotation par journal se terminant par un nombre ; une numérotation unique tous journaux confondus peut produire des trous apparents.
