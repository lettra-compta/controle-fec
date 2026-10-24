# controle-fec

Skill Claude (format Agent Skills) de contrôle de conformité de format d'un FEC (Fichier des Écritures Comptables) selon l'article A47 A-1 du Livre des procédures fiscales. Produit un rapport Markdown : score de conformité, anomalies classées par gravité, numéros de ligne.

Contrôle de format uniquement : pas d'analyse financière, pas d'audit, pas de garantie d'acceptation par l'administration.

Auteur : Lettra. Licence : MIT (voir `LICENSE`).

## Installation

**Claude Code, en une commande (recommandé)** : le dépôt est aussi un marketplace de plugins Claude Code. Dans une session Claude Code (version 2.1.275 ou plus) :

```
/plugin install controle-fec --marketplace lettra-compta/controle-fec
```

Ou en deux temps, depuis une session ou le terminal :

```
/plugin marketplace add lettra-compta/controle-fec
/plugin install controle-fec@lettra
```

Mise à jour : `claude plugin update controle-fec@lettra`. Le plugin ne contient que le skill (pas de hook, pas de serveur MCP, aucun appel réseau) : le script s'exécute en local sur le fichier fourni.

**Claude Code, installation manuelle** : copier le dossier `controle-fec/` dans `~/.claude/skills/` (tous les projets) ou dans `.claude/skills/` à la racine d'un projet. Le skill se déclenche quand un FEC est fourni ou qu'un contrôle de FEC est demandé.

**claude.ai** (offres Pro, Max, Team, Enterprise) : zipper le dossier `controle-fec/` (le zip contient le dossier lui-même, dont le nom doit rester `controle-fec`). Dans Paramètres > Capacités, activer l'exécution de code et la création de fichiers, puis dans la section Skills cliquer sur « Upload skill » et importer le zip. Activer le skill dans la liste si besoin.

## Utilisation directe (sans Claude)

```bash
python3 scripts/controle_fec.py 900000002FEC20251231.txt -o rapport.md
python3 scripts/controle_fec.py export.txt --cloture 20251231 --json resultat.json
```

Python 3.8 ou plus, bibliothèque standard uniquement.

## Tests

```bash
python3 tests/test_controle_fec.py
```

Les trois FEC de `tests/` sont synthétiques et fictifs ; `tests/generer_fec_tests.py` les régénère.

## Contenu

- `SKILL.md` : instructions pour Claude
- `.claude-plugin/plugin.json` et `.claude-plugin/marketplace.json` : manifeste du plugin et du marketplace Claude Code
- `scripts/controle_fec.py` : moteur de contrôle
- `references/regles.md` : catalogue des règles, sources et barème du score
- `tests/` : FEC synthétiques et tests
