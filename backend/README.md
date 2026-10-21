# Backend

Le service FastAPI (T03) fournit les sessions, la recherche exacte de patient, les rencontres accessibles et l'audit. Le domaine laboratoire T04 possède ses ingestions et sa projection internes. L'adaptateur HTTP HL7 T05 accepte les fixtures synthétiques OML/ORU et produit un ACK après commit. Le service RIS T06 gère les demandes, examens et comptes rendus validés avec routes HTTP protégées. T07 rapproche les études Orthanc, T08 compose la synthèse autorisée et T10 fournit les métadonnées et un aperçu PNG contrôlé.

L'entrée est `src/app/main.py`. La migration `0001_t03` crée patient, rencontre, utilisateurs, rôles, accès par rencontre, sessions et audit. `0002_domains` ajoute les tables métier laboratoire, radiologie et imagerie. Les services métier, leurs routes de lecture et les mutations RIS sont implémentés. Aucun schéma n'est créé automatiquement lors des requêtes.

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
$env:HL7_SERVICE_SECRET = (Get-Content -Raw infra/.secrets/hl7_service_secret.txt).Trim()
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
.\.venv\Scripts\python -m pip install -r simulators/modality/requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests/modality -v
```

Les tests backend utilisent SQLite en mémoire uniquement sous `APP_ENV=test`. Le moteur applicatif local exige PostgreSQL et le pilote psycopg. La migration et ses tables doivent encore être vérifiées sur un poste avec Docker ; le contrôle local SQLite ne prouve pas le comportement PostgreSQL.

## Synthèse, RIS et aperçu d'imagerie

`GET /api/v1/encounters/{id}/summary` demande une session médecin/radiologue et un accès explicite à la rencontre. Il compose les résultats biologiques courants, les examens RIS et l'état daté des études. Une panne Orthanc rend un HTTP 200 avec avertissement ; une panne de base ou d'audit requis rend HTTP 503 sans dossier. La lecture est auditée avant retour clinique.

Les routes RIS `POST /api/v1/radiology-orders`, `PATCH /api/v1/radiology-exams/{id}`, `PUT /api/v1/radiology-exams/{id}/report` et `POST /api/v1/radiology-exams/{id}/report/validate` exigent session, origine et en-tête CSRF. Le médecin ou radiologue autorisé crée une demande ; seul un radiologue autorisé peut marquer l'examen réalisé, écrire un brouillon et valider. Le rapport final est immuable dans ce schéma.

`GET /api/v1/imaging-studies/{id}` retourne les métadonnées autorisées. `GET /api/v1/imaging-studies/{id}/viewer-link` et la route `/preview` contrôlent à nouveau la session, les droits de rencontre et la disponibilité PACS. La route `/preview` renvoie au plus 8 Mio de PNG, avec `Cache-Control: no-store`. L'interface ne reçoit pas de credential Orthanc. Il s'agit d'un aperçu logiciel non diagnostique, pas d'un viewer DICOM complet. La [démonstration locale](../docs/DEMO.md) décrit l'enchaînement des commandes et le script de vérification.

## Envoyer les messages synthétiques HL7

Initialisez d'abord les secrets avec `python scripts/init_local_env.py` depuis la racine. Dans le terminal du backend, `HL7_SERVICE_SECRET` doit être chargé avant le lancement d'Uvicorn. Dans un autre terminal PowerShell, depuis la racine :

```powershell
$env:HL7_SERVICE_SECRET = (Get-Content -Raw infra/.secrets/hl7_service_secret.txt).Trim()
python simulators/lis/send_hl7.py order.oml.hl7
python simulators/lis/send_hl7.py result.nominal.oru.hl7
python simulators/lis/send_hl7.py result.correction.oru.hl7
```

Les réponses contiennent `MSA|AA|...` uniquement après commit. Un rejeu exact reçoit le même acquittement logique sans créer une seconde version ; une réutilisation d'ID avec d'autres octets reçoit HTTP 409 et `MSA|AR`. `result.missing-crp.oru.hl7` remplace le nominal dans un scénario isolé. L'endpoint `/internal/hl7/messages` exige le secret de service et ne doit pas être routé par un proxy public. Le secret n'est jamais envoyé au navigateur.

## Essayer le rapprochement Orthanc T07

Après le démarrage de PostgreSQL et d'Orthanc selon [infra](../infra/README.md), la migration et `seed-demo`, gardez les variables `APP_ENV`, `DATABASE_URL` et `PYTHONPATH` du terminal backend. Depuis `backend/`, créez la demande et l'examen synthétiques :

```powershell
..\.venv\Scripts\python -m app.cli seed-radiology-demo
```

Dans un autre terminal, depuis la racine, générez et envoyez l'unique instance DICOM :

```powershell
.\.venv\Scripts\python -m pip install -r simulators/modality/requirements.txt
.\.venv\Scripts\python simulators/modality/generate_and_send.py --send
```

De retour dans `backend/`, chargez localement les identifiants REST Orthanc et rapprochez l'étude. Le fichier secret est ignoré par Git ; ne copiez pas son contenu dans le code ou les logs.

```powershell
$orthancConfig = Get-Content -Raw ../infra/.secrets/orthanc.secret.json | ConvertFrom-Json
$env:ORTHANC_BASE_URL = 'http://127.0.0.1:8042'
$env:ORTHANC_USERNAME = 'demo'
$env:ORTHANC_PASSWORD = $orthancConfig.RegisteredUsers.demo
$env:ORTHANC_TIMEOUT_MS = '500'
..\.venv\Scripts\python -m app.cli match-demo-study
..\.venv\Scripts\python -m app.cli refresh-demo-study
```

Le premier appel lie le StudyInstanceUID à l'UUID d'examen si le PatientID, son domaine, l'accession et la modalité concordent. Le second retourne `available`, `incomplete` ou `unavailable`, `checked_at` et la date de dernière synchronisation. Une panne Orthanc conserve le rattachement existant et affiche un code d'avertissement. Ces commandes restent internes ; les routes de consultation T10 sont décrites plus haut. L'import réel dans l'image Docker, la persistance PostgreSQL et les cas concurrents doivent encore être validés sur un poste avec Docker.

