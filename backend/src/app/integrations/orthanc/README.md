# Client Orthanc

Le client REST privé T07 suit le [contrat imagerie](../../../../../contracts/imaging.md). Il cherche une étude par `StudyInstanceUID` avec `POST /tools/find`, puis lit l'étude et ses séries avec `GET /studies/{id}` et `GET /series/{id}`. Il vérifie les IDs et métadonnées, compte les instances et applique un délai total aux appels successifs. Il ne suit aucune redirection pour éviter la transmission des identifiants Orthanc à une autre cible.

Les erreurs réseau, le délai et le refus d'authentification deviennent des codes Orthanc normalisés. Les identifiants d'administration restent dans les variables d'environnement du backend et ne sont jamais envoyés au frontend. Les tests utilisent un faux transport HTTP ; l'import réel dans l'instance Docker reste à vérifier.

