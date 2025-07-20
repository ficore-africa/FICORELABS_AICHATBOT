from flask import Blueprint

users_bp = Blueprint('grocery', __name__, template_folder='templates')

from .routes import *
