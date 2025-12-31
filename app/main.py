from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.api.routes.parse import router as parse_router

app = FastAPI(
    title="Agent Parser (Resume Extraction Service)",
    description="Deterministic resume parsing service that extracts candidate information from DOCX/PDF/TXT resumes with evidence tracking",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.include_router(parse_router)

@app.get("/", tags=["health"])
def root():
    return {"service": "agent-parser", "status": "running"}

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

def custom_openapi():
    """Generate OpenAPI schema with custom settings."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Agent Parser API",
        version="0.1.0",
        description="Resume parsing API with evidence-backed extraction",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
