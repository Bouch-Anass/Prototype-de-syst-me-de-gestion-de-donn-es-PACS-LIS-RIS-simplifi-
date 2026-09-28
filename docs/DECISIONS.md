# Décisions et points à confirmer

Ce fichier distingue les éléments repris de la conception et les précisions proposées pour rendre le travail distribuable.

| ID | Décision | Statut | Conséquence |
|---|---|---|---|
| D01 | PostgreSQL métier séparé du stockage DICOM Orthanc | Repris de la conception | Pas de pixels dans la base métier |
| D02 | Dossier centré sur patient et rencontre | Repris de la conception | Un résultat ne flotte pas sans contexte |
| D03 | HL7 v2 ciblé et DICOM pour les échanges | Repris de la conception | Profil local et scénarios testés obligatoires |
| D04 | FastAPI en backend modulaire dans un monorepo | Proposition de structuration | Pas de microservices au premier jalon |
| D05 | Réponse de synthèse commune et mocks JSON | Proposition de contrat | Frontend indépendant de l'avancement des connecteurs |
| D06 | RIS implémenté dans le backend | Proposition de périmètre | Pas de RIS externe supplémentaire |
| D07 | Ingestion OML puis ORU depuis le simulateur | Proposition de premier flux | Pas de prescription sortante bidirectionnelle à ce stade |
| D08 | HTTP interne pour le premier test HL7, MLLP ensuite si retenu | À confirmer en T02 | Même pipeline métier, transport interchangeable |
| D09 | État d'imagerie daté et timeout Orthanc court | Proposition | Dégradation locale, pas de blocage de tout le dossier |
| D10 | Échec d'audit : refus des opérations cliniques | Proposition à tester | Pas d'accès clinique silencieusement non tracé |
| D11 | Frontend : framework à choisir avant T09 | Ouvert | React avec TypeScript est une option, non une dépendance déjà imposée |
| D12 | Schéma d'authentification et durée des sessions | Ouvert | Pas de choix implicite entre cookies et tokens |
| D13 | Version HL7, champs obligatoires, ACK, encodage et transport | Ouvert, bloquant pour le parseur | Pas de conformité présumée d'après le seul nom de message |
| D14 | Viewer et éventuel plugin DICOMweb | Ouvert | REST Orthanc suffit pour le rapprochement initial |
| D15 | Versions exactes des outils et images de conteneurs | À fixer en T01 | Verrouillage avant le premier déploiement reproductible |
| D16 | Licence du dépôt et des données de démonstration | Ouvert | Aucune licence ajoutée automatiquement |

## Gestion des changements

Une décision modifiée précise le motif, les lots affectés, la migration éventuelle et les tests adaptés. Les décisions ouvertes ne justifient pas des contrats différents selon les modules.

## Questions utiles avant d'élargir le périmètre

- Si deux systèmes réutilisent le même identifiant patient, le domaine d'identification empêche-t-il une collision ?
- Si le LIS retransmet un résultat après un timeout, le dossier change-t-il une seconde fois ?
- Si Orthanc répond mais qu'une étude n'est que partielle, l'interface sait-elle le distinguer ?
- Si le compte rendu est corrigé, quelle version est affichée et où reste la trace précédente ?
- Si un utilisateur connaît l'UUID d'un autre dossier, peut-il quand même y accéder ?

Ces questions correspondent à des tests d'architecture, pas à des fonctionnalités décoratives.

