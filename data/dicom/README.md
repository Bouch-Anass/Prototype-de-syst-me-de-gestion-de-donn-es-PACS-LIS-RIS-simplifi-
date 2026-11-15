# Fixtures DICOM

Le [simulateur de modalité](../../simulators/modality/README.md) génère un fichier DICOM CT exclusivement synthétique à partir du manifeste DEMO-001 : PatientID `DEMO-P001`, domaine `DEMO`, accession `DEMO-ACC001` et StudyInstanceUID `2.25.10101`. Une instance de 2 × 2 pixels occupe une série ; le manifeste attend donc une série et une instance. Les métadonnées attendues sont rappelées dans [study-metadata.json](study-metadata.json).

Le fichier généré va dans `data/generated/` et reste hors Git. Ces comptes prouvent seulement la complétude du scénario fictif ; ils ne prouvent pas la fin d'une acquisition clinique. N'ajouter aucun fichier téléchargé sans vérification de provenance, licence et données identifiantes.

## Images publiques de démonstration

Le [manifeste des échantillons](public-samples.json) référence trois fichiers de test distribués par pydicom. Les versions et empreintes SHA-256 sont fixées ; leur [provenance amont](https://raw.githubusercontent.com/pydicom/pydicom/v3.0.2/src/pydicom/data/test_files/README.txt) renvoie aux jeux de test NEMA WG04.

| Fichier | Modalité | Matrice | Examen fictif |
| --- | --- | --- | --- |
| `CT_small.dcm` | Scanner | 128 × 128 | `DEMO-ACC001` |
| `MR2_UNCR.dcm` | IRM | 1024 × 1024 | `DEMO-WEB-MR001` |
| `MR_small.dcm` | IRM | 64 × 64 | `DEMO-WEB-MR002` |

Sur l'installation native Windows déjà initialisée, avec les comptes de démonstration sauvegardés localement :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/load-demo-imaging.ps1
```

Le script démarre Orthanc 1.13.0 depuis la [distribution Windows officielle](https://orthanc.uclouvain.be/downloads/windows-64/orthanc/1.13.0/index.html), reconnecte le backend local, crée les deux examens IRM nécessaires et importe les images par l'API avec le rôle imagerie. Ouvrir `DEMO-P001`, puis **Imagerie → Afficher l’aperçu**. Les examens, études et instances utilisent des identifiants stables : relancer l'import ne crée pas de doublon.

Les originaux et leurs notices restent dans `data/local/dicom-sources/`. Les copies importables et les PNG de contrôle restent dans `data/generated/public-dicom/`. Ces répertoires sont ignorés par Git. Les pixels sont conservés ; les métadonnées sont reconstruites par liste blanche avec l'identité fictive, sans tags privés ni identité de la source. L'échographie initialement examinée a été écartée car elle contient du texte incrusté dans les pixels.

Les deux IRM sont des images de test isolées : elles restent indiquées comme partielles, le manifeste initial ne définissant une complétude attendue que pour `DEMO-ACC001`. Les aperçus restent accessibles. Les références de licence sont celles de [pydicom](https://github.com/pydicom/pydicom/blob/v3.0.2/LICENSE) et de [pydicom-data](https://github.com/pydicom/pydicom-data/blob/39a2eb31815eec435dc26c322c27aec5cfcbddb6/LICENSE) ; ces échantillons ne constituent pas des examens diagnostiques.

La préparation seule, sans serveur ni import, reste possible avec `python scripts/seed_public_dicom.py`. Examiner les PNG de contrôle avant d'ajouter toute autre source.

