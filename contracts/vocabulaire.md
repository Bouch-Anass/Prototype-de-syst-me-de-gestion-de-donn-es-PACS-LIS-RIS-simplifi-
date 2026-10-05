# Vocabulaire commun — contrat v0.1

Les champs machine préexistants sont conservés. Les libellés affichés et le nouveau code métier sont en français. `encounter` désigne un **épisode de soins**, pas une personne ni une demande.

| Identifiant machine | Libellé français |
|---|---|
| patient / encounter | Patient / Épisode de soins |
| laboratory / radiology / imaging | Laboratoire / Radiologie / Imagerie |
| report / observation / study | Compte rendu ou rapport / Observation / Étude |
| available / partial / unavailable | Disponible / Partiel / Indisponible |
| missing / invalid / incomplete | Résultat manquant / Donnée invalide / Incomplet |
| preliminary / final / corrected | Provisoire / Final / Corrigé |
| planned / performed / cancelled | Planifié / Réalisé / Annulé |
| physician / radiologist / lab_technician / admin | Médecin / Radiologue / Technicien de laboratoire / Administrateur |
| LAB_RESULT_MISSING | Résultat attendu non reçu |
| IMAGING_UNAVAILABLE | Imagerie temporairement indisponible |
| ACCESS_DENIED | Accès non autorisé |

Conventions des futurs services Python : `resoudre_patient`, `ingerer_demande`, `ingerer_resultat`, `lister_examens`, `verifier_disponibilite`, `composer_dossier`, `enregistrer_evenement`. Les noms ne définissent pas à eux seuls des signatures ou des autorisations.
