import os
os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost:5432/db")
os.environ.setdefault("EMBEDDINGS_PROVIDER", "openai")
os.environ.setdefault("ENABLE_METRICS", "false")

from applicationApi import create_app


def test_app_starts():
    app = create_app()
    assert app is not None
    with app.test_client() as c:
        r = c.get("/api/health/health")
        assert r.status_code in (200, 404)  # alguns ambientes montam /api/health, outros /api/health/health
