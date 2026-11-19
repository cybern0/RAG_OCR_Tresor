"""Contrôle au démarrage : la base a-t-elle les colonnes que le code lit ?

Sans ce contrôle, une base qui n'a pas reçu une migration répond par des erreurs 500 cryptiques
(« la colonne … n'existe pas ») dès qu'on liste les fichiers. On préfère s'arrêter net avec la commande à lancer.
"""

from sqlalchemy import text

from app.db.vecteur import DocumentVersion

# colonne -> script de migration qui l'ajoute (bases existantes ; une base neuve créée par 01_schema.sql les a déjà)
_MIGRATIONS = {
    "tableaux_indexes": "database/migration_reindexation.sql",
    "images_indexes": "database/migration_reindexation.sql",
}


def colonnes_manquantes(engine) -> dict[str, str]:
    """{colonne manquante de document_version: script de migration à appliquer} (vide si la base est à jour)."""
    table = DocumentVersion.__table__
    with engine.connect() as conn:
        presentes = {
            r[0]
            for r in conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :t AND table_schema = :s"),
                {"t": table.name, "s": table.schema or "public"},
            )
        }
    return {c.name: _MIGRATIONS.get(c.name, "database/") for c in table.columns if c.name not in presentes}


def verifier_schema(engine) -> None:
    manquantes = colonnes_manquantes(engine)
    if not manquantes:
        return
    scripts = sorted(set(manquantes.values()))
    commandes = "\n".join(f"  psql -U postgres -d <base> -v ON_ERROR_STOP=1 -f {s}" for s in scripts)
    raise RuntimeError(
        "La base de données n'est pas à jour : colonnes manquantes dans document_version : "
        f"{', '.join(sorted(manquantes))}.\nAppliquer la migration, puis redémarrer l'API :\n{commandes}"
    )
