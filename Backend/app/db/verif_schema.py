"""Contrôle au démarrage : la base a-t-elle les colonnes que le code lit ?

Sans ce contrôle, une base créée avec un ancien schéma répond par des erreurs 500 cryptiques
(« la colonne … n'existe pas ») dès qu'on liste les fichiers. On préfère s'arrêter net en disant quoi faire :
recréer la base vierge avec les scripts de database/ (il n'y a pas de script de migration).
"""

from sqlalchemy import text

from app.db.vecteur import DocumentVersion

_SCRIPT = "database/01_schema.sql"


def colonnes_manquantes(engine) -> dict[str, str]:
    """{colonne manquante de document_version: script qui la crée} (vide si la base est à jour)."""
    table = DocumentVersion.__table__
    with engine.connect() as conn:
        presentes = {
            r[0]
            for r in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :t AND table_schema = :s"),
                {"t": table.name, "s": table.schema or "public"},
            )
        }
    return {c.name: _SCRIPT for c in table.columns if c.name not in presentes}


def verifier_schema(engine) -> None:
    manquantes = colonnes_manquantes(engine)
    if not manquantes:
        return
    raise RuntimeError(
        "La base de données n'est pas conforme au schéma : colonnes manquantes dans document_version : "
        f"{', '.join(sorted(manquantes))}.\nIl n'y a pas de migration : après sauvegarde, recréer la base vierge puis "
        f"redémarrer l'API :\n  psql -U postgres -c \"DROP DATABASE <base>;\" -c \"CREATE DATABASE <base>;\"\n"
        f"  psql -U postgres -d <base> -v ON_ERROR_STOP=1 -f {_SCRIPT}\n"
        "  puis database/02_donnees_reference.sql et database/03_verification.sql"
    )
