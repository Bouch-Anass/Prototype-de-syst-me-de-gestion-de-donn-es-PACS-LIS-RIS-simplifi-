# Vérifications du pack initial

**Mise à jour du 10 novembre 2026 :** la stack Docker comprend maintenant l'application, PostgreSQL 17 et Orthanc. Les trois services sont `healthy` ; le smoke test authentifié a réussi sur le dossier existant, avec laboratoire disponible, un examen RIS et aperçu PNG réel. Voir le [compte rendu Docker](DOCKER_FIX.md) pour le problème, la correction et les limites. Les sections datées ci-dessous décrivent les résultats historiques ; elles ne remplacent pas cette preuve plus récente.

Contrôles réalisés le 28 septembre 2026 avec Python 3.12.14.

| Vérification | Résultat |
|---|---|
| Présence des fichiers requis | Réussite |
| Résolution des liens Markdown locaux | Réussite |
| Parsing des quatre fichiers JSON | Réussite |
| Tests ciblés des exemples | 13 tests réussis |
| Contrôles négatifs sur valeurs manquantes, identité, accession et rattachement | Réussite |

Ces vérifications concernent uniquement les documents et les données d'exemple. Elles ne prouvent pas le fonctionnement d'une API, l'intégration à Orthanc ou la conformité d'un message HL7.

Les diagrammes sont fournis en Mermaid, modifiables dans les fichiers Markdown et destinés au rendu GitHub. Leur rendu sur GitHub n'a pas été contrôlé ici.

Le workflow GitHub Actions est fourni mais n'a pas été exécuté à distance. Aucune application, base de données, instance Orthanc ou infrastructure Docker n'a été démarrée pour valider ce squelette.

Les six PDF existants n'ont pas été modifiés. Aucun commit, push, ticket ou dépôt GitHub distant n'a été créé.

## Contrôles T01/T02 — 13 octobre 2026

Sur Python 3.13.2, `python scripts/check_repo.py` a réussi et `python -m unittest discover -s tests/contract -v` a exécuté 17 tests avec succès. `node --check frontend/app.js` a réussi. Un serveur HTTP local a servi l'aperçu frontend et les trois mocks avec des réponses 200. Le YAML Compose a été parsé localement et ses trois ports sont liés à `127.0.0.1`. Les quatre fixtures HL7 générées sont terminées par `CR` et comparées au manifeste par les tests.

Docker n'est pas disponible sur ce poste : `docker compose config`, les healthchecks, la persistance des volumes et la connexion Orthanc restent à vérifier dans un environnement Docker. L'aperçu frontend a ensuite été inspecté dans Edge aux formats bureau et mobile : chargement des polices, absence de débordement horizontal à 390 px et affichage des états CRP absente/PACS indisponible. Le frontend statique utilise des mocks et ne prouve pas encore les droits, l'audit ou l'intégration métier.

## Socle T03 — 19 octobre 2026

`python -m unittest discover -s tests/backend -v` a exécuté 9 tests avec succès sur SQLite en mémoire : readiness, recherche exacte, rencontres accessibles, refus 401/403/404, blocage après échecs de connexion, contrôle CSRF à la déconnexion, expiration de session, refus de la lecture quand l'écriture d'audit échoue et refus d'un seed d'identité contradictoire. Une migration Alembic a été appliquée à une base SQLite temporaire ; `alembic check` n'a détecté aucun écart avec les modèles. La base temporaire a été supprimée après le contrôle. `python scripts/check_repo.py` a réussi.

Ce contrôle n'est pas une preuve d'exécution sur PostgreSQL. Docker et psycopg ne sont pas disponibles sur le poste de vérification ; la connexion réelle, la migration PostgreSQL et la persistance restent à essayer. Les parcours HL7, RIS, Orthanc, synthèse et frontend sur API ne sont pas couverts par T03.

## Domaine laboratoire T04 — 21 octobre 2026

