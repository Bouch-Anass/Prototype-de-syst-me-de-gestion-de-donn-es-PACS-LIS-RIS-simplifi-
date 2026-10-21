# Contrat radiologie et imagerie

## Trois objets distincts

- La demande radiologique exprime l'examen demandé et porte l'accession.
- L'examen représente sa réalisation et ses états.
- L'étude d'imagerie référence les objets DICOM dans Orthanc.

Un compte rendu peut être absent alors qu'une étude est présente, et inversement. L'interface ne doit pas confondre « images disponibles » et « compte rendu validé ».

## Import initial

Le simulateur de modalité importe un jeu DICOM synthétique dans Orthanc par C-STORE. La configuration des AE Titles, du port DICOM et des pairs autorisés sera livrée avec l'environnement local.

Le backend utilise l'API REST privée Orthanc pour le rapprochement et l'état. Il ne consulte pas directement son stockage sur disque ou son index interne.

## Rapprochement

| Clé | Usage | Règle |
|---|---|---|
| PatientID et domaine d'identification convenu | Identité | Doit correspondre au patient de la rencontre |
| AccessionNumber | Demande radiologique | Doit identifier la demande attendue |
| StudyInstanceUID | Identité de l'étude | Stable et unique ; pas un identifiant patient |
| ID interne Orthanc | Accès technique au PACS | Peut être conservé côté serveur, pas utilisé comme identité clinique |
| UUID d'examen | Relation métier | Lie l'étude au RIS |

Si le jeu DICOM ne transporte pas l'autorité d'identification, l'importateur du scénario mono-source utilise le domaine `DEMO` fixé dans le [manifeste](../data/fixtures/scenario.json), puis confronte `PatientID`, accession et Study Instance UID à la [fixture de métadonnées](../data/dicom/study-metadata.json). Il ne faut pas inventer un domaine différent dans chaque lot.

L'absence ou la contradiction d'une clé bloque le rattachement automatique. Une fonctionnalité de résolution manuelle contrôlée pourra être ajoutée ; ce n'est pas une association arbitraire par nom.

## Disponibilité

| État | Sens |
|---|---|
| `available` | Étude accessible selon la vérification définie |
| `incomplete` | L'attente du scénario n'est pas satisfaite ou la complétude reste non établie |
| `unavailable` | Accès impossible à l'instant de contrôle, même si une référence existe |

Pour les fixtures, le manifeste fixe le nombre attendu de séries et d'instances. Cette méthode de démonstration ne constitue pas une preuve générale de fin d'acquisition clinique.

Chaque état est accompagné d'un instant de contrôle ou de dernière synchronisation. Une donnée ancienne ne doit pas être affichée comme une vérification instantanée.

## Accès au viewer

Pour le scénario T10, `viewer-link` retourne le chemin local d'un aperçu PNG servi par le backend. La route `/preview` vérifie de nouveau session, rôle, accès à la rencontre et disponibilité ; elle ne transmet aucun credential Orthanc. Le PNG est borné à 8 Mio et marqué `Cache-Control: no-store`. Cet aperçu non diagnostique couvre seulement une instance de l'étude ; ce n'est pas un viewer DICOM complet. L'[API Orthanc officielle](https://orthanc.uclouvain.be/book/users/rest.html) décrit le rendu PNG de `/instances/{id}/preview`.

Une URL non devinable ne suffit pas comme contrôle d'accès. La requête d'image doit vérifier l'autorisation ou un jeton temporaire strictement limité, selon la stratégie retenue.

DICOMweb et ses plugins ne sont pas nécessaires pour cette première démonstration. Le rendu avec l'image Orthanc réelle reste à vérifier.

## Tests obligatoires

Import correct, accession inconnue, patient contradictoire, Study Instance UID déjà connu, étude partielle, PACS arrêté, timeout, accès interdit et absence de secret côté navigateur.

