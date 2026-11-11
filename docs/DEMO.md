# Démonstration locale reproductible

Ce parcours utilise uniquement le patient fictif `DEMO-P001`. Les secrets restent dans `infra/.secrets/`, hors Git. Le navigateur accède au frontend et à l'API sur **la même origine** `http://127.0.0.1:8000` ; il ne reçoit jamais les identifiants Orthanc.

## Lancement entièrement Docker sur une installation déjà préparée

Depuis la racine du dépôt :

```bash
python3 scripts/init_local_env.py
docker compose -f infra/compose.yaml up -d --build
docker compose -f infra/compose.yaml ps
```

Attendre que `app`, `postgres` et `orthanc` soient `healthy`, puis ouvrir **http://127.0.0.1:8000/frontend/**. Se connecter avec `demo-doctor` et rechercher `DEMO-P001`. Les mots de passe restent locaux ; sur le poste préparé, ils sont dans `infra/.secrets/demo_accounts.json`. Sur un nouveau clone, suivre le [guide Docker complet](DOCKER.md) pour créer les comptes et charger le scénario.

Le [guide infrastructure](../infra/README.md) donne aussi la commande compatible avec `docker-compose` V1. Le service `app` applique les migrations mais ne crée ni comptes ni scénario. Le [compte rendu du 10 novembre](DOCKER_FIX.md) détaille la première mise en route ; les [suggestions de démonstration](DEMO_SUGGESTIONS.md) proposent un déroulé de présentation.

## Initialisation du scénario : parcours hybride

Les étapes suivantes utilisent Python 3.12+ sur l'hôte, PostgreSQL et Orthanc dans Docker, et des commandes PowerShell. Elles servent notamment à préparer les comptes et les données d'un clone vierge. Sous Linux/macOS, adapter les variables d'environnement et utiliser `.venv/bin/python`.

Si `app` est déjà lancé, l'arrêter avec `docker compose -f infra/compose.yaml stop app` avant de lancer Uvicorn sur l'hôte : les deux utilisent le port `8000`. À la fin du parcours, arrêter Uvicorn, puis lancer `docker compose -f infra/compose.yaml up -d --build app` pour revenir au mode entièrement Docker.

## 1. Initialiser les services

Depuis la racine du clone :

```powershell
py scripts/init_local_env.py
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml up -d postgres orthanc
docker compose -f infra/compose.yaml ps
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python -m pip install -r simulators/modality/requirements.txt
```

Attendre que PostgreSQL et Orthanc soient `healthy`. Aucun mot de passe de démonstration n'est stocké dans le dépôt.

## 2. Préparer le dossier et les comptes

Dans un terminal PowerShell depuis la racine :

```powershell
$env:APP_ENV = 'development'
$env:APP_ORIGIN = 'http://127.0.0.1:8000'
$env:HL7_SERVICE_SECRET = (Get-Content -Raw infra/.secrets/hl7_service_secret.txt).Trim()
$dbPassword = (Get-Content -Raw infra/.secrets/postgres_password.txt).Trim()
$env:DATABASE_URL = "postgresql+psycopg://app:$dbPassword@127.0.0.1:5433/pacs_lis_ris"
$orthancConfig = Get-Content -Raw infra/.secrets/orthanc.secret.json | ConvertFrom-Json
$env:ORTHANC_BASE_URL = 'http://127.0.0.1:8042'
$env:ORTHANC_USERNAME = 'demo'
$env:ORTHANC_PASSWORD = $orthancConfig.RegisteredUsers.demo
$env:ORTHANC_TIMEOUT_MS = '500'
Set-Location backend
$env:PYTHONPATH = 'src'
..\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
..\.venv\Scripts\python -m app.cli seed-demo
..\.venv\Scripts\python -m app.cli seed-radiology-demo
..\.venv\Scripts\python -m app.cli create-user --username demo-doctor --role physician
..\.venv\Scripts\python -m app.cli create-user --username demo-radiologist --role radiologist
..\.venv\Scripts\python -m app.cli grant-encounter --username demo-doctor --encounter-id 20000000-0000-4000-8000-000000000001
..\.venv\Scripts\python -m app.cli grant-encounter --username demo-radiologist --encounter-id 20000000-0000-4000-8000-000000000001
..\.venv\Scripts\python -m app.cli complete-radiology-demo --username demo-radiologist
..\.venv\Scripts\python -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log
```