`python -m unittest discover -s tests/backend -v` a exécuté 15 tests avec succès, dont cinq nouveaux tests métier laboratoire sur SQLite : rejeu exact et conflit, valeur manquante distincte de zéro, correction en nouvelle version, rejet des valeurs/codes/unités invalides et refus d'un rattachement contradictoire. Un sixième test a appliqué les migrations jusqu'à `0002_domains` dans une base SQLite temporaire ; `alembic check` n'a détecté aucun écart entre schéma et modèles. Les 17 tests de contrat, `python scripts/check_repo.py` et `git diff --check` ont également réussi.

Ces essais ne couvrent ni la réception HL7 réelle, ni des ingestions concurrentes sur PostgreSQL. Docker n'est pas disponible sur ce poste ; la validation PostgreSQL et la persistance des volumes restent ouvertes.

## Première tranche HL7 T05 — 21 octobre 2026

`python -m unittest discover -s tests/backend -v` a exécuté 21 tests avec succès, dont six nouveaux tests HTTP du profil local : demande et résultat, CRP absente, rejeu exact, correction, conflit d'identifiant, valeur mal formée, patient inconnu, authentification, limite de taille et échec de l'audit. Dans ce dernier cas, aucun ACK positif ni écriture métier ne subsiste. Les 17 tests de contrat restent réussis.

Le sender CLI n'a pas été essayé contre un serveur PostgreSQL réel. Les tests utilisent SQLite en mémoire et ne prouvent pas le comportement sous deux réceptions concurrentes, la configuration réseau du proxy, ni la persistance Docker.

## Première tranche Orthanc T07 — 21 octobre 2026

`python -m unittest discover -s tests/backend -v` a exécuté 33 tests avec succès, dont 12 nouveaux tests T07 sur SQLite et faux transport Orthanc : rapprochement, rejeu exact, patient/accession/modalité contradictoires, UID déjà lié, étude partielle puis complète, panne PACS avec conservation de la référence et du dernier bon instant, refus REST et échec d'audit. Les 17 tests de contrat, `python scripts/check_repo.py` et `git diff --check` ont aussi réussi.

Le générateur a créé localement un fichier DICOM synthétique avec pydicom 3.0.2. Un test séparé avec pynetdicom 3.0.4 a vérifié les tags et un C-STORE réussi vers un serveur DICOM de boucle locale (`python -m unittest discover -s tests/modality -v`, 1 test). Ces dépendances ont été installées dans un environnement isolé ; le workflow CI les installe explicitement.

Docker n'est pas disponible sur ce poste. Aucun C-STORE vers l'image Orthanc du Compose, appel REST réel, essai PostgreSQL concurrent ou parcours viewer n'a été validé. Au moment de ce contrôle, T06 n'était pas encore implémenté ; T07 utilisait un seed radiologique synthétique limité à la démonstration.

## Première tranche RIS T06 — 21 octobre 2026

`python -m unittest discover -s tests/backend -q` a exécuté 38 tests avec succès sur SQLite en mémoire, dont cinq nouveaux tests RIS : parcours demande → examen réalisé → compte rendu final, refus des transitions interdites, accès par rôle et rencontre, accession/date cohérentes et rollback si l'audit échoue. Le contrôle de migration existant n'a détecté aucun écart de schéma. Les 17 tests de contrat, `python scripts/check_repo.py` et `git diff --check` ont réussi.

Le service RIS est interne. Les routes HTTP envisagées dans le contrat ne sont pas exposées ; l'audit des refus à cette future frontière reste à réaliser. Aucun parcours PostgreSQL ni test de transitions concurrentes n'a été effectué. Le seed T07 n'utilise pas encore ce service.

## Tranches T06/T08–T12 — 21 octobre 2026

`python -m unittest discover -s tests/backend -q` a exécuté **46 tests réussis** sur SQLite, dont les nouvelles vérifications des routes RIS avec session et CSRF, de la synthèse issue de HL7/RIS/Orthanc, de la CRP absente, de la panne PACS, des refus de rôle/rencontre, de l'audit requis, de l'aperçu PNG contrôlé et des assets frontend servis par FastAPI. `node --check frontend/app.js`, les 17 tests de contrat, `python scripts/check_repo.py` et `git diff --check` ont réussi. Le test de migration existant n'a détecté aucun écart avec les modèles.

