# Environnement local T01

Le Compose [compose.yaml](compose.yaml) démarre PostgreSQL métier et Orthanc. Les images sont fixées à `postgres:17.11-bookworm` et `orthancteam/orthanc:26.9.1` (décision D15). Le backend et le frontend ne sont pas encore des services Compose.

## Prérequis et démarrage depuis un clone vierge

Installer Docker Desktop avec le moteur Compose V2 et Python 3.12 ou plus récent. Depuis la racine du dépôt :

```powershell
py scripts/init_local_env.py
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
```

Sous Linux/macOS, remplacer `py` par `python3`. Le script crée une fois les secrets aléatoires dans `infra/.secrets/`, ignoré par Git. Il ne remplace pas les secrets existants. Les identifiants sont dans ces fichiers locaux uniquement : utilisateur PostgreSQL `app`, base `pacs_lis_ris`, utilisateur Orthanc `demo`. Garder l'accès au répertoire limité au poste de développement ; les permissions Unix des fichiers sont `0600`.

## Services et contrôles

| Service | Adresse locale | Persistance | Healthcheck |
|---|---|---|---|
| PostgreSQL 17.11 | `127.0.0.1:5433` | volume nommé `postgres_data` | `pg_isready` |
| Orthanc 26.9.1 REST/UI | `http://127.0.0.1:8042` | volume nommé `orthanc_data` | sonde `/probes/test-aliveness.py` |
| Orthanc DICOM C-STORE | `127.0.0.1:4242`, AE Title `DEMOPACS` | même volume Orthanc | couvert par l'état du service Orthanc |

Les ports sont liés à `127.0.0.1` et ne sont pas publiés sur le réseau du poste. Orthanc requiert l'authentification même en local. L'interface d'administration Orthanc sert seulement aux essais techniques ; le frontend applicatif futur passera par le backend. Les images DICOM et les données SQL sont séparées. Le réseau Compose est privé au projet, sans exposition de ports supplémentaire.

Pour vérifier la disponibilité :

```powershell
docker compose -f infra/compose.yaml ps
docker compose -f infra/compose.yaml exec postgres pg_isready -U app -d pacs_lis_ris
```

Ouvrir ensuite `http://127.0.0.1:8042` avec l'utilisateur `demo` et le mot de passe présent dans `infra/.secrets/orthanc.secret.json`. Aucune donnée patient n'est initialisée par T01 ; l'insertion métier et les migrations relèvent de T03.

Pour arrêter sans perdre les données :

```powershell
docker compose -f infra/compose.yaml down
```

Les volumes nommés restent présents et sont réutilisés au prochain `up -d`. **Destructif, uniquement si la perte des données locales est voulue :** `docker compose -f infra/compose.yaml down --volumes`. La commande normale n'effectue jamais cette purge. Changer un secret PostgreSQL après l'initialisation du volume ne change pas automatiquement le mot de passe déjà enregistré ; prévoir une rotation explicite.

## Limites de la vérification

Le fichier Compose et les secrets peuvent être contrôlés statiquement sur tout poste Python. Le démarrage, les healthchecks et la persistance doivent être confirmés sur un poste avec Docker. Ce réseau local et ces mots de passe de démonstration ne constituent pas un déploiement clinique.
