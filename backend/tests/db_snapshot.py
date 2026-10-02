"""Shared test helpers: a full-database snapshot and a storage-tree snapshot.

full_snapshot() captures EVERY persisted column of EVERY row of EVERY table, so "a refused request changed
nothing" cannot pass while some related record quietly changed. storage_snapshot() lists every stored file."""

import os

from sqlalchemy import select


def full_snapshot(db, exclude_tables=()):
    from app.db.base import Base

    db.rollback()
    db.expire_all()
    dump = {}
    for table in Base.metadata.sorted_tables:
        if table.name in exclude_tables:
            continue
        query = select(table)
        if list(table.primary_key.columns):
            query = query.order_by(*table.primary_key.columns)
        dump[table.name] = [tuple(repr(value) for value in row) for row in db.execute(query)]
    return dump


def storage_snapshot(root, exclude_dirs=("_upload_tmp",)):
    """Relative path + size of every file under the attachment storage root (temp chunk dirs excluded)."""
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for name in files:
            path = os.path.join(folder, name)
            found.append((os.path.relpath(path, root), os.path.getsize(path)))
    return sorted(found)
