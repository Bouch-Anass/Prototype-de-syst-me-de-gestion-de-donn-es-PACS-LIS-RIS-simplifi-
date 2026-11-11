# Données de démonstration

Le [manifeste commun](fixtures/scenario.json) est la référence des identifiants utilisés par les lots.

| Dossier | Contenu |
|---|---|
| `fixtures/` | Patient, rencontre, commandes et références synthétiques communes |
| `hl7/` | Messages HL7 synthétiques générés depuis le manifeste |
| `dicom/` | Clés de rapprochement et consignes du futur fichier DICOM |
| `generated/` | Sorties locales générées, ignorées par Git |

Les UUID et le Study Instance UID fixes servent uniquement au scénario isolé DEMO-001. D'autres scénarios doivent générer des identifiants distincts. Ils ne constituent pas une stratégie d'identification de production.

Le seed applicatif est disponible via `python -m app.cli seed-demo` dans le backend ; la [procédure Docker](../docs/DOCKER.md) montre son exécution dans le conteneur.

Une copie locale d'un CT fourni par l'utilisateur peut être préparée avec [prepare_demo_ct.py](../scripts/prepare_demo_ct.py). Le script conserve seulement les attributs nécessaires à l'image, remplace les identifiants par ceux de `DEMO-ACC002`, retire les tags privés et génère un PNG pour rechercher visuellement des annotations incrustées. La copie et le PNG restent dans `data/generated/`, ignoré par Git ; le fichier source n'est pas modifié. Le nom du fichier source suggère NLST, mais sa provenance et ses droits de réutilisation ne sont pas établis par le dépôt. Cette transformation ne constitue pas une certification d'anonymisation.

