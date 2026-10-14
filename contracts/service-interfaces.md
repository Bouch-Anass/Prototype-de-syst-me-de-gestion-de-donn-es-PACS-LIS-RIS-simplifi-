# Interfaces internes du premier jalon

Contrat de coopération entre lots, à traduire en types Python lors de T03–T08. Les UUID sont internes ; les identifiants externes sont toujours accompagnés de leur domaine. Les services ne retournent pas d'objets ORM bruts.

| Service | Entrée minimale | Sortie / erreur |
|---|---|---|
| `identity.resolve_patient` | `{identifier_domain, external_id}` | `{patient_id}` ou `IDENTITY_UNKNOWN` |
| `identity.resolve_encounter` | `{patient_id, identifier_domain, external_id}` | `{encounter_id}` ou `ENCOUNTER_UNKNOWN` / `PATIENT_MISMATCH` |
| `laboratory.ingest_order` | `{source, control_id, content_hash, patient_id, encounter_id, placer_number, filler_number, panel_code}` | `{lab_order_id, replayed}` ou conflit ; transaction atomique |
| `laboratory.ingest_result` | mêmes clés de corrélation, `reported_at`, liste de `{coding_system, code, value_numeric, unit}` | `{lab_report_id, version, replayed}` ; observation manquante dérivée du manifeste |
| `radiology.get_encounter_exams` | `{encounter_id}` | examens et compte rendu courant selon [API](api.md) |
| `imaging.match_study` | `{patient_id, accession_number, study_instance_uid, modality}` | `{exam_id, imaging_study_id}` ou attente/rejet explicite |
| `imaging.get_availability` | `{exam_id, timeout_ms}` | `{availability_status, checked_at, studies}` |
| `summary.build_summary` | `{actor_id, encounter_id}` | objet du contrat JSON ou `ACCESS_DENIED` / `SERVICE_UNAVAILABLE` ; audit requis |
| `audit.record_event` | `{actor_id, action, resource_id, outcome, correlation_id}` | persistance ou échec bloquant pour opération clinique |

Les erreurs de domaine se convertissent aux codes HTTP dans les routes. Le parsing HL7 et les appels Orthanc restent dans leurs adaptateurs, qui appellent ces services métier. La matrice de droits du [contrat API](api.md) s'applique avant toute projection de dossier.
