import os
from blog.models import Photo
from database import db
from main_app import app

photos_dir = os.path.join(os.path.dirname(__file__), 'photos')

with app.app_context():
    added = 0
    removed = 0
    # Get all image files in /photos
    image_files = [f for f in os.listdir(photos_dir) if f.lower().endswith((
        '.jpg', '.jpeg', '.png', '.gif', '.webp'))]
    # Add missing files to DB
    for fname in image_files:
        exists = Photo.query.filter_by(filename=fname).first()
        if not exists:
            photo = Photo(filename=fname, caption='', description='')
            db.session.add(photo)
            added += 1
    # Remove DB records for files that no longer exist
    db_filenames = [p.filename for p in Photo.query.all()]
    for db_fname in db_filenames:
        if db_fname not in image_files:
            photo = Photo.query.filter_by(filename=db_fname).first()
            if photo:
                db.session.delete(photo)
                removed += 1
    db.session.commit()
    print(f"Added {added} new photos to the database.")
    print(f"Removed {removed} photos from the database that no longer exist in /photos.")
