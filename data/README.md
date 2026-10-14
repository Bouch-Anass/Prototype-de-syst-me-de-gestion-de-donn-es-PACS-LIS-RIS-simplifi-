# Données de démonstration

Le [manifeste commun](fixtures/scenario.json) est la référence des identifiants utilisés par les lots.

| Dossier | Contenu |
|---|---|
| `fixtures/` | Patient, rencontre, commandes et références synthétiques communes |
| `hl7/` | Messages HL7 synthétiques générés depuis le manifeste |
| `dicom/` | Clés de rapprochement et consignes du futur fichier DICOM |
| `generated/` | Sorties locales générées, ignorées par Git |

Les UUID et le Study Instance UID fixes servent uniquement au scénario isolé DEMO-001. D'autres scénarios doivent générer des identifiants distincts. Ils ne constituent pas une stratégie d'identification de production.

Le seed SQL/applicatif n'est pas encore fourni. Le manifeste décrit ses entrées, pas une commande d'import déjà disponible.

