# Domaines métier

| Module | Lot | Interface principale |
|---|---|---|
| [identity](identity/README.md) | A | Résolution exacte du patient et de la rencontre |
| [auth](auth/README.md) | A | Acteur authentifié et accès autorisé |
| [audit](audit/README.md) | A | Trace minimale d'une opération |
| [laboratory](laboratory/README.md) | B | Demande, résultat, correction et lecture |
| [radiology](radiology/README.md) | C | Demande, examen et compte rendu |
| [imaging](imaging/README.md) | C | Rapprochement et disponibilité d'étude |
| [summary](summary/README.md) | A | Composition de la réponse du dossier |

Les modules sont dans le même backend et peuvent partager une transaction. Cette proximité ne supprime pas leur propriété des tables et des règles métier.

