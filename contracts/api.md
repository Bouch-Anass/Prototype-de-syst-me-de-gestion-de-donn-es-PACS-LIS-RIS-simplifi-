# Contrat API de démarrage

Version proposée : **0.1.0**, contribution T02 du Membre 1. Revue requise avant adoption collective. La structure de synthèse est définie par [le schéma JSON](schemas/synthese.schema.json) ; les erreurs par [leur schéma](schemas/erreur.schema.json). Le [contrat d'accès](acces.md) complète les droits décrits ici.

## Routes de la conception

| Méthode et chemin | Fonction | Accès minimal |
|---|---|---|
| `POST /api/v1/auth/login` | Ouvrir une session | Identifiants valides ; protection contre les tentatives répétées |
| `GET /api/v1/patients?identifier_domain=...&identifier=...` | Recherche exacte par domaine et identifiant | Utilisateur autorisé, contexte contrôlé |
| `GET /api/v1/patients/{id}/encounters` | Rencontres du patient | Accès autorisé à ce patient |
| `GET /api/v1/encounters/{id}/summary` | Dossier agrégé | Médecin ou radiologue autorisé |
| `GET /api/v1/imaging-studies/{id}` | Métadonnées d'une étude | Accès clinique à la rencontre liée |
| `GET /api/v1/imaging-studies/{id}/viewer-link` | Accès contrôlé à l'affichage | Même contrôle que les métadonnées |
| `POST /internal/hl7/messages` | Transport HTTP de test, si retenu | Compte de service ; réseau interne uniquement |
| `GET /health/ready` | État prêt/non prêt du service métier | Réponse technique minimale |

Login et session suivent D12 et [le contrat d'accès](acces.md). Recherche : paramètres obligatoires non vides, comparaison exacte sensible à la casse, sans normalisation implicite. Retour `{"items": [...]}` avec zéro ou un patient au format du schéma ; zéro résultat si absent ou hors affectation. La liste des épisodes utilise la même enveloppe, tri décroissant de `started_at`, puis UUID. Les noms ne servent jamais de clé.

Pour `summary`, UUID mal formé : 422 ; identité non authentifiée : 401 ; rôle non autorisé : 403 ; épisode inconnu ou hors affectation : 404. Les deux derniers cas de ressource utilisent le même message. Les réponses cliniques et erreurs portent `Cache-Control: no-store` et `X-Correlation-ID` (UUID généré côté serveur). La corrélation du corps d'erreur est identique à cet en-tête. Aucune réponse avec données avant autorisation et audit requis.

## Propositions de routes d'écriture, à valider avant implémentation

| Route proposée | Usage | Lot |
|---|---|---|
| `POST /api/v1/radiology-orders` | Créer une demande liée à une rencontre | C avec A |
| `PATCH /api/v1/radiology-exams/{id}` | Faire évoluer l'état d'un examen | C |
| `PUT /api/v1/radiology-exams/{id}/report` | Enregistrer le compte rendu courant | C |

Ces routes ne sont pas présentées comme déjà spécifiées dans les PDF. Les transitions, droits et validations doivent être testés avant exposition. Les données initiales peuvent être créées par un seed tant que ces routes ne sont pas prêtes.

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

## Nullabilité, ordre et qualité

Tous les champs du schéma sont présents, même lorsqu'une valeur autorise `null`. Une liste vide signifie zéro élément connu. Un examen planifié peut avoir `performed_at=null` et `report=null`. Les compteurs d'une étude peuvent être inconnus (`null`), sa dernière synchronisation absente ; `checked_at` reste l'instant de vérification. Les messages d'avertissement sont en français ; les codes stables servent au programme.

Rapports : une seule version courante par demande, plus grand numéro de version, tri décroissant de `reported_at` puis UUID. Observations : tri par système puis code. Examens : tri par accession puis UUID ; études : par UID. Le consommateur ne dépend pas de l'ordre des propriétés JSON. Deux rapports de la même demande ne doivent pas être fusionnés en perdant la provenance.

Laboratoire `available` : toutes les analyses demandées sont exploitables ; `partial` : au moins une attendue est manquante ou invalide ; `unavailable` : aucun rapport reçu pour les demandes attendues. Sans demande : `reports=[]`, `available` signifie aucune donnée attendue manquante, pas un résultat médical normal. Une valeur manquante/invalide est nulle et accompagnée d'un avertissement attaché au rapport et au code de l'analyse. Numérique disponible : nombre JSON fini, unité obligatoire, jamais une chaîne numérique.

Imagerie : `unavailable` si le contrôle PACS échoue ; sinon `incomplete` si une étude attendue manque ou est partielle ; sinon `available`. Sans examen : `studies=[]`, aucune image attendue. Une panne PACS ne transforme pas le laboratoire en indisponible. Un compte rendu final possède une date de validation postérieure ou égale à la réalisation de l'examen. Les tests d'intégration vérifieront ces relations ; le schéma seul ne prouve pas l'intégrité des données.

## Matrice minimale de droits proposée

| Action | physician | radiologist | lab_technician | admin |
|---|---|---|---|---|
| Identité minimale dans un contexte autorisé | Oui | Oui | Oui | Support limité |
| Lire les résultats biologiques | Oui | Oui | Oui | Non par défaut |
| Valider un résultat biologique | Non | Non | Oui | Non |
| Lire compte rendu et imagerie | Oui | Oui | Non par défaut | Non par défaut |
| Valider un compte rendu radiologique | Non | Oui | Non | Non |
| Gérer utilisateurs et rôles | Non | Non | Non | Oui |
| Audit technique global | Non | Non | Non | Oui |

Le technicien n'accède pas à la synthèse clinique complète. Une future route biologique dédiée ou une projection filtrée devra être spécifiée avant son écran. Administrer l'application ne donne pas automatiquement accès aux données cliniques.

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
| Rôle insuffisant pour la fonction | 403 |
| Ressource inexistante ou hors affectation | 404, même message générique |
| Réutilisation incohérente d'identifiant métier | 409 |
| Données d'entrée invalides | 422 |
| Base métier ou audit requis indisponible | 503 |
| Orthanc seul indisponible pendant la synthèse | 200 avec état dégradé |
| Accès au viewer impossible car PACS indisponible | 503 contrôlé |

Les réponses techniques ne contiennent ni traceback, ni payload HL7, ni mot de passe, ni adresse privée sensible. L'état HTTP du transport HL7 ne remplace jamais l'ACK applicatif défini dans son profil.

## Interfaces internes proposées

| Service | Entrée | Sortie ou effet |
|---|---|---|
| Identité : resoudre_patient | domaine et identifiant externe | UUID exact ou erreur d'identité |
| Laboratoire : ingerer_demande / ingerer_resultat | message validé et identité résolue | Écriture transactionnelle, identifiant de traitement |
| Laboratoire : lire_rapports_courants | UUID d'épisode autorisé | Bloc `laboratory` conforme au schéma, avertissements associés |
| Radiologie : lister_examens | UUID d'épisode autorisé | Bloc `radiology` conforme au schéma |
| Imagerie : verifier_disponibilite | Examens autorisés, budget temporel | Bloc `imaging`, avertissements et dates de vérification |
| Synthèse : composer_dossier | acteur et UUID d'épisode | Réponse commune, audit requis |
| Audit : enregistrer_evenement | acteur, action, ressource, résultat, corrélation | Trace minimale persistée |

Contrat d'appel T08 : autoriser via Membre 2, lire patient/épisode et blocs des Membres 3/4, composer et vérifier la réponse, persister l'audit via Membre 2, puis émettre. Erreur Orthanc seule : bloc dégradé ; erreur de base ou d'audit : 503. Les services de lecture n'écrivent pas dans les autres domaines. L'implémentation Python (synchrone/asynchrone, session SQL) sera fixée en T03/T08 sans modifier ces entrées/sorties publiques.

