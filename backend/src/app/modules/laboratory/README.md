# Module laboratory

Lot B.

Responsabilité : Demandes, rapports, observations et corrections biologiques.

Tables : lab_order, lab_report, lab_observation ; inbound_message avec l'adaptateur.

Le service `service.py` implémente `ingest_order`, `ingest_result` et `get_encounter_reports` pour le panneau synthétique du manifeste. Chaque ingestion valide le contexte patient/rencontre et les codes/unités attendus, puis valide sa transaction avant de retourner un reçu. L'adaptateur HL7 de T05 calcule le SHA-256 des octets reçus, parse le profil et convertit les erreurs `LaboratoryError` en ACK.

Invariants vérifiés sur SQLite : CRP manquante explicitement nulle ; zéro disponible conservé ; corrections versionnées sans écraser l'ancienne version ; rejeu exact sans duplication ; conflit même identifiant/autre contenu ; absence d'écriture dans les tables d'identité. La migration `0002_domains` a été appliquée et comparée aux modèles sur SQLite. PostgreSQL et les réceptions concurrentes restent à vérifier.

