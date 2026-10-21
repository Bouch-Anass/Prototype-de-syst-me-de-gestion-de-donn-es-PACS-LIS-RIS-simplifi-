# Adaptateur HL7

Lot B. `service.py` applique le [profil HL7](../../../../../contracts/hl7-profile.md) local DEMO-001 : segments stricts, identifiants et unités du manifeste, SHA-256 des octets reçus, corrélation exacte et ACK après commit. L'endpoint HTTP interne est dans `app.main`.

Le transport exige `Authorization: Bearer` avec `HL7_SERVICE_SECRET`, `Content-Type: application/hl7-v2; charset=utf-8` et une taille maximale de 64 KiB. L'absence de secret désactive l'endpoint. Les écritures du message et du domaine sont transactionnelles ; un échec d'audit empêche l'ACK positif. Les rejets laissent une trace technique séparée, sans payload clinique.

Les tests SQLite couvrent OML, ORU nominal, CRP manquante, correction, rejeu, conflit, patient inconnu, limite de taille et échec d'audit. Le transport MLLP, les rejouabilités concurrentes sur PostgreSQL et l'exposition réseau contrôlée restent à vérifier.

