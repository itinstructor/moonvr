from flask import Flask

def create_app():
    app = Flask(__name__)
    # ...existing config...

    # Register the Blog blueprint at the correct prefix
    from blog import blog_bp
    app.register_blueprint(blog_bp, url_prefix='/aquaponics/blog')

    return app