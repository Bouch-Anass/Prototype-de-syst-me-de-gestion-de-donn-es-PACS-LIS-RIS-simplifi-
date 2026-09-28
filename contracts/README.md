# Contrats d'intégration

Les contrats constituent la frontière commune entre les lots. Ils décrivent le premier jalon ; ce ne sont pas encore des spécifications OpenAPI ou des profils de conformité certifiés.

| Contrat | Usage |
|---|---|
| [API](api.md) | Routes, droits, réponses et erreurs |
| [HL7](hl7.md) | Réception, mapping métier, rejouabilité et ACK |
| [Imagerie](imaging.md) | Import, rapprochement, disponibilité et accès |
| [Exemples de synthèse](examples/README.md) | Mocks pour le frontend et cibles pour le backend |

## Règles communes

- JSON UTF-8 ; champs API en `snake_case`.
- UUID internes distincts des identifiants de systèmes externes.
- Dates seules en `YYYY-MM-DD` ; instants avec fuseau en ISO 8601.
- `null` signifie absence de valeur, pas chaîne vide ou nombre zéro.
- Les listes vides sont `[]`.
- Les états sont des valeurs machine stables ; le frontend traduit leur libellé.
- Les codes d'analyses incluent leur système ; les fixtures emploient le système local `DEMO`.
- Chaque erreur exploitable possède `code`, `message` et `correlation_id`.
- Une modification de champ partagé met à jour simultanément contrat, mocks et tests.
- L'absence d'une donnée ne doit jamais être maquillée en succès complet.

L'OpenAPI générée par FastAPI deviendra la référence exécutable lorsque les routes seront implémentées. Ce squelette n'en fournit pas une fausse version exhaustive.

