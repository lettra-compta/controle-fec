# Règles de contrôle

Sources publiques : Livre des procédures fiscales, articles L47 A et A47 A-1 ; description technique du FEC publiée par la DGFiP ; Plan comptable général (classes 1 à 7).

## Rappels de la norme (article A47 A-1)

- 18 champs, dans cet ordre : JournalCode, JournalLib, EcritureNum, EcritureDate, CompteNum, CompteLib, CompAuxNum, CompAuxLib, PieceRef, PieceDate, EcritureLib, Debit, Credit, EcritureLet, DateLet, ValidDate, Montantdevise, Idevise.
- Variante admise : Debit et Credit remplacés par Montant et Sens (Sens = D/C ou +1/-1).
- Champs facultatifs (vides si non utilisés) : CompAuxNum, CompAuxLib, EcritureLet, DateLet, Montantdevise, Idevise. Tous les autres sont obligatoires.
- Première ligne : noms des champs. Encodage ASCII, ISO 8859-15 ou UTF-8.
- Dates AAAAMMJJ sans séparateur. Montants : virgule décimale, pas de séparateur de milliers, signe admis en premier ou dernier caractère.
- CompteNum : les trois premiers caractères sont numériques et correspondent au PCG.
- Nom du fichier : SirenFECAAAAMMJJ (date de clôture).

Note : le texte laisse au contribuable le choix du séparateur, à décrire dans la documentation remise. La tabulation et la barre verticale sont les deux usages les plus courants ; ce skill ne reconnaît que ces deux séparateurs.

## Catalogue

| Code | Gravité | Contrôle | Explication |
|---|---|---|---|
| F01 | Critique | Fichier vide ou illisible | Le fichier ne contient aucune ligne exploitable. |
| F02 | Critique | Séparateur non reconnu | Ni tabulation ni barre verticale (\|) détectée dans l'en-tête. |
| F03 | Critique | Nombre de colonnes de l'en-tête différent de 18 | L'article A47 A-1 impose 18 champs, dans un ordre fixe. |
| F04 | Critique | Libellé ou ordre de colonne non conforme | Les noms de champs de la première ligne doivent reprendre exactement ceux de l'article A47 A-1, dans l'ordre. |
| F05 | Mineure | Casse ou espaces des libellés de colonnes | Le libellé est reconnu mais ne respecte pas la graphie exacte de la norme. |
| F06 | Majeure | Nombre de champs incorrect sur une ligne | La ligne ne comporte pas le même nombre de champs que l'en-tête (séparateur parasite dans un libellé, champ manquant). |
| F07 | Mineure | Marque d'ordre des octets (BOM) en début de fichier | Accepté par la plupart des outils mais source de rejet du premier libellé de colonne par certains. |
| F08 | Mineure | Nom de fichier non conforme | Le nom attendu est SirenFECAAAAMMJJ (SIREN sur 9 chiffres, puis FEC, puis date de clôture). |
| F09 | Mineure | Lignes vides dans le fichier | Des lignes vides ont été ignorées. |
| D01 | Majeure | Champ obligatoire vide | Ce champ ne peut pas être vide selon l'article A47 A-1. |
| D02 | Majeure | Date invalide (format AAAAMMJJ attendu) | Les dates doivent être au format AAAAMMJJ sans séparateur et correspondre à une date réelle. |
| D03 | Majeure | Montant invalide | Les montants doivent être numériques, virgule décimale, sans séparateur de milliers ; le signe est admis en premier ou dernier caractère. |
| D04 | Mineure | Point utilisé comme séparateur décimal | La norme impose la virgule comme séparateur décimal. Le montant a été interprété malgré tout. |
| D05 | Majeure | Champ Sens invalide | Dans la variante Montant/Sens, Sens doit valoir D ou C, ou +1 ou -1. |
| D06 | Mineure | Débit et crédit renseignés sur la même ligne | Une ligne d'écriture porte normalement un montant soit au débit, soit au crédit. |
| D07 | Information | Montants négatifs | Admis par la norme (montant signé) mais à vérifier : une contrepassation s'inscrit en principe dans le sens opposé. |
| D08 | Mineure | Ligne à montant nul | Débit et crédit nuls sur la ligne. |
| D09 | Majeure | Devise renseignée sans montant en devise (ou inversement) | Montantdevise et Idevise doivent être renseignés ensemble. |
| D10 | Mineure | Date de lettrage sans code de lettrage (ou inversement) | EcritureLet et DateLet vont de pair. |
| C01 | Majeure | Numéro de compte non conforme au PCG | Les trois premiers caractères de CompteNum doivent être numériques (article A47 A-1, VII 1). |
| C02 | Majeure | Compte hors des classes 1 à 7 du PCG | Seuls les comptes des classes 1 à 7 (bilan et gestion) sont attendus dans un FEC. Les classes 8 (comptes spéciaux) et 9 (analytique) n'y ont pas leur place. |
| C03 | Mineure | Même numéro de compte avec plusieurs libellés | Un numéro de compte devrait porter un libellé unique sur l'exercice. |
| E01 | Critique | Déséquilibre global débit / crédit | Le total des débits doit égaler le total des crédits. |
| E02 | Critique | Écriture déséquilibrée | Pour un même couple JournalCode + EcritureNum, le total des débits doit égaler le total des crédits. |
| E03 | Majeure | Dates d'écriture différentes au sein d'une même écriture | Toutes les lignes d'une écriture doivent porter la même EcritureDate. |
| E04 | Mineure | Écriture fractionnée dans le fichier | Les lignes d'une même écriture ne sont pas contiguës. |
| E05 | Mineure | Écriture à une seule ligne | Une écriture comptable mouvemente au moins deux comptes. |
| T01 | Majeure | Chronologie des dates de validation non respectée | Dans un journal, les écritures doivent être validées dans l'ordre de leur numérotation : une date de validation antérieure à celle de l'écriture précédente signale une rupture de chronologie. |
| T02 | Mineure | Date de validation antérieure à la date d'écriture | ValidDate est antérieure à EcritureDate. |
| T03 | Majeure | Date d'écriture postérieure à la date de clôture | EcritureDate est postérieure à la date de clôture de l'exercice. |
| T04 | Mineure | Période couverte supérieure à 24 mois | L'écart entre la première et la dernière EcritureDate dépasse 24 mois. |
| N01 | Majeure | Trous dans la numérotation des écritures | Dans un journal, la numérotation des écritures doit être continue et sans rupture. |
| N02 | Majeure | Numéro d'écriture réutilisé à des dates différentes | Un même EcritureNum est employé pour des écritures distinctes dans le même journal. |
| N03 | Mineure | Numérotation non exploitable pour le contrôle de continuité | Le numéro d'écriture ne se termine pas par une partie numérique ; la continuité n'a pas pu être vérifiée. |
| J01 | Mineure | Code journal avec plusieurs libellés | Un code journal devrait porter un libellé unique. |

## Score

Score = 100 moins, pour chaque règle déclenchée, une pénalité égale au poids de sa gravité (Critique 25, Majeure 10, Mineure 3, Information 0) modulé de 60 % à 100 % selon la proportion de lignes touchées (racine carrée du ratio). Une seule anomalie critique plafonne le score à 59.

| Score | Niveau |
|---|---|
| 90 à 100 | Conforme |
| 75 à 89 | Conforme avec réserves |
| 60 à 74 | À corriger |
| 0 à 59 | Non conforme |

Ce barème est une convention interne au skill, pas une grille de l'administration.
