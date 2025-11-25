try:
    from database import db  # Fixed: import from database.py to avoid circular import
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

from datetime import datetime, timezone, timedelta
from werkzeug.security import check_password_hash


class User(db.Model):
    """User model for NASA blog authentication."""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship to blog posts
    posts = db.relationship('BlogPost', backref='author', lazy=True, cascade='all, delete-orphan')

    def check_password(self, password):
        """Verify password against hash."""
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        """Check if account is currently locked."""
        if self.locked_until and self.locked_until > datetime.now(timezone.utc):
            return True
        return False

    def increment_failed_login(self):
        """Increment failed login attempts and lock if threshold reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 10:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)

    def reset_failed_logins(self):
        """Reset failed login counter on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self):
        return f'<User {self.username}>'


class BlogPost(db.Model):
    """Blog post model."""
    __tablename__ = 'blog_post'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.String(500), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    published = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Images associated with this post
    images = db.relationship('BlogImage', backref='post', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BlogPost {self.title}>'


class BlogImage(db.Model):
    """Model for blog post images."""
    __tablename__ = 'blog_image'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('blog_post.id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<BlogImage {self.filename}>'


class LoginAttempt(db.Model):
    """Model to log login attempts for security monitoring."""
    __tablename__ = 'login_attempt'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    success = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<LoginAttempt {self.username} @ {self.timestamp}>'


class Photo(db.Model):
    """Model for gallery photos."""
    __tablename__ = 'photo'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    # Integer position for manual ordering in the gallery. Lower numbers display first.
    position = db.Column(db.Integer, nullable=False, default=0, index=True)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Optionally, add a user_id if you want to track who uploaded

    def __repr__(self):
        return f'<Photo {self.filename}>'


