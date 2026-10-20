# Backend

Le service FastAPI (T03) fournit les sessions, la recherche exacte de patient, les rencontres accessibles et l'audit. Le domaine laboratoire T04 possède maintenant ses ingestions et sa projection internes, testées sur SQLite. Les adaptateurs HL7, Orthanc et la synthèse clinique restent à développer.

L'entrée est `src/app/main.py`. La migration `0001_t03` crée patient, rencontre, utilisateurs, rôles, accès par rencontre, sessions et audit. `0002_domains` ajoute les tables métier laboratoire, radiologie et imagerie ; seuls les services laboratoire sont actuellement implémentés. Aucun schéma n'est créé automatiquement lors des requêtes.

| Emplacement | Responsabilité |
|---|---|
| [core](src/app/core/README.md) | Configuration, erreurs et dépendances communes |
| [db](src/app/db/README.md) | Session, transactions et historique des migrations |
| [modules](src/app/modules/README.md) | Domaines métier |
| [integrations](src/app/integrations/README.md) | Frontières avec HL7 et Orthanc |

Routes, services et stockage sont séparés. Les objets ORM ne doivent pas être retournés directement au frontend avec tous leurs champs. Les contrats exposent seulement les informations autorisées.

## Démarrage local

Prérequis : Python 3.12+, PostgreSQL démarré selon [infra/README.md](../infra/README.md). Depuis la racine du dépôt, en PowerShell :

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
$env:APP_ENV = 'development'
$env:APP_ORIGIN = 'http://127.0.0.1:8000'
$dbPassword = (Get-Content -Raw infra/.secrets/postgres_password.txt).Trim()
$env:DATABASE_URL = "postgresql+psycopg://app:$dbPassword@127.0.0.1:5433/pacs_lis_ris"
Set-Location backend
$env:PYTHONPATH = 'src'
..\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
..\.venv\Scripts\python -m app.cli seed-demo
..\.venv\Scripts\python -m app.cli create-user --username demo-doctor --role physician
..\.venv\Scripts\python -m app.cli grant-encounter --username demo-doctor --encounter-id 20000000-0000-4000-8000-000000000001
..\.venv\Scripts\python -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-access-log
```

`create-user` demande un mot de passe d'au moins 12 caractères dans le terminal. Aucun compte ni mot de passe par défaut n'est livré. `seed-demo` est idempotent et lit uniquement le manifeste synthétique. Le rôle seul n'accorde aucun dossier : `grant-encounter` associe explicitement l'utilisateur à la rencontre. Un administrateur technique ne peut pas lire les données cliniques par son seul rôle.

Depuis un autre terminal, `GET http://127.0.0.1:8000/health/ready` doit retourner `{"status":"ready"}`. Pour se connecter, envoyer `POST /api/v1/auth/login` avec JSON `{"username":"demo-doctor","password":"..."}` et l'en-tête `Origin: http://127.0.0.1:8000`. Conserver les cookies du même client HTTP. Le cookie `app_session` est HttpOnly, SameSite=Lax ; le cookie `csrf_token` est lisible par le client et doit être transmis dans `X-CSRF-Token` avec la même origine pour les mutations authentifiées. En production, `APP_ENV=production` impose une origine HTTPS et le drapeau Secure.

`GET /api/v1/patients?identifier_domain=DEMO&identifier=DEMO-P001` recherche exactement le couple domaine/identifiant. `GET /api/v1/patients/{id}/encounters` retourne seulement les rencontres autorisées. Un identifiant inexistant donne 404 ; une ressource existante hors contexte donne 403. Une panne SQL ou d'audit donne 503 sans contenu clinique. Les événements d'audit conservent des UUID et codes d'action, jamais le mot de passe ni l'identifiant patient externe.

## Contrôles

Depuis la racine, après installation des dépendances :

```powershell
.\.venv\Scripts\python -m unittest discover -s tests/backend -v
.\.venv\Scripts\python -m unittest discover -s tests/contract -v
```

Les tests backend utilisent SQLite en mémoire uniquement sous `APP_ENV=test`. Le moteur applicatif local exige PostgreSQL et le pilote psycopg. La migration et ses tables doivent encore être vérifiées sur un poste avec Docker ; le contrôle local SQLite ne prouve pas le comportement PostgreSQL.