`create-user` demande chaque mot de passe sans l'afficher. Conserver le serveur actif dans ce terminal. Lors d'une répétition, `seed-demo`, `seed-radiology-demo` et `complete-radiology-demo` ne créent pas de doublons ; ne recréez pas les comptes existants.

## 3. Envoyer les données synthétiques

Dans un second terminal depuis la racine :

```powershell
$env:HL7_SERVICE_SECRET = (Get-Content -Raw infra/.secrets/hl7_service_secret.txt).Trim()
.\.venv\Scripts\python simulators/lis/send_hl7.py order.oml.hl7
.\.venv\Scripts\python simulators/lis/send_hl7.py result.nominal.oru.hl7
.\.venv\Scripts\python simulators/modality/generate_and_send.py --send
```

Les messages HL7 répétés à l'identique sont des rejeux sans nouvelle version. Pour rapprocher l'étude après C-STORE, retourner au premier terminal, arrêter Uvicorn avec Ctrl+C, puis lancer :

```powershell
..\.venv\Scripts\python -m app.cli match-demo-study
..\.venv\Scripts\python -m app.cli refresh-demo-study
..\.venv\Scripts\python -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log
```

## 4. Consulter et vérifier

Ouvrir `http://127.0.0.1:8000/frontend/`, se connecter avec `demo-doctor`, puis rechercher `DEMO-P001`. La synthèse doit montrer le rapport biologique, l'examen RIS validé et l'étude d'imagerie. Si Orthanc est disponible, **Afficher l’aperçu** charge une image PNG via une route contrôlée par la session. Cet aperçu sert uniquement à la démonstration logicielle et n'est pas diagnostique.

Le contrôle automatisé du même parcours se lance dans un troisième terminal depuis la racine :

```powershell
.\.venv\Scripts\python scripts/smoke_live.py --username demo-doctor
```

Le script demande le mot de passe, vérifie readiness, recherche exacte, rencontre, synthèse et aperçu disponible, puis se déconnecte. Il n'accepte qu'une origine HTTP de boucle locale.

## 5. Modes dégradés et persistance

Pour vérifier la dégradation PACS, arrêter Orthanc sans effacer son volume :

```powershell
docker compose -f infra/compose.yaml stop orthanc
```

Recharger la synthèse : le backend doit répondre 200, conserver les données LIS/RIS et signaler l'imagerie indisponible. Relancer Orthanc avec `docker compose -f infra/compose.yaml start orthanc`, attendre `healthy`, puis relancer le contrôle. Le cas CRP absente est couvert par les tests automatisés et nécessite une base de scénario isolée si on veut le montrer sans conflit avec le message nominal déjà ingéré.

Pour vérifier la persistance, utiliser `docker compose -f infra/compose.yaml down`, puis `up -d` et relancer `scripts/smoke_live.py` après le retour des services. La commande normale `down` conserve les volumes. **Ne pas ajouter `--volumes`** si vous voulez garder les données.

Le 10 novembre 2026, les trois services Docker ont été vérifiés sains et le smoke test a réussi sur les données existantes, jusqu'à l'aperçu PNG avec Orthanc réel. L'initialisation complète depuis un clone vierge, les nouvelles ingestions, les modes dégradés et la persistance après arrêt de toute la stack restent à vérifier dans ce parcours. Voir les [preuves et limites](DOCKER_FIX.md) et l'[historique des vérifications](VERIFICATIONS.md).
