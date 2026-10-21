# Fixtures DICOM

Le [simulateur de modalité](../../simulators/modality/README.md) génère un fichier DICOM CT exclusivement synthétique à partir du manifeste DEMO-001 : PatientID `DEMO-P001`, domaine `DEMO`, accession `DEMO-ACC001` et StudyInstanceUID `2.25.10101`. Une instance de 2 × 2 pixels occupe une série ; le manifeste attend donc une série et une instance. Les métadonnées attendues sont rappelées dans [study-metadata.json](study-metadata.json).

Le fichier généré va dans `data/generated/` et reste hors Git. Ces comptes prouvent seulement la complétude du scénario fictif ; ils ne prouvent pas la fin d'une acquisition clinique. N'ajouter aucun fichier téléchargé sans vérification de provenance, licence et données identifiantes.

