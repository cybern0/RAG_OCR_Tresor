# Contrôle d'accès (RBAC) à deux rôles : ADMIN et UTILISATEUR.
# Chaque action exige une permission (tables _role, permission, role_permission) ET un périmètre :
# le service de l'utilisateur (_user -> agent -> service_id).
# Refus par défaut : un utilisateur sans agent ou sans service n'a accès à aucun document.