Le [guide de démonstration](DEMO.md) et `scripts/smoke_live.py` fournissent une procédure depuis un clone équipé de Docker. Au moment de ce contrôle, le parcours Docker n'était pas exécuté. Les vérifications PostgreSQL 18 locales sont consignées ci-dessous. L'aperçu PNG est une représentation de démonstration non diagnostique, pas un viewer DICOM complet.

## PostgreSQL 18 local — 21 octobre 2026

Un cluster PostgreSQL 18.1 temporaire, lié à `127.0.0.1:55432`, a été initialisé dans `.dist/pg-validation-18` pour cette vérification ; ce n'est pas l'image PostgreSQL 17 du Compose. Le pilote `psycopg[binary]==3.3.6` a été installé dans `.dist/pgdeps` hors Git. Sur une base de test vierge, `alembic upgrade head` puis `alembic check` ont réussi. Le test `tests/integration/test_postgres_concurrency.py` a validé les rejeux HL7 simultanés, l'unicité d'accession, les transitions RIS concurrentes, le rapprochement d'étude concurrent, puis login, synthèse et aperçu via l'API avec faux Orthanc. Un seul traitement métier a été conservé pour chaque course vérifiée.

Après un arrêt/redémarrage du cluster local, les compteurs `patient`, `lab_report` et `imaging_study` sont restés `1/1/1`. Le p95 de **30 lectures de synthèse après échauffement** était **0,058 s** sur cette configuration PostgreSQL 18 avec faux Orthanc ; il ne mesure pas le temps d'un Orthanc réel. `scripts/smoke_live.py` a réussi sur HTTP contre le backend lié à ce cluster, Orthanc étant absent : la synthèse conservait LIS/RIS et signalait l'imagerie indisponible.

Docker et les navigateurs automatisables ne sont pas disponibles dans cette session. L'image PostgreSQL 17, Orthanc Docker, le navigateur, les healthchecks Compose, cinq répétitions du parcours réel et le délai d'intégration HL7 nominal restent à vérifier. La procédure de [DEMO.md](DEMO.md) sert à réaliser ces essais sur un poste Docker.

## Docker Desktop — 9 novembre 2026

Sur Docker Desktop 4.93.0 avec moteur 29.8.1, `docker compose -f infra/compose.yaml up -d --build` a construit l'application et démarré PostgreSQL 17.11, Orthanc 26.9.1 et FastAPI. Les trois services sont devenus `healthy` ; `GET /health/ready` a répondu `{"status":"ready"}` depuis l'hôte. `seed-demo` et `seed-radiology-demo` ont chargé le patient, la rencontre et l'examen fictifs.

Les fixtures `order.oml.hl7` et `result.nominal.oru.hl7` ont reçu chacune HTTP 200 et `MSA|AA` contre l'application conteneurisée et PostgreSQL 17. Le simulateur a envoyé l'instance CT synthétique par C-STORE à Orthanc réel. `match-demo-study` puis `refresh-demo-study` ont renvoyé `availability_status: available`, avec une série et une instance.

À ce stade du démarrage initial, le parcours authentifié médecin, la finalisation RIS, l'aperçu PNG dans un navigateur, la panne PACS, la persistance des volumes après redémarrage et les métriques sur ce stack n'avaient pas encore été vérifiés. Les résultats PostgreSQL 18/faux Orthanc ci-dessus ne doivent pas être confondus avec ces vérifications Docker.

## Quatre rôles et données de test — 9 novembre 2026

Après ajout de la migration `0003_imaging_role`, le Compose PostgreSQL 17/Orthanc/FastAPI a été reconstruit et les trois services sont devenus `healthy`. `seed-demo-accounts` a créé quatre comptes fictifs avec mots de passe aléatoires hachés et accès explicite à `DEMO-E001`. Les secrets en clair sont dans `infra/.secrets/demo_accounts.json`, ignoré par Git.

