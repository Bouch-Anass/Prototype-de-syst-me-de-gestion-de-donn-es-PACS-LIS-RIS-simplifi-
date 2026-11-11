# Contrat API de démarrage

## Routes de la conception

| Méthode et chemin | Fonction | Accès minimal |
|---|---|---|
| `POST /api/v1/auth/login` | Ouvrir une session | Identifiants valides ; protection contre les tentatives répétées |
| `GET /api/v1/auth/me` | Restaurer le rôle de la session active | Session valide |
| `GET /api/v1/patients?identifier=...` | Recherche par identifiant | Utilisateur autorisé, contexte contrôlé |
| `GET /api/v1/patients/{id}/encounters` | Rencontres du patient | Accès autorisé à ce patient |
| `GET /api/v1/encounters/{id}/summary` | Dossier agrégé | Un des quatre rôles cliniques et accès à la rencontre |
| `GET /api/v1/imaging-studies/{id}` | Métadonnées d'une étude | Accès clinique à la rencontre liée |
| `GET /api/v1/imaging-studies/{id}/viewer-link` | Accès contrôlé à l'affichage | Même contrôle que les métadonnées |
| `POST /api/v1/lab-orders/{id}/reports` | Nouvelle version du résultat biologique | Technicien de laboratoire et accès à la rencontre |
| `POST /api/v1/encounters/{id}/imaging-studies` | Import d'une instance DICOM synthétique | Technicien d'imagerie et accès à la rencontre |
| `POST /internal/hl7/messages` | Transport HTTP de test, si retenu | Compte de service ; réseau interne uniquement |
| `GET /health/ready` | État prêt/non prêt du service métier | Réponse technique minimale |

Le formulaire biologique accepte 1 à 200 observations numériques dans une nouvelle version du rapport. CRP et glucose gardent les codes et unités du manifeste ; les analyses supplémentaires ont un code local `DEMO`, un libellé et une unité fournis par le technicien. Les codes dupliqués dans une même version sont refusés. Le profil d'entrée HL7 demeure limité aux analyses du manifeste. Le navigateur envoie les DICOM sélectionnés un par un à la route d'import existante, avec un bilan des réussites et des échecs ; chaque instance reste limitée à 8 Mio et doit correspondre à une demande RIS autorisée.

D12 fixe pour T03 une session côté serveur avec cookie HttpOnly et SameSite=Lax, expiration après 30 minutes d'inactivité et 8 heures au maximum ; `Secure` est activé sous `APP_ENV=production` avec origine HTTPS. Le login vérifie l'origine ; les mutations authentifiées utilisent l'origine et `X-CSRF-Token`. Ces mécanismes sont implémentés dans la première tranche T03 pour login, logout, recherche et rencontres. Le rôle seul ne suffit pas à autoriser l'accès à un dossier. Le premier jalon retourne 403 pour une ressource existante hors contexte et 404 pour une ressource inexistante, sans contenu clinique dans les deux cas.

La recherche T03 exige `identifier_domain` et `identifier` en paramètres de requête. Elle retourne `{"patients":[...]}` avec l'identité minimale. La route des rencontres retourne `{"encounters":[...]}` avec les seules rencontres explicitement accordées à l'utilisateur. La route interne HL7 est implémentée pour le profil local DEMO-001. La synthèse T08 et les routes d'imagerie T10 exigent une session clinique et un accès explicite à la rencontre.

## Routes d'écriture RIS T06

| Route proposée | Usage | Lot |
|---|---|---|
| `POST /api/v1/radiology-orders` | Créer une demande liée à une rencontre | C avec A |
| `PATCH /api/v1/radiology-exams/{id}` | Faire évoluer l'état d'un examen | C |
| `PUT /api/v1/radiology-exams/{id}/report` | Enregistrer le compte rendu courant | C |
| `POST /api/v1/radiology-exams/{id}/report/validate` | Valider le brouillon courant | C |

Ces routes ne sont pas présentées comme déjà spécifiées dans les PDF. Elles sont exposées avec session, contrôle d'origine, CSRF, réponse d'erreur et audit des refus métier. `PATCH` accepte `{"status":"performed","performed_at":"...Z"}` ; `PUT /report` accepte `{"content":"..."}` et conserve un brouillon ; `/validate` accepte `{"validated_at":"...Z"}`. Le final est immuable. Les données initiales du scénario T07 peuvent encore être créées par un seed.

