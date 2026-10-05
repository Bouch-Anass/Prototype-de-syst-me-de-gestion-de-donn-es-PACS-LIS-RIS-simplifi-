# Identifiants et scénario commun — proposition T02

Le [manifeste DEMO-001](../data/fixtures/scenario.json) est la source des valeurs de test. Il ne crée ni patient ni table. Le Membre 1 coordonne ses changements ; le Membre 6 aide à produire les jeux et chaque domaine implémente son import.

| Information | Valeur DEMO-001 | Liaison |
|---|---|---|
| Patient externe | `DEMO-P001`, domaine `DEMO` | Patient existant, couple unique |
| Épisode externe | `DEMO-E001`, domaine `DEMO` | Épisode existant du patient |
| Demande biologique | `DEMO-LAB001`, autorité `DEMO` | Numéro placeur, unique dans ce domaine |
| Référence LIS | `DEMO-LIS001`, autorité `DEMO-LIS` | Numéro remplisseur de la même demande |
| Bilan | `BILAN_DEMO`, système `DEMO` | Analyses CRP et GLU du manifeste |
| Accession radiologique | `DEMO-ACC001` | Demande radiologique de cet épisode |
| Étude DICOM | `2.25.10101` | Étude liée à l'examen ; distincte de l'identifiant Orthanc |

Les UUID internes se trouvent dans `ids` et servent aux clés étrangères. Ni le domaine ni l'épisode ne se déduisent d'un nom ou du dernier message reçu. Pas de conversion de casse, de troncature ou de suppression silencieuse des espaces : une entrée ne respectant pas la convention est refusée. Deux identifiants identiques de domaines différents ne désignent pas nécessairement le même patient.

Chaîne : PID-3.1 + PID-3.4 → patient ; PV1-19.1 + autorité → épisode → patient ; ORC/OBR → demande biologique de cet épisode. Imagerie : PatientID + IssuerOfPatientID → patient ; accession → demande → examen → épisode ; ces chemins doivent aboutir au même patient avant l'association du StudyInstanceUID.

## Écart assumé à soumettre en revue

Les PDF de semaine 1 décrivent `PAT-SIM-0007`, `ENC-2026-0091`, NFS/CRP. Le starter a introduit DEMO-001 et CRP/glucose. T02 conserve ce petit jeu comme premier essai technique et le signale dans D19 : le glucose sert de résultat conservé dans le cas CRP absente. Il ne représente pas une NFS. Avant la démonstration évaluée, l'équipe devra accepter cet écart ou ajouter le scénario NFS/CRP ; aucune équivalence clinique n'est revendiquée.

Les horodatages fixes du manifeste ne sont pas la date réelle d'exécution. Chaque test se déroule dans un jeu isolé. Les corrections utilisent un nouvel identifiant de message et un nouveau rapport ; le rejeu conserve l'identifiant et le contenu. Les générateurs réservent les identifiants fixes à DEMO-001, sans réutilisation dans d'autres études.
