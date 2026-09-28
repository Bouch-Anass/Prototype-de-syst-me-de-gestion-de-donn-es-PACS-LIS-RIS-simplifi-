# Backend

Cible proposée : une application FastAPI modulaire, une base PostgreSQL métier, des adaptateurs HL7 et Orthanc.

Ce dossier ne contient pas encore d'application exécutable. T03 introduira l'entrée `src/app/main.py`, la configuration, les dépendances verrouillées et les migrations.

| Emplacement | Responsabilité |
|---|---|
| [core](src/app/core/README.md) | Configuration, erreurs et dépendances communes |
| [db](src/app/db/README.md) | Session, transactions et historique des migrations |
| [modules](src/app/modules/README.md) | Domaines métier |
| [integrations](src/app/integrations/README.md) | Frontières avec HL7 et Orthanc |

Routes, services et stockage sont séparés. Les objets ORM ne doivent pas être retournés directement au frontend avec tous leurs champs. Les contrats exposent seulement les informations autorisées.