L'accès contrôlé à l'imagerie ajoute `GET /api/v1/imaging-studies/{id}/preview`, qui renvoie un PNG borné et non mis en cache après vérification des droits et de la disponibilité. `viewer-link` renvoie uniquement son chemin relatif local, sans credential Orthanc. Il s'agit d'un aperçu de démonstration non diagnostique.

## Forme de la synthèse

Les [trois fichiers JSON](examples/README.md) fixent le premier contrat d'affichage pour un utilisateur autorisé à consulter l'ensemble de la rencontre.

| Champ racine | Signification |
|---|---|
| `patient` | UUID, identifiant externe, domaine, nom synthétique |
| `encounter` | Rencontre et état |
| `laboratory` | État global du bloc et versions courantes des rapports à afficher |
| `radiology` | Examens et compte rendu courant |
| `imaging` | Disponibilité globale, références d'études et date d'état |
| `warnings` | Avertissements structurés sans contenu sensible inutile |

`laboratory.status` : `available/partial/unavailable`.
`imaging.availability_status` et état de chaque étude : `available/incomplete/unavailable`.
`observation.data_status` : `available/missing/invalid`.

Le statut API `partial` est calculé ; il n'est pas un nouvel état de la table `lab_report`. Un rapport peut être final et contenir une analyse attendue manquante.

La réponse présente la dernière version pertinente d'un rapport biologique. La conservation de toutes les versions en base reste obligatoire ; une route d'historique sera ajoutée séparément si nécessaire.

Une date `last_synced_at` ne prouve pas la disponibilité actuelle. En cas de contrôle récent échoué, l'état retourné est `unavailable`, même si une référence d'étude connue est conservée.

## Matrice des droits implémentée

| Action | physician | radiologist | lab_technician | imaging_technician | admin |
|---|---|---|---|---|---|
| Lire la synthèse LIS/RIS/PACS d'une rencontre accordée | Oui | Oui | Oui | Oui | Non par défaut |
| Créer une version de résultat LIS | Non | Non | Oui | Non | Non |
| Créer/finaliser un examen et compte rendu RIS | Non | Oui | Non | Non | Non |
| Importer une instance DICOM dans Orthanc et la rapprocher | Non | Non | Non | Oui | Non |

Toutes les écritures exigent session, origine autorisée, jeton CSRF et accès explicite à la rencontre. La route d'import vérifie les identifiants synthétiques et la correspondance avec une demande RIS avant le stockage dans Orthanc. Les routes d'administration et d'audit global ne sont pas exposées dans ce prototype. Administrer l'application ne donne pas automatiquement accès aux données cliniques.

## Erreurs

Exemple fictif :

```json
{
  "code": "ACCESS_DENIED",
  "message": "Accès non autorisé à cette ressource.",
  "correlation_id": "b0000000-0000-4000-8000-000000000001"
}
```

| Situation | HTTP attendu |
|---|---|
| Absence d'authentification ou session invalide | 401 |
| Droit insuffisant sur ressource existante | 403, sans données cliniques |
| Ressource inexistante | 404 |
| Réutilisation incohérente d'identifiant métier | 409 |
| Données d'entrée invalides | 422 |
| Base métier ou audit requis indisponible | 503 |
| Orthanc seul indisponible pendant la synthèse | 200 avec état dégradé |
| Accès au viewer impossible car PACS indisponible | 503 contrôlé |

Les réponses techniques ne contiennent ni traceback, ni payload HL7, ni mot de passe, ni adresse privée sensible. L'état HTTP du transport HL7 ne remplace jamais l'ACK applicatif défini dans son profil.

## Interfaces internes proposées

| Service | Entrée | Sortie ou effet |
|---|---|---|
| Identité : resolve_patient | domaine et identifiant externe | UUID exact ou erreur d'identité |
| Laboratoire : ingest_order / ingest_result | message validé et identité résolue | Écriture transactionnelle, identifiant de traitement |
| Radiologie : get_encounter_exams | UUID de rencontre | Examens et compte rendu autorisés |
| Imagerie : get_availability | UUID d'examen, budget temporel | Référence, état et date de vérification |
| Synthèse : build_summary | acteur et UUID de rencontre | Réponse commune, audit requis |
| Audit : record_event | acteur, action, ressource, résultat, corrélation | Trace minimale persistée |

Ces noms décrivent des responsabilités. Les signatures Python exactes seront fixées lors de T02/T03.

