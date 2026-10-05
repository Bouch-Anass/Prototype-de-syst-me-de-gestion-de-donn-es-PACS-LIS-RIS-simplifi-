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
| D08 | HTTP interne synchrone pour le premier essai HL7 ; MLLP en étape suivante | Proposition T02 v0.1 à relire par 2, 3 et 6 | Corps ER7, réponse HL7 ; même service d'ingestion |
| D09 | État d'imagerie daté et timeout Orthanc court | Proposition | Dégradation locale, pas de blocage de tout le dossier |
| D10 | Échec d'audit : refus des opérations cliniques | Proposition à tester | Pas d'accès clinique silencieusement non tracé |
| D11 | Frontend : framework à choisir avant T09 | Ouvert | React avec TypeScript est une option, non une dépendance déjà imposée |
| D12 | Session serveur par cookie HttpOnly pour le navigateur, compte de service distinct pour HL7 | Proposition T02 à relire par 2 et 5 | Expiration, CSRF et droits décrits dans le contrat d'accès ; implémentation T03 |
| D13 | Profil local DEMO-LAB-0.1 sur HL7 2.5.1 | Proposition T02 à relire par 3 | Cardinalités, types et réponses OML/ORU définis dans le contrat HL7 ; pas de conformité générale revendiquée |
| D14 | Viewer et éventuel plugin DICOMweb | Ouvert | REST Orthanc suffit pour le rapprochement initial |
| D15 | Versions exactes des outils et images de conteneurs | À fixer en T01 | Verrouillage avant le premier déploiement reproductible |
| D16 | Licence du dépôt et des données de démonstration | Ouvert | Aucune licence ajoutée automatiquement |
| D17 | Répartition en six membres ; Membre 1 responsable de T02 et T08 | Retenu par le groupe via le porteur du projet | Voir la répartition nominative par numéro ; aucun nom inventé |
| D18 | Français pour les libellés et le nouveau code ; clés machine existantes conservées | Convention de la contribution T02 à relire | Pas de rupture silencieuse des exemples et du modèle existants |
| D19 | DEMO-001 : CRP/glucose et identifiants DEMO pour le premier essai | Proposition explicite à relire | Diffère du scénario NFS/CRP et PAT-SIM-0007 des PDF ; ceux-ci restent inchangés |
| D20 | Schéma JSON de synthèse versionné et exemples validés | Proposition de contrat T02 v0.1 | Structure et types vérifiés séparément des invariants métier |

## État de la revue T02 — 5 octobre 2026

La contribution est prête à être discutée ; aucun accord des autres membres n'est présumé. Le [bilan T02](T02_CONTRATS_COMMUNS.md) précise les décisions, vérifications et avis attendus. D11 (framework), D14 (viewer), D15 (versions de déploiement) et D16 (licence) restent ouverts et ne sont pas nécessaires pour relire les exemples de synthèse. D08, D12, D13 et D19 doivent être acceptées ou amendées avant les implémentations dépendantes.

## Gestion des changements

Une décision modifiée précise le motif, les lots affectés, la migration éventuelle et les tests adaptés. Les décisions ouvertes ne justifient pas des contrats différents selon les modules.

## Questions utiles avant d'élargir le périmètre

- Si deux systèmes réutilisent le même identifiant patient, le domaine d'identification empêche-t-il une collision ?
- Si le LIS retransmet un résultat après un timeout, le dossier change-t-il une seconde fois ?
- Si Orthanc répond mais qu'une étude n'est que partielle, l'interface sait-elle le distinguer ?
- Si le compte rendu est corrigé, quelle version est affichée et où reste la trace précédente ?
- Si un utilisateur connaît l'UUID d'un autre dossier, peut-il quand même y accéder ?

Ces questions correspondent à des tests d'architecture, pas à des fonctionnalités décoratives.