`docker compose -f infra/compose.yaml run --rm app python -m unittest discover -s /app/tests/backend -q` : **48 tests réussis**. `py scripts/check_live_roles.py` : connexion des quatre rôles, lectures de LIS/RIS/PACS, refus HTTP 403 des écritures croisées et du médecin, correction LIS par le laboratoire, création/finalisation RIS par le radiologue, import DICOM et rapprochement Orthanc par l'imagerie, puis lecture de la nouvelle étude par le médecin : **tous les contrôles réussis**. Le contrôle a utilisé l'instance synthétique `data/generated/demo-002-ct.dcm` et n'a pas imprimé les mots de passe.

`node --check frontend/app.js` a réussi. L'interface a été ouverte dans un navigateur sur `http://127.0.0.1:8000/frontend/` ; le passage en mode **API locale** a affiché les champs de connexion. Le parcours visuel complet après connexion reste à vérifier. L'aperçu PNG et les changements en base ont été vérifiés via HTTP ; aucune performance représentative ni persistance des volumes après redémarrage n'est revendiquée.

## CT externe converti localement — 9 novembre 2026

Le fichier CT fourni par l'utilisateur, `ct-lung-screening-nlst-instance.dcm` (526 502 octets), a été lu en montage Docker **lecture seule**. Il possédait des identifiants patient et cinq tags privés, mais pas l'issuer ni le StudyID du scénario. Son upload direct avec `demo-imaging` a retourné HTTP 422 `INVALID_DICOM`, avant tout stockage Orthanc.

`scripts/prepare_demo_ct.py` a créé une copie DICOM locale par liste blanche de métadonnées et une image PNG de contrôle. Le PNG de cette tranche a été examiné sans texte incrusté visible ; cela ne certifie pas l'anonymisation. La copie garde 524 288 octets de pixels, possède zéro tag privé et ne contient pas les champs `InstitutionName`, `PatientBirthDate` ou `StudyDescription`. Elle reprend les identifiants du scénario `DEMO-ACC002` et une nouvelle série/SOP UID. L'upload par `demo-imaging` a retourné HTTP 201. La synthèse du médecin a ensuite montré l'étude `2.25.10102` avec **2 séries et 2 instances** dans Orthanc. L'aperçu de l'application affichait d'abord la série initiale 2×2 ; la sélection de la série au numéro le plus élevé a été ajoutée et vérifiée par un test ciblé. Après reconstruction des conteneurs, les **49 tests backend** ont réussi et l'aperçu authentifié du médecin a répondu HTTP 200 avec une image **512×512**. Les fichiers dérivés sont ignorés par Git ; la provenance exacte et les droits de réutilisation du fichier source ne sont pas documentés dans le dépôt.

## Interface unifiée et saisies extensibles — 10 novembre 2026

L'interface exige désormais l'authentification avant la recherche et restaure une session existante via `GET /api/v1/auth/me`. Le sélecteur « scénarios fictifs / API locale » a été retiré. Le formulaire du laboratoire accepte des analyses locales supplémentaires dans une version de rapport ; le backend limite chaque version à 200 observations et refuse les codes dupliqués. Le formulaire d'imagerie sélectionne plusieurs fichiers DICOM et les envoie un par un avec un résultat par fichier. La synthèse RIS affiche aussi la procédure demandée, la priorité et les états de la demande et de l'examen.

`docker compose -f infra/compose.yaml run --rm app python -m unittest discover -s /app/tests/backend -q` : **50 tests réussis**. `node --check frontend/app.js` et `git diff --check` ont réussi. Les trois conteneurs ont redémarré en état `healthy` ; `/health/ready` et `/frontend/` ont répondu. Dans le navigateur, la page actualisée présentait uniquement le formulaire de connexion, sans dossier visible avant authentification, et le champ DICOM autorisait une sélection multiple. La saisie visuelle complète après connexion et un lot DICOM multi-fichiers réel restent à vérifier manuellement.

## Retrait du badge d'en-tête — 11 novembre 2026

Le badge « Données fictives » et ses styles inutilisés ont été retirés du frontend à la demande de l'équipe. Le conteneur applicatif a été reconstruit ; les trois services sont redevenus `healthy`. La réponse HTTP de `/frontend/` ne contient plus `environment-badge` et conserve le formulaire de connexion. Les données restent synthétiques et la notice de démonstration reste affichée dans l'interface. Aucun test backend supplémentaire n'était nécessaire pour cette suppression visuelle.
