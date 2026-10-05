# Contrat d'accès — proposition T02 v0.1

Responsable de l'implémentation : Membre 2. Relecteurs : Membres 1, 4 et 5. Les choix ci-dessous sont proposés pour la démonstration locale, sans mécanisme déjà livré.

## Session du navigateur

- `POST /api/v1/auth/login` reçoit `username` et `password` ; succès 200 avec utilisateur minimal (`id`, `display_name`, `roles`), sans secret dans le JSON.
- Session opaque stockée côté serveur. Cookie `session_id`, HttpOnly, SameSite=Lax, Path=/, sans Domain ; Secure en HTTPS. Exception HTTP limitée à localhost et documentée dans T01. Pas de jeton de session dans le stockage JavaScript.
- Expiration proposée : 30 minutes d'inactivité et 8 heures au maximum. Connexion renouvelant l'identifiant de session ; déconnexion invalidant la session serveur et le cookie.
- `GET /api/v1/auth/session` renvoie l'utilisateur minimal et un jeton CSRF lié à la session ; 401 si session invalide. `POST /api/v1/auth/logout` renvoie 204.
- Toute écriture avec session exige un en-tête `X-CSRF-Token` valide et une origine autorisée. Login : contrôle d'origine et protection contre les tentatives répétées. Même origine pour frontend et API ; CORS fermé par défaut.

## Ressources et droits

Le Membre 2 fournit un service `verifier_acces(acteur, action, identifiant_episode)` utilisé par T08 et T10. Accès = utilisateur actif + rôle autorisé + affectation explicite au dossier. Proposition de stockage : association utilisateur/épisode, contrainte unique ; les comptes de démonstration reçoivent leurs affectations par seed. Aucune règle « tout médecin voit tout ».

Session absente ou expirée : 401. Rôle insuffisant pour une fonction : 403. Ressource inexistante ou hors affectation : 404 avec le même message générique. Refus audité côté serveur ; aucune donnée du dossier divulguée. Compte administrateur : gestion technique, sans droit clinique implicite.

Toute lecture clinique doit persister un événement d'accès avant émission de la réponse ; si l'audit requis échoue, réponse 503 sans données. Une écriture métier et son audit sont dans la même transaction. Un refus conserve sa trace hors d'une transaction métier annulée ; si l'audit du refus échoue, l'accès demeure refusé et une alerte technique minimale est produite. Un événement de lecture signifie « réponse autorisée préparée », pas preuve de réception par le navigateur.

## Images et services

Chaque requête d'image passe par l'API et vérifie de nouveau session et affectation. Le Membre 4 récupère l'image après ce contrôle, le Membre 5 utilise une URL applicative de même origine. Aucun lien direct à l'administration Orthanc. Le choix du viewer reste D14 ; il devra accepter ce mode d'accès ou faire évoluer le contrat en revue.

L'ingestion HL7 HTTP utilise un compte de service et un secret Bearer distinct, injecté hors Git via `HL7_SERVICE_SECRET`. Ce secret autorise une source connue, pas une identité déclarée arbitrairement dans MSH. Aucune session de navigateur n'autorise cet endpoint. Taille, délais et erreurs sont définis dans [le profil HL7](hl7.md).

Tests attendus dans T03/T10 : session expirée, rôle insuffisant, UUID connu mais hors affectation, CSRF absent, secret HL7 invalide, audit indisponible, accès à l'image après révocation de la session. T02 fournit ce contrat ; ces contrôles ne sont pas implémentés par ses tests de données.
