# Authentification déléguée au système (PAM sous Linux, LogonUser sous Windows) — l'application intermédiaire

Principe retenu avec l'encadreur : **les comptes et les mots de passe appartiennent au système
d'exploitation**, gérés par l'administrateur système (`useradd`, `passwd`, `groupadd` sous Linux ;
`net user`, `lusrmgr.msc` sous Windows). L'application ne crée ni comptes ni mots de passe OS : elle
**vérifie** le couple nom/mot de passe auprès du système — via **PAM** sous Linux, via **LogonUser**
(pywin32) sous Windows — puis donne accès aux dossiers de la GED en jouant le rôle d'intermédiaire.
Un seul référentiel d'identités, aucun mot de passe stocké côté application.

## Ce qui a changé dans l'application

| Élément | Mode `local` (défaut) | Mode `pam` |
|---|---|---|
| Vérification du mot de passe | hash scrypt dans `_user` | appel PAM (`services/auth_os.py`), le mot de passe n'est jamais lu ni stocké |
| Création des comptes app | interface + CLI (avec mot de passe) | **provisionnement automatique au premier accès** : profil minimal (rôle `UTILISATEUR`, sans agent), le super administrateur rattache ensuite l'agent et les rôles métier via l'interface |
| Comptes de démarrage | — | les comptes `source_compte = 'local'` (ex. le super administrateur créé au CLI) restent valables, pour ne jamais perdre l'accès |
| Modification du mot de passe | profil, admin, CLI | **refusée** (409) : elle se fait côté OS ; le nom d'utilisateur (identifiant OS) n'est pas renommable non plus |
| Jetons de session | liés au hash local | liés à une empreinte du nom OS (`empreinte_session`) — l'application ne pouvant pas détecter un changement de mot de passe OS, la durée de session reste bornée par `TOKEN_TTL_MINUTES` |

La table `_user` porte le nouveau `source_compte` (`local` | `os`) ; `mot_de_passe_hash` est devenu nullable
(NULL = mot de passe géré par le système). `POST /users` et la liste des comptes exposent `source_compte`.

## Installation sur le serveur Linux (comptes locaux)

1. Installer la dépendance : `uv sync` (ajoute `python-pam`).
2. Créer le service PAM `/etc/pam.d/tresor-ged` (nom configurable via `AUTH_OS_SERVICE`) :

```
# /etc/pam.d/tresor-ged — vérification des comptes locaux pour la GED
auth required pam_unix.so
account required pam_unix.so
```

3. Laisser l'API lire `/etc/shadow` : `pam_unix` le refuse à un service non privilégié. Deux options —
   donner la lecture au service de l'API (`setfacl -m u:<compte_api>:r /etc/shadow`, le plus simple) ou
   passer par SSSD (option retenue si l'on évolue vers l'annuaire, voir plus bas). Lancer l'API sous un
   **compte dédié** (jamais root) de toute façon.
4. Activer dans `.env` : `AUTH_MODE=pam`.
5. Créer un utilisateur OS de test (`useradd -m demo1 && passwd demo1`), démarrer l'API, se connecter à
   l'interface avec `demo1` et **le mot de passe Linux** : le profil applicatif est créé automatiquement,
   le super administrateur le rattache à un agent (division, rôles métier) depuis la gestion des comptes.

## Sécurité

- Le mot de passe saisi est transmis à PAM puis **oublié** : jamais journalisé, jamais mis en cache, jamais
  dans la base (seuls les événements `connexion.echec` / `connexion.reussie` sont tracés, sans secrets).
- Le blocage après 5 échecs (IP + nom, 5 minutes) s'applique aussi au mode pam — un attaquant ne peut pas
  forcer les mots de passe OS à travers l'application.
- En cas de panne de PAM, la connexion répond **503** avec un message clair (vérifier `/etc/pam.d/<service>`)
  au lieu d'un 401 trompeur ; les comptes locaux de secours restent disponibles.
- Le provisionnement automatique peut être désactivé (`AUTH_OS_AUTO_CREER=false`) : seuls les comptes
  préalablement créés par le super administrateur peuvent alors se connecter.

## Choix du serveur : Linux ou Windows/AD

Le code appelant est **le même** : `services/auth_os.py` choisit le mécanisme selon l'OS qui héberge l'API.

- **Serveur Linux (comptes locaux)** : la procédure ci-dessus suffit.
- **Serveur Windows 11** (démo complète sur une seule machine) : la vérification passe par `LogonUser`
  (pywin32) — le SAM local, ou l'annuaire du domaine si la machine y est jointe, valide lui-même le mot de
  passe. Sous Windows, le privilège « Agir comme partie du système d'exploitation » est requis pour valider
  des mots de passe (terminal Administrateur, service LocalSystem, ou `secpol.msc`). Domaine configurable
  via `AUTH_OS_DOMAIN` (« . » = comptes locaux). Installation pas à pas, comptes Windows et scénario de
  démonstration : **docs/demo_windows11.md**.
- **Serveur joint à un domaine Windows (Active Directory)** : sous Linux, joindre la machine (`realmd` +
  `sssd` : `realm join domaine.local`) et les utilisateurs se connectent avec **le même mot de passe que
  Windows** — c'est SSSD qui répond à PAM, aucune modification de l'application ; sous Windows, joindre la
  machine au domaine et régler `AUTH_OS_DOMAIN` sur son nom NetBIOS, LogonUser interroge alors l'annuaire.
- La brique SMB (accès Windows direct aux dossiers partagés) reste une décision ouverte : elle ne touche
  pas ce code, elle partagerait la même arborescence `storage/uploads/<division>/<dossier>/` avec les
  mêmes groupes.

## Limites connues (à assumer devant l'encadreur)

- Un changement de mot de passe OS n'invalide pas immédiatement les jetons déjà émis (l'application ne le
  voit pas) : la session expire au plus tard à la fin du TTL (`TOKEN_TTL_MINUTES`, 8 h par défaut).
- En comptes locaux, `pam_unix` exige l'accès à `/etc/shadow` : c'est la contrainte d'exploitation nº 1.
- La création des comptes OS reste hors de l'application (choix assumé : séparation des rôles, c'est
  l'administrateur système qui décide qui existe).
