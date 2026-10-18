from fastapi import APIRouter, FastAPI

from app.api import accounts, auth, dashboard, settings, strategies

app = FastAPI(title="XAU Lab API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok"}


for r in (auth.router, settings.router, accounts.router, strategies.router, dashboard.router):
    api.include_router(r)
app.include_router(api)
