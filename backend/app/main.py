from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, clients, projects, rate_items, regional_multipliers, scope_items, sports

app = FastAPI(title="NestaPrime Estimator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(regional_multipliers.router)
app.include_router(sports.sports_router)
app.include_router(sports.project_sports_router)
app.include_router(scope_items.scope_items_router)
app.include_router(scope_items.project_scope_items_router)
app.include_router(rate_items.labour_categories_router)
app.include_router(rate_items.rate_items_router)


@app.get("/health")
def health():
    return {"status": "ok"}
