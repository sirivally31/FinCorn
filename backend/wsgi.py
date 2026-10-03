"""WSGI entrypoint for production-style hosting platforms."""
from app import app, bootstrap

bootstrap()