# Simulateur de modalité

T07 génère une instance CT synthétique de 2 × 2 pixels, dans une série et une étude, à partir du [manifeste commun](../../data/fixtures/scenario.json). Aucun fichier DICOM n'est versionné. Installer `requirements.txt` dans un environnement Python dédié, puis, depuis la racine du dépôt :

```powershell
python -m pip install -r simulators/modality/requirements.txt
python simulators/modality/generate_and_send.py
python simulators/modality/generate_and_send.py --send
```

`--send` transmet le fichier par C-STORE à `127.0.0.1:4242` (AE appelé `DEMOPACS`, AE appelant `DEMOMOD`). Le port peut être modifié avec `--port`. Démarrer d'abord l'[Orthanc local](../../infra/README.md). La sortie est `data/generated/demo-001-ct.dcm`, ignorée par Git. Le même StudyInstanceUID est volontairement réutilisé pour les essais isolés de DEMO-001 ; séparer ou réinitialiser les environnements de démonstration au besoin.

Le test `python -m unittest discover -s tests/modality -v` contrôle les tags, le fichier et un C-STORE vers un serveur DICOM de boucle locale. Ce test ne valide pas l'image Docker Orthanc. Aucune acquisition réelle ni acte clinique n'est simulé.

