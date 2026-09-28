# Environnement local

Lot E. Ce dossier décrit le déploiement à construire en T01 ; il ne contient pas encore de Compose opérationnel.

| Service prévu | Exposition | Persistance |
|---|---|---|
| Interface / point d'entrée | Interface locale pendant le développement | Aucune donnée clinique |
| Backend | Interne ou interface locale selon lancement | PostgreSQL métier |
| PostgreSQL | Réseau privé ; port hôte seulement si nécessaire | Volume nommé |
| Orthanc | Réseau privé ; port de test local si nécessaire | Volume PACS séparé |
| Listener HL7 éventuel | Réseau privé de démonstration | Journal métier via backend |

La disponibilité d'un conteneur n'est pas la disponibilité du service. Les healthchecks et conditions de démarrage distinguent les deux.

Définir versions exactes, limites de temps, volumes, secrets, initialisation et commandes de tests. Ne pas utiliser un tag d'image flottant comme seul repère de reproductibilité.

Ne pas fournir une commande de purge automatique des données pour « réparer » un démarrage. Toute opération destructive doit être séparée et explicitement signalée.

