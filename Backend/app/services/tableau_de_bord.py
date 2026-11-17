"""Tableaux de bord : la même application avec un filtre de périmètre appliqué CÔTÉ SERVEUR dans les requêtes.

ROOT : toute l'organisation, par service ; DIVISION : sa division, par rôle ; AGENT : ce qui le concerne.
Il n'y a plus de niveau SERVICE : le super administrateur a la vue d'ensemble par service, le chef de division la vue par rôle.
Les chiffres sont des agrégats : un super administrateur voit des nombres de fichiers, jamais leur contenu (il faut déverrouiller).
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.acces import condition_acces_fichiers
from app.core.permissions import NIVEAU_DIVISION, NIVEAU_ROOT, Principal
from app.db.metier import (
    AccesException,
    Agent,
    Division,
    Dossier,
    DocumentRole,
    RoleDivision,
    Service,
    User,
    UserRoleDivision,
)
from app.db.vecteur import Document
from app.schemas.document import RoleBrief
from app.schemas.tableau_de_bord import (
    AccesPonctuelBrief,
    ColonneRepartition,
    FichierBrief,
    Indicateur,
    LigneRepartition,
    Repartition,
    TableauDeBordOut,
)
from app.services import historique as historique_svc

SANS_ROLE = ~select(DocumentRole.document_id).where(DocumentRole.document_id == Document.id).exists()


def _compte(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _par(db: Session, colonne, *conditions) -> dict[int, int]:
    return dict(db.execute(select(colonne, func.count()).where(*conditions).group_by(colonne)).all())


def _ton(n: int, seuil_alerte: int | None = None) -> str:
    if n == 0:
        return "neutre"
    return "alerte" if seuil_alerte is not None and n >= seuil_alerte else "attention"


def _brief_fichiers(db: Session, rows: list[Document]) -> list[FichierBrief]:
    noms = {u.id: u.nom_utilisateur for u in db.scalars(select(User).where(User.id.in_({d.cree_par for d in rows if d.cree_par})))}
    dossiers = {d.id: d.nom for d in db.scalars(select(Dossier).where(Dossier.id.in_({d.dossier_id for d in rows})))}
    return [
        FichierBrief(id=d.id, titre=d.titre, dossier_id=d.dossier_id, dossier_nom=dossiers.get(d.dossier_id, ""), depose_par=noms.get(d.cree_par), depose_le=d.cree_le)
        for d in rows
    ]


def _derniers(db: Session, principal: Principal, n: int = 8):
    _, rows = historique_svc.lister_historique(db, principal, limit=n)
    return [historique_svc.to_out(r) for r in rows]


def _postes_vacants(db: Session, divisions: list[Division]) -> list[str]:
    chefs_d = {a.division_id for a in db.scalars(select(Agent).where(Agent.titre == "CHEF_DIVISION", Agent.actif.is_(True)))}
    return [f"Division « {d.nom} » : poste de chef de division vacant (le super administrateur assure l'intérim)." for d in divisions if d.actif and d.id not in chefs_d]


def construire(db: Session, principal: Principal) -> TableauDeBordOut:
    if principal.niveau == NIVEAU_ROOT:
        return _root(db, principal)
    if principal.niveau == NIVEAU_DIVISION:
        return _division(db, principal)
    return _agent(db, principal)


def _root(db: Session, principal: Principal) -> TableauDeBordOut:
    services = list(db.scalars(select(Service).order_by(Service.nom)))
    divisions = list(db.scalars(select(Division).order_by(Division.nom)))
    div_service = {d.id: d.service_id for d in divisions}
    actifs = Agent.actif.is_(True)
    fichiers = Document.corbeille_le.is_(None)
    nb_agents = _par(db, Agent.service_id, actifs)
    nb_fichiers = _par(db, Document.division_id, fichiers)
    nb_a_classer = _par(db, Document.division_id, fichiers, SANS_ROLE)
    lignes = []
    for s in services:
        ds = [d for d in divisions if d.service_id == s.id]
        a_classer = sum(nb_a_classer.get(d.id, 0) for d in ds)
        lignes.append(LigneRepartition(
            id=s.id, libelle=s.nom, sous_titre=s.site,
            valeurs={"divisions": len(ds), "agents": nb_agents.get(s.id, 0), "fichiers": sum(nb_fichiers.get(d.id, 0) for d in ds), "a_classer": a_classer},
            alerte=a_classer > 0,
        ))
    admins = db.scalar(select(func.count(User.id)).where(User.actif.is_(True), User.role.has(code="ADMIN"))) or 0
    alertes = []
    if admins < 2:
        alertes.append(f"Seulement {admins} super administrateur actif : prévoyez-en au moins deux (le compte racine est un point de défaillance unique).")
    alertes += _postes_vacants(db, divisions)
    sans_division = db.scalar(select(func.count(Agent.id)).where(actifs, Agent.division_id.is_(None))) or 0
    if sans_division:
        alertes.append(f"{sans_division} agent(s) actif(s) sans division : ils n'ont accès à aucun fichier.")
    verif = historique_svc.verifier_chaine(db)
    if not verif["ok"]:
        alertes.append(f"L'historique de traçabilité est ALTÉRÉ à partir de l'entrée n°{verif['premier_rang_invalide']}.")
    total_a_classer = sum(nb_a_classer.values())
    return TableauDeBordOut(
        niveau="ROOT", titre="Vue d'ensemble de la direction",
        indicateurs=[
            Indicateur(cle="services", libelle="Services actifs", valeur=sum(1 for s in services if s.actif)),
            Indicateur(cle="divisions", libelle="Divisions actives", valeur=sum(1 for d in divisions if d.actif)),
            Indicateur(cle="agents", libelle="Agents actifs", valeur=sum(nb_agents.values())),
            Indicateur(cle="fichiers", libelle="Fichiers", valeur=sum(nb_fichiers.values())),
            Indicateur(cle="a_classer", libelle="Fichiers à classer", valeur=total_a_classer, ton=_ton(total_a_classer)),
        ],
        repartition=Repartition(
            titre="Par service",
            colonnes=[ColonneRepartition(cle=c, libelle=l) for c, l in (("divisions", "Divisions"), ("agents", "Agents"), ("fichiers", "Fichiers"), ("a_classer", "À classer"))],
            lignes=lignes,
        ),
        alertes=alertes, derniers_changements=_derniers(db, principal),
    )


def _division(db: Session, principal: Principal) -> TableauDeBordOut:
    division = db.get(Division, principal.division_id)
    fichiers = Document.corbeille_le.is_(None)
    roles = list(db.scalars(select(RoleDivision).where(RoleDivision.division_id == division.id).order_by(RoleDivision.libelle)))
    agents_par_role = _par(db, UserRoleDivision.role_division_id, UserRoleDivision.role_division_id.in_([r.id for r in roles]))
    fichiers_par_role = _par(db, DocumentRole.role_division_id, DocumentRole.role_division_id.in_([r.id for r in roles]))
    nb_agents = db.scalar(select(func.count(Agent.id)).where(Agent.division_id == division.id, Agent.actif.is_(True))) or 0
    nb_fichiers = db.scalar(select(func.count(Document.id)).where(Document.division_id == division.id, fichiers)) or 0
    a_classer_rows = list(db.scalars(select(Document).where(Document.division_id == division.id, fichiers, SANS_ROLE, condition_acces_fichiers(db, principal)).order_by(Document.cree_le.desc()).limit(10)))
    nb_a_classer = db.scalar(select(func.count(Document.id)).where(Document.division_id == division.id, fichiers, SANS_ROLE)) or 0
    alertes = []
    if not roles:
        alertes.append("Aucun rôle défini dans cette division : créez le dictionnaire de rôles pour classer les fichiers.")
    return TableauDeBordOut(
        niveau="DIVISION", titre=f"Division « {division.nom} »", sous_titre="Vue par rôle",
        indicateurs=[
            Indicateur(cle="agents", libelle="Agents actifs", valeur=nb_agents),
            Indicateur(cle="roles", libelle="Rôles actifs", valeur=sum(1 for r in roles if r.actif)),
            Indicateur(cle="fichiers", libelle="Fichiers", valeur=nb_fichiers),
            Indicateur(cle="a_classer", libelle="Fichiers à classer", valeur=nb_a_classer, ton=_ton(nb_a_classer), lien="/dossiers?a_classer=1"),
        ],
        repartition=Repartition(
            titre="Par rôle",
            colonnes=[ColonneRepartition(cle="agents", libelle="Agents"), ColonneRepartition(cle="fichiers", libelle="Fichiers")],
            lignes=[LigneRepartition(id=r.id, libelle=r.libelle, sous_titre=None if r.actif else "Désactivé", valeurs={"agents": agents_par_role.get(r.id, 0), "fichiers": fichiers_par_role.get(r.id, 0)}) for r in roles],
        ),
        alertes=alertes, a_classer=_brief_fichiers(db, a_classer_rows),
        derniers_changements=_derniers(db, principal),
    )


def _agent(db: Session, principal: Principal) -> TableauDeBordOut:
    moi = principal.user.id
    division = db.get(Division, principal.division_id) if principal.division_id else None
    roles = list(db.scalars(select(RoleDivision).join(UserRoleDivision, UserRoleDivision.role_division_id == RoleDivision.id).where(UserRoleDivision.user_id == moi).order_by(RoleDivision.libelle)))
    mes = list(db.scalars(select(Document).where(Document.cree_par == moi, Document.corbeille_le.is_(None)).order_by(Document.cree_le.desc()).limit(5)))
    nb_mes = db.scalar(select(func.count(Document.id)).where(Document.cree_par == moi, Document.corbeille_le.is_(None))) or 0
    now = datetime.now(timezone.utc)
    exceptions = db.execute(
        select(AccesException, Document.titre).join(Document, Document.id == AccesException.document_id)
        .where(AccesException.user_id == moi, AccesException.active.is_(True), AccesException.expire_le > now).order_by(AccesException.expire_le)
    ).all()
    alertes = [] if division else ["Vous n'êtes rattaché à aucune division : demandez à votre administrateur de vous en affecter une."]
    if division and not roles:
        alertes.append("Aucun rôle ne vous est attribué : vos fichiers déposés seront « à classer » et vous ne verrez que les vôtres. Demandez un rôle.")
    return TableauDeBordOut(
        niveau="AGENT", titre="Mon espace", sous_titre=f"Division « {division.nom} »" if division else None,
        indicateurs=[
            Indicateur(cle="roles", libelle="Mes rôles", valeur=len(roles)),
            Indicateur(cle="fichiers", libelle="Fichiers déposés par moi", valeur=nb_mes),
            Indicateur(cle="acces", libelle="Accès ponctuels actifs", valeur=len(exceptions)),
        ],
        alertes=alertes, mes_roles=[RoleBrief(id=r.id, code=r.code, libelle=r.libelle) for r in roles], mes_fichiers=_brief_fichiers(db, mes),
        acces_ponctuels=[AccesPonctuelBrief(document_id=e.document_id, document_titre=t, expire_le=e.expire_le) for e, t in exceptions],
        derniers_changements=_derniers(db, principal, 5),
    )
