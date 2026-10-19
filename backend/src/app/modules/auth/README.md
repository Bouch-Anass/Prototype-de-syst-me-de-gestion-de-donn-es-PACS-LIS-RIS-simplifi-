# Module auth

Lot A.

Responsabilité : Authentification, rôles et contrôle du contexte d'accès.

Tables : app_user, role, user_role.

Invariants : Un administrateur technique n'obtient pas automatiquement l'accès clinique.

T03 fournit les comptes créés localement sans identifiants par défaut, le hash scrypt, les rôles, les sessions opaques côté serveur, le blocage temporaire après échecs et le contrôle CSRF sur la déconnexion. Les droits cliniques exigent aussi un accès explicite à la rencontre.

