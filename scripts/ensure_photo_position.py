#!/usr/bin/env python3
"""Add `position` column to the `photo` table if it doesn't exist.
Run once from the project root in the virtualenv:
    python scripts/ensure_photo_position.py
"""
from main_app import app
from database import db
from sqlalchemy import inspect, text

with app.app_context():
    # Prefer the modern attribute `db.engine` (Flask-SQLAlchemy 3+).
    # Fall back to `db.get_engine()` if `engine` is not available.
    engine = getattr(db, 'engine', None)
    if engine is None:
        try:
            engine = db.get_engine()
        except Exception:
            # Last resort: try without arguments (older versions)
            engine = db.get_engine(app)
    inspector = inspect(engine)
    cols = [c['name'] for c in inspector.get_columns('photo')]
    if 'position' in cols:
        print('position column already exists.')
    else:
        dialect = engine.dialect.name
        print(f'Adding position column using dialect: {dialect}')
        if dialect == 'sqlite':
            sql = 'ALTER TABLE photo ADD COLUMN position INTEGER NOT NULL DEFAULT 0;'
        else:
            # Generic SQL that works for many DBs
            sql = 'ALTER TABLE photo ADD COLUMN position INTEGER DEFAULT 0;'
        with engine.begin() as conn:
            conn.execute(text(sql))
        # Populate positions based on upload_date ordering as an initial state
        photos = db.session.execute(text('SELECT id FROM photo ORDER BY upload_date'))
        pos = 0
        for row in photos:
            db.session.execute(text('UPDATE photo SET position = :pos WHERE id = :id'), {'pos': pos, 'id': row[0]})
            pos += 1
        db.session.commit()
        print('position column added and initialized.')
