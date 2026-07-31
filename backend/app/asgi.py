"""ASGI entrypoint: `uvicorn backend.app.asgi:app`."""
from backend.app.main import create_app

app = create_app()
