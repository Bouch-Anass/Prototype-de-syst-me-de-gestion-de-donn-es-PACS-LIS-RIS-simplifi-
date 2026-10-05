# Exemples de réponse

Mocks de `GET /api/v1/encounters/{id}/summary`, pour un utilisateur autorisé à consulter tout le dossier. Ce sont trois situations alternatives du même scénario, pas trois patients ou trois versions à importer simultanément.

| Fichier | Usage |
|---|---|
| [summary.nominal.json](summary.nominal.json) | Parcours normal, laboratoire et imagerie disponibles |
| [summary.missing-crp.json](summary.missing-crp.json) | CRP attendue manquante, glucose conservé |
| [summary.orthanc-unavailable.json](summary.orthanc-unavailable.json) | Référence d'étude connue mais images indisponibles |

Toutes les valeurs sont fictives. Aucune plage de référence, interprétation ou conclusion clinique n'est proposée.

Les identifiants proviennent du [manifeste commun](../../data/fixtures/scenario.json). Les horodatages sont fixes pour des tests reproductibles, pas des mesures récentes.

Le frontend peut utiliser ces fichiers sans attendre l'API. Les tests vérifient le [schéma public](../schemas/synthese.schema.json) et les invariants ciblés de DEMO-001. Les fixtures représentent trois alternatives, pas des mesures de disponibilité en direct. Elles ne remplacent ni l'OpenAPI future ni les tests du backend. Voir [les identifiants](../identifiants.md) pour l'écart documenté au scénario NFS/CRP des PDF.

