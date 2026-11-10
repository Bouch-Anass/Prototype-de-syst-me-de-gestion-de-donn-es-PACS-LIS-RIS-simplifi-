# Mise en route Docker — 10 novembre 2026

## Problème constaté

La demande était de lancer le projet avec Docker. PostgreSQL et Orthanc étaient déjà actifs et `healthy`, mais le fichier Compose ne définissait aucun service pour l'API et le frontend. Le démarrage des services de données ne suffisait donc pas à rendre l'application web accessible.

Sur ce poste, `docker compose` était absent ; seul `docker-compose` 1.29.2 était installé. Cet ancien exécutable ne prend pas en charge le champ racine `name` du fichier Compose. L'accès au socket Docker nécessitait aussi une exécution autorisée hors du bac à sable de l'agent ; aucune permission du socket n'a été changée.

## Correction réalisée

- Ajout de [infra/Dockerfile](../infra/Dockerfile), basé sur Python 3.12, pour embarquer le backend, le frontend et les fixtures nécessaires.
- Ajout du service `app` dans [infra/compose.yaml](../infra/compose.yaml), avec attente des services de données sains, port local `8000`, redémarrage automatique et sonde `/health/ready`.
- Ajout de [infra/start_app.py](../infra/start_app.py) : lecture des secrets montés, configuration des connexions internes `postgres:5432` et `orthanc:8042`, migrations Alembic, puis lancement d'Uvicorn.
- Ajout de [.dockerignore](../.dockerignore) pour limiter le contexte de construction aux fichiers nécessaires. Les secrets locaux ne sont pas intégrés à l'image.
- Adaptation temporaire de la configuration pour Compose V1 : remplacement de `name` par `version: "3.8"`, chemins résolus et nom de projet conservé avec `-p pacs-lis-ris-local`. La commande Bash reproductible est dans le [guide infrastructure](../infra/README.md).

Le premier contrôle HTTP a révélé une erreur **500 sur la synthèse patient** : `data/dicom/study-metadata.json` manquait dans l'image. Le service d'imagerie lit ce fichier pour contrôler le scénario. La correction a ajouté ce fichier au contexte autorisé et au Dockerfile. L'image a ensuite été reconstruite et seul le conteneur `app` a été remplacé.

Les volumes PostgreSQL et Orthanc, les comptes existants et les mots de passe locaux ont été conservés. Aucun compte n'est créé automatiquement au démarrage.

## Résultat vérifié

| Contrôle | Résultat observé |
| --- | --- |
| Conteneurs `app`, `postgres`, `orthanc` | Tous `healthy` |
| `GET /health/ready` | `200`, `{"status":"ready"}` |
| `GET /frontend/` | `200` |
| Connexion avec le compte local `demo-doctor` | Réussie |
| Recherche `DEMO-P001`, rencontre et synthèse | Réussies |
| Laboratoire | `available` |
| RIS | Un examen présent |
| Imagerie Orthanc | `available` |
| Aperçu PNG via l'API authentifiée | Signature PNG vérifiée |
| Déconnexion | Réussie |
| Vérification des liens/fichiers et `git diff --check` | Réussies |

Le parcours a été vérifié avec [scripts/smoke_live.py](../scripts/smoke_live.py), alimenté localement avec les identifiants existants sans les afficher. L'application est accessible à **http://127.0.0.1:8000/frontend/** : sélectionner **API locale**, puis rechercher `DEMO-P001` après connexion. Sur ce poste, les identifiants préexistants se trouvent dans `infra/.secrets/demo_accounts.json`, fichier ignoré par Git ; ce fichier n'est pas créé par `init_local_env.py`.

## Limites de cette preuve

Cette vérification réutilise une base et une étude Orthanc déjà initialisées. Elle ne prouve pas un démarrage depuis une base vierge, une nouvelle ingestion HL7 ou DICOM, cinq exécutions complètes successives, la persistance après arrêt de tous les services, ni les performances. Aucun parcours visuel automatisé dans un navigateur n'a été exécuté pendant cette intervention. Le PNG reste un aperçu de démonstration, pas un viewer diagnostique.

Voir le [guide de lancement](DEMO.md) et les [suggestions de présentation](DEMO_SUGGESTIONS.md).
