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
| D08 | HTTP interne pour le premier test HL7 ; MLLP différé | Fixé pour le premier jalon T02 | Même pipeline métier, transport interchangeable ; endpoint hors proxy public |
| D09 | État d'imagerie daté et timeout Orthanc court | Proposition | Dégradation locale, pas de blocage de tout le dossier |
| D10 | Échec d'audit : refus des opérations cliniques | Proposition à tester | Pas d'accès clinique silencieusement non tracé |
| D11 | HTML/CSS/JavaScript sans framework ; conserver les mocks et ajouter un mode API sur la même origine | T09 implémenté, parcours navigateur réel à vérifier | Pas de dépendances npm ni de CORS ; mêmes composants d'affichage pour mocks et synthèse autorisée |
| D12 | Session applicative côté serveur, cookie HttpOnly, SameSite=Lax ; 30 min d'inactivité, 8 h maximum | Première tranche T03 implémentée, testée sur SQLite ; PostgreSQL à vérifier | HTTPS en production impose Secure ; contrôle d'origine et CSRF pour les mutations authentifiées ; rôle et contexte de rencontre vérifiés côté backend |
| D13 | Profil local HL7 v2.5.1 UTF-8 OML^O21 / ORU^R01, ACK original après commit et HTTP interne | Fixé pour le premier jalon T02 | Champs, cardinalités, erreurs et fixtures dans `contracts/hl7-profile.md` ; conformité générale non revendiquée |
| D14 | Aperçu PNG Orthanc via route backend contrôlée ; pas de plugin DICOMweb pour la démonstration | Première tranche T10 implémentée avec faux Orthanc ; vrai PACS à vérifier | Session et droits contrôlés à chaque requête, PNG borné et non mis en cache ; aucun usage diagnostique |
| D15 | Images `postgres:17.11-bookworm` et `orthancteam/orthanc:26.9.1` | Fixé pour T01, démarrage à vérifier avec Docker | Versions explicites ; mise à jour volontaire et testée, sans tag `latest` |
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

