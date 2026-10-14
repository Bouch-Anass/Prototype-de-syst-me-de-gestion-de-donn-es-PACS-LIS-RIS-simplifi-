# Profil local HL7 v2.5.1 — DEMO-001

Ce profil est un **sous-ensemble de démonstration**, pas une certification de conformité générale. Il fixe les champs acceptés par le premier adaptateur et les fixtures de [data/hl7](../data/hl7/README.md). Les structures OML_O21 et ORU_R01 suivent les groupes de la [référence HL7 v2.5.1](https://www.hl7.eu/HL7v2x/v251/hl7v251msgstruct.htm).

## Enveloppe et transport

- Encodage UTF-8 ; segments terminés par `CR` (`0x0D`) ; pas d'enveloppe MLLP dans le fichier fixture.
- Délimiteurs `MSH-1 = |`, `MSH-2 = ^~\&` ; aucun séparateur non échappé dans une valeur libre.
- `MSH-9` : `OML^O21^OML_O21` ou `ORU^R01^ORU_R01` ; `MSH-11 = P` ; `MSH-12 = 2.5.1` ; `MSH-18 = UNICODE UTF-8`.
- `MSH-3/4` : `DEMO-LIS` / `DEMO` ; `MSH-5/6` : `PACS-RIS-LIS` / `DEMO`. `MSH-10` est unique pour cette source. `MSH-7` utilise `YYYYMMDDHHMMSS+0000`.
- Mode d'ACK original : `MSH-15/16` vides, un ACK applicatif `ACK^O21^ACK` ou `ACK^R01^ACK`. `MSA-1 = AA` seulement après commit, `AE` pour échec temporaire, `AR` pour rejet métier/profil ; `MSA-2` recopie `MSH-10`. Rejeu identique : même résultat logique, sans réécriture.
- Premier transport : `POST /internal/hl7/messages` sur le réseau local, `Content-Type: application/hl7-v2; charset=utf-8`, corps brut HL7 et authentification de service par en-tête `Authorization: Bearer`. L'endpoint reste hors du proxy public. Réponse : corps ACK du même type ; HTTP 200 si traité ou rejoué, 409 pour ID réutilisé avec un autre contenu, 422 pour profil/identité invalides, 503 pour stockage indisponible. Un échec d'authentification (401) ou de taille (413) intervient avant parsing, sans ACK. MLLP est reporté et devra réutiliser le pipeline métier.
- Taille maximale : 64 KiB. Le hash de déduplication SHA-256 porte sur les octets UTF-8 après retrait éventuel de l'enveloppe de transport, **sans normalisation des segments**.

## Segments acceptés

| Message | Ordre exact du sous-ensemble | Cardinalité locale |
|---|---|---|
| OML^O21 | `MSH PID PV1 ORC OBR` | un de chaque, aucun autre segment dans le premier jalon |
| ORU^R01 | `MSH PID PV1 OBR OBX...` | un de chaque sauf `OBX` : 1 à 2 |

| Champ | Règle locale | Usage métier |
|---|---|---|
| `PID-3` | `external_id^^^identifier_domain^MR` | résolution exacte du patient ; aucune création implicite |
| `PV1-19` | `encounter_external_id^^^identifier_domain` | rencontre existante de ce patient |
| `ORC-1` | `NW` | création de demande OML |
| `ORC-2`, `OBR-2` | `placer_number^DEMO` identiques | demande laboratoire |
| `ORC-3`, `OBR-3` | `filler_number^DEMO-LIS` identiques | résultat laboratoire |
| `OBR-4` | `LAB-PANEL^Panel demo^DEMO` | panneau du scénario |
| `OBR-25` | `F` dans ORU initial, `C` dans une correction | état du rapport |
| `OBX-2` | `NM` | valeur numérique finie |
| `OBX-3` | `code^display^DEMO` | code attendu dans le manifeste |
| `OBX-5` | nombre décimal non vide | valeur présente ; zéro reste une vraie valeur |
| `OBX-6` | unité du manifeste | unité attendue pour ce code |
| `OBX-11` | `F` dans le résultat initial, `C` dans une correction | état de l'observation |

Le manifeste [scenario.json](../data/fixtures/scenario.json) est la source unique des identifiants, du panneau, des codes et des unités. Le résultat nominal porte CRP et glucose. Dans la variante dégradée, seul l'OBX glucose est présent ; le domaine laboratoire crée une observation CRP `missing` avec valeur `null` et un avertissement. Un code inconnu, une unité contradictoire, une valeur non numérique, un patient ou une rencontre inconnus sont rejetés. La correction porte un nouveau `MSH-10`, le même couple `OBR-2/3`, `OBR-25=C` et `OBX-11=C` ; T04/T05 doivent créer une nouvelle version sans écraser la précédente. Les variantes nominale, manquante et corrigée sont des parcours isolés, pas une séquence à ingérer ensemble.
