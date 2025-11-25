"""
Database configuration for SQLAlchemy.
This module creates the shared database instance used across the application.
"""
from flask_sqlalchemy import SQLAlchemy

# Create the database instance
# This will be initialized with the Flask app in main_app.py
db = SQLAlchemy()


