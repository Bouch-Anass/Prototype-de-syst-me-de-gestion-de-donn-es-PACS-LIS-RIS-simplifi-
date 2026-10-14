# Fixtures HL7 synthétiques

Le [profil local](../../contracts/hl7-profile.md) fixe HL7 v2.5.1 et le sous-ensemble OML^O21 / ORU^R01. Le [manifeste](../fixtures/scenario.json) fournit tous les identifiants, codes, unités et valeurs nominales. Les fichiers `*.hl7` sont générés par `py scripts/generate_hl7_fixtures.py` depuis la racine du dépôt. Leurs segments se terminent par l'octet `CR` (`0x0D`).

| Fichier | Usage |
|---|---|
| `order.oml.hl7` | demande du panneau biologique |
| `result.nominal.oru.hl7` | CRP 3.2 mg/L et glucose 4.8 mmol/L |
| `result.missing-crp.oru.hl7` | glucose présent, CRP attendue mais absente |
| `result.correction.oru.hl7` | nouvelle version du rapport, CRP corrigée à 3.4 mg/L |

Les ORU nominal et CRP absente sont des variantes indépendantes du même scénario : ne pas les ingérer successivement comme des corrections. Le message de correction est à ingérer après le nominal dans un scénario isolé. Les messages de rejeu conflictuel, patient inconnu et format mal formé seront ajoutés avec l'adaptateur T05, car leur comportement dépend du stockage transactionnel et du parseur effectif. Aucun message ni patient réel n'est utilisé.
