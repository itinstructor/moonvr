from flask import Blueprint

# Define the Blueprint
# The first argument is the blueprint's name.
# The second argument, __name__, helps Flask locate the blueprint's resources.
# The template_folder tells the blueprint where to find its template files.
geomap_bp = Blueprint("geomap_bp", __name__, template_folder="templates")

# Import the routes to register them with the blueprint
from . import routes


