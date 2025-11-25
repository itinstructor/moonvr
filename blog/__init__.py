from flask import Blueprint


# create blueprint with the name used in templates: 'blog_bp'
blog_bp = Blueprint('blog_bp', __name__, 
                    template_folder='templates',
                    static_folder='static',
                    static_url_path='/blog/static')

# ensure routes are imported so decorators run
from . import routes  # noqa


