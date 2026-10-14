# Configuration Orthanc

Lot E avec C. T01 fixe l'image `orthancteam/orthanc:26.9.1`, le stockage persistant, une authentification locale, l'AE Title `DEMOPACS`, le port DICOM `4242` et le port REST `8042` dans le [Compose](../compose.yaml). Les ports sont liés uniquement à `127.0.0.1`. Le simulateur de modalité et sa liste de pairs sont à mettre en place en T07.

Le choix d'un plugin DICOMweb ou viewer dépend de D14. Ne pas exposer l'administration Orthanc au navigateur ni laisser les contrôles désactivés par défaut.

La base métier PostgreSQL n'est pas une invitation à configurer l'index Orthanc dans les mêmes tables.

