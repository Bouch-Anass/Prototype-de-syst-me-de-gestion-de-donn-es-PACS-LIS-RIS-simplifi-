# Démonstration entièrement conteneurisée

Depuis la racine du dépôt, sur un poste avec Docker Desktop et PowerShell :

```powershell
py scripts/init_local_env.py
docker compose -f infra/compose.yaml up -d --build --wait
docker compose -f infra/compose.yaml ps
```

L'application et l'interface sont sur `http://127.0.0.1:8000/frontend/`. Tous les ports publiés sont liés à la boucle locale. Le premier démarrage télécharge les images et installe les dépendances Python. Les commandes `run --rm app` ci-dessous utilisent le même environnement et les secrets Docker que le serveur, sans placer de mot de passe dans la ligne de commande.

## Préparer le scénario fictif

```powershell
docker compose -f infra/compose.yaml run --rm app python -m app.cli seed-demo
docker compose -f infra/compose.yaml run --rm app python -m app.cli seed-radiology-demo
docker compose -f infra/compose.yaml run --rm app python -m app.cli seed-demo-accounts
docker compose -f infra/compose.yaml run --rm app python -m app.cli complete-radiology-demo --username demo-radiologist
```

Les quatre comptes sont créés avec des mots de passe aléatoires. Ils sont stockés sous forme de hash `scrypt` dans PostgreSQL ; leurs mots de passe lisibles sont uniquement dans `infra/.secrets/demo_accounts.json` sur votre poste et ne sont jamais ajoutés à Git. Ouvrez ce fichier localement pour vous connecter. Le jeu de données est entièrement synthétique.

| Compte | Domaine en écriture | Autres domaines |
| --- | --- | --- |
| `demo-doctor` | Aucun | Lecture des trois domaines |
| `demo-lab` | Résultats LIS | Lecture RIS et imagerie |
| `demo-imaging` | Import DICOM et rapprochement PACS | Lecture LIS et RIS |
| `demo-radiologist` | Demandes, examens et comptes rendus RIS | Lecture LIS et imagerie |

Chaque compte doit aussi disposer d'un accès explicite à la rencontre `DEMO-E001`, accordé par `seed-demo-accounts`.

## Importer les résultats et l'image

```powershell
docker compose -f infra/compose.yaml run --rm app python /app/simulators/lis/send_hl7.py order.oml.hl7 --host app
docker compose -f infra/compose.yaml run --rm app python /app/simulators/lis/send_hl7.py result.nominal.oru.hl7 --host app
docker compose -f infra/compose.yaml run --rm app python /app/simulators/modality/generate_and_send.py --send --host orthanc
docker compose -f infra/compose.yaml run --rm app python -m app.cli match-demo-study
docker compose -f infra/compose.yaml run --rm app python -m app.cli refresh-demo-study
```

Le résultat `result.missing-crp.oru.hl7` remplace le résultat nominal **dans une base de scénario séparée** ; ne l'envoyez pas après le nominal. Les fixtures utilisent des identifiants fixes pour ce seul scénario.

## Vérifier

```powershell
py scripts/smoke_live.py --username demo-doctor
docker compose -f infra/compose.yaml ps
```

Dans le navigateur, se connecter comme `demo-doctor`, puis chercher `DEMO-P001`. Vérifier la CRP, le glucose, le compte rendu final et l'aperçu PNG. Pour tester l'indisponibilité PACS :

```powershell
docker compose -f infra/compose.yaml stop orthanc
py scripts/smoke_live.py --username demo-doctor
docker compose -f infra/compose.yaml start orthanc
```

La synthèse doit rester lisible pendant la panne avec l'imagerie indiquée indisponible. Attendre le retour à l'état `healthy` avant de revérifier l'aperçu. Pour examiner les erreurs : `docker compose -f infra/compose.yaml logs --tail=100 app orthanc postgres`.

`docker compose -f infra/compose.yaml down` arrête le projet **sans supprimer les volumes**. Les comptes et les données restent présents au prochain `up -d`. L'aperçu PNG est uniquement pédagogique et non diagnostique.

## Essayer les éditions depuis l'interface

Après connexion, recherchez `DEMO-P001`.

1. Avec `demo-lab`, modifiez la CRP à `5.1 mg/L` et le glucose à `4.6 mmol/L`. Le bouton **Ajouter une analyse** permet d'ajouter d'autres codes locaux, libellés, valeurs et unités (jusqu'à 200 observations par rapport). Enregistrez : un nouveau rapport versionné doit apparaître. Laisser la CRP vide produit un résultat manquant explicite.
2. Avec `demo-radiologist`, créez un nouvel examen avec l'accession `DEMO-ACC002` et un compte rendu fictif. Le formulaire utilise une modalité CT et finalise l'examen.
3. Générez un second fichier DICOM synthétique dans le répertoire local ignoré par Git :

```powershell
docker compose -f infra/compose.yaml run --rm app python /app/simulators/modality/generate_and_send.py --variant 2
```

4. Avec `demo-imaging`, importez `data/generated/demo-002-ct.dcm` depuis le formulaire PACS. Le champ accepte aussi une sélection de plusieurs fichiers `.dcm` ; chaque fichier est envoyé séparément (8 Mio maximum) et le formulaire affiche les réussites et échecs. Chaque instance doit correspondre au patient et à un examen RIS existant. Le fichier de cet exemple porte `PatientID=DEMO-P001`, `IssuerOfPatientID=DEMO`, `AccessionNumber=DEMO-ACC002` et `StudyInstanceUID=2.25.10102`. La nouvelle étude peut être marquée **incomplète** : le manifeste ne donne un nombre attendu de séries et d'instances que pour DEMO-001. Son aperçu pédagogique reste accessible.
5. Avec `demo-doctor`, vérifiez que les trois domaines sont lisibles et qu'aucun formulaire d'édition n'est proposé. L'API vérifie aussi les droits indépendamment de l'interface.

## Essayer un CT externe sur le scénario fictif

La route d'import refuse un DICOM dont les identifiants patient, rencontre et examen ne correspondent pas au scénario. Pour tester les pixels d'un CT externe sans ajouter ses métadonnées d'origine à Orthanc, créer une copie locale et examiner d'abord le PNG généré :

```powershell
$source = 'C:\chemin\vers\image-ct.dcm'
docker compose -f infra/compose.yaml run --rm --no-deps --volume "${source}:/input.dcm:ro" --volume "${PWD}\scripts:/app/scripts:ro" app python /app/scripts/prepare_demo_ct.py /input.dcm
```

Le script prépare `data/generated/demo-002-nlst-ct.dcm` et `data/generated/demo-002-nlst-review.png`. Il accepte uniquement un CT mono-image non compressé en 16 bits. Vérifier le PNG pour toute information incrustée dans les pixels et n'utiliser qu'une source dont la provenance et les droits de réutilisation sont connus. La copie conserve les pixels, retire les métadonnées non nécessaires et les tags privés, puis prend les identifiants `DEMO-P001`, `DEMO-ACC002` et `2.25.10102`. Après avoir créé l'examen `DEMO-ACC002` avec `demo-radiologist`, importer la copie avec `demo-imaging`. Le DICOM d'origine reste intact et n'est pas stocké dans Orthanc.
