# Environnement local T01

Le Compose [compose.yaml](compose.yaml) démarre PostgreSQL métier, Orthanc et le service `app` (API FastAPI et frontend sur la même origine). Les images de base sont fixées à `postgres:17.11-bookworm`, `orthancteam/orthanc:26.9.1` et `python:3.12-slim`. L'application lit les secrets montés dans `/run/secrets`, applique les migrations Alembic au démarrage, puis démarre Uvicorn.

## Prérequis et démarrage depuis un clone vierge

Installer Docker Desktop avec le moteur Compose V2 et Python 3.12 ou plus récent. Depuis la racine du dépôt :

```powershell
py scripts/init_local_env.py
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml up -d --build
docker compose -f infra/compose.yaml ps
```

Sous Linux/macOS, remplacer `py` par `python3`. Le script crée une fois les secrets aléatoires dans `infra/.secrets/`, ignoré par Git. Il ne remplace pas les secrets existants. Les identifiants sont dans ces fichiers locaux uniquement : utilisateur PostgreSQL `app`, base `pacs_lis_ris`, utilisateur Orthanc `demo`. Garder l'accès au répertoire limité au poste de développement ; les permissions Unix des fichiers sont `0600`.

Ouvrir **http://127.0.0.1:8000/frontend/**, se connecter, puis rechercher `DEMO-P001`. Les comptes et données existants sont conservés ; un clone vierge doit charger le scénario selon le [guide Docker](../docs/DOCKER.md). Le service ne crée pas automatiquement de comptes.

Sur un poste Linux équipé uniquement de l'ancien exécutable `docker-compose` 1.29, utiliser cette commande Bash depuis la racine (elle adapte seulement le champ de nom du projet à Compose V1) :

```bash
docker-compose -p pacs-lis-ris-local --project-directory "$PWD/infra" \
  -f <(sed 's/^name: pacs-lis-ris-local$/version: "3.8"/' infra/compose.yaml) up -d --build
```

## Services et contrôles

| Service | Adresse locale | Persistance | Healthcheck |
|---|---|---|---|
| PostgreSQL 17.11 | `127.0.0.1:5433` | volume nommé `postgres_data` | `pg_isready` |
| Orthanc 26.9.1 REST/UI | `http://127.0.0.1:8042` | volume nommé `orthanc_data` | sonde `/probes/test-aliveness.py` |
| Orthanc DICOM C-STORE | Port `4242` sur le réseau Compose uniquement, AE Title `DEMOPACS` | même volume Orthanc | couvert par l'état du service Orthanc |
| Application et frontend | `http://127.0.0.1:8000/frontend/` | données dans PostgreSQL/Orthanc | `/health/ready` |

Les ports sont liés à `127.0.0.1` et ne sont pas publiés sur le réseau du poste. Orthanc requiert l'authentification même en local. L'interface d'administration Orthanc sert seulement aux essais techniques ; le frontend applicatif passe par le backend. Les images DICOM et les données SQL sont séparées. Le réseau Compose est privé au projet, sans exposition de ports supplémentaire.

Pour vérifier la disponibilité :

```powershell
docker compose -f infra/compose.yaml ps
docker compose -f infra/compose.yaml exec postgres pg_isready -U app -d pacs_lis_ris
```

Ouvrir ensuite `http://127.0.0.1:8000/frontend/`. La procédure [Docker complète](../docs/DOCKER.md) initialise le dossier fictif, les comptes, les messages HL7 et l'étude DICOM. Orthanc reste accessible en local sur `http://127.0.0.1:8042` avec les identifiants de `infra/.secrets/orthanc.secret.json` pour les essais techniques.

Pour arrêter sans perdre les données :

```powershell
docker compose -f infra/compose.yaml down
```

Les volumes nommés restent présents et sont réutilisés au prochain `up -d`. **Destructif, uniquement si la perte des données locales est voulue :** `docker compose -f infra/compose.yaml down --volumes`. La commande normale n'effectue jamais cette purge. Changer un secret PostgreSQL après l'initialisation du volume ne change pas automatiquement le mot de passe déjà enregistré ; prévoir une rotation explicite.

## Limites de la vérification

Le 10 novembre 2026, les trois services et le parcours HTTP authentifié jusqu'à l'aperçu PNG ont été vérifiés. Les ingestions HL7 et DICOM ont également été testées sur le Compose. La persistance des volumes Docker après arrêt/redémarrage et les mesures de performance restent à vérifier. Voir les [vérifications](../docs/VERIFICATIONS.md) et le [compte rendu de mise en route](../docs/DOCKER_FIX.md). Ce réseau local et ces mots de passe de démonstration ne constituent pas un déploiement clinique.
