"""
Copie les données d'une base PostgreSQL vers celle de `DATABASE_URL`
(changement d'hébergeur : Render -> Neon, par exemple).

Les identifiants sont conservés et les séquences recalées. La base d'origine
n'est que lue. La base de destination doit être vide, sauf avec `--replace`.

Usage (PowerShell) :
  $env:SOURCE_DATABASE_URL = "postgresql://user:password@host/dbname"
  python -m scripts.copy_database             # copier
  python -m scripts.copy_database --dry-run   # compter les lignes sans écrire
  python -m scripts.copy_database --replace   # vider la destination avant de copier
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("copy_database")

from sqlalchemy import Integer, create_engine, func, insert, select, text

from app import models  # noqa: F401  (enregistre les tables sur Base.metadata)
from app.database import Base, _normalize_url, create_all, engine as target

BATCH = 500  # lignes par INSERT : reste loin de la limite de paramètres SQL


def count(conn, table) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


def run(dry_run: bool = False, replace: bool = False) -> None:
    source_url = os.environ.get("SOURCE_DATABASE_URL", "")
    if not source_url:
        raise SystemExit("SOURCE_DATABASE_URL n'est pas défini (URL de la base d'origine)")
    url, connect_args = _normalize_url(source_url)
    source = create_engine(url, connect_args=connect_args)
    if (url.host, url.database) == (target.url.host, target.url.database):
        raise SystemExit("La base d'origine et la base de destination sont identiques")
    logger.info("Origine : %s/%s -> destination : %s/%s",
                url.host, url.database, target.url.host, target.url.database)

    tables = Base.metadata.sorted_tables  # parents avant enfants (clés étrangères)
    if not dry_run:
        create_all()

    with source.connect() as src, target.begin() as dst:
        existing = {t.name: count(dst, t) for t in tables} if not dry_run else {}
        filled = {name: n for name, n in existing.items() if n}
        if filled and not replace:
            raise SystemExit(f"La destination contient déjà des données {filled} : relancer avec --replace pour les remplacer")
        if filled:
            dst.execute(text("TRUNCATE " + ", ".join(f'"{t.name}"' for t in tables) + " RESTART IDENTITY CASCADE"))
            logger.info("Destination vidée")

        for table in tables:
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            if dry_run:
                logger.info("[dry-run] %-26s %d lignes", table.name, len(rows))
                continue
            for start in range(0, len(rows), BATCH):
                dst.execute(insert(table).values(rows[start:start + BATCH]))
            logger.info("%-26s %d lignes copiées", table.name, len(rows))

        if dry_run:
            return
        for table in tables:
            # Les identifiants ont été insérés tels quels : la séquence doit repartir après le dernier
            pk = list(table.primary_key.columns)
            if len(pk) == 1 and isinstance(pk[0].type, Integer):
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0].name}'), "
                    f'COALESCE(MAX("{pk[0].name}"), 1), MAX("{pk[0].name}") IS NOT NULL) FROM "{table.name}"'
                ))
        mismatch = {t.name: (count(src, t), count(dst, t)) for t in tables if count(src, t) != count(dst, t)}
        if mismatch:
            raise RuntimeError(f"Nombres de lignes différents (origine, destination) : {mismatch}")
    logger.info("Copie terminée et vérifiée")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copie les données d'une base PostgreSQL vers DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="vide la destination avant de copier")
    args = parser.parse_args()
    run(dry_run=args.dry_run, replace=args.replace)


if __name__ == "__main__":
    main()
