from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes.aula import router as prof_router, public_router
from app.routes.frequencia import router as frequencia_router
from app.routes.notas import router as notas_router
from app.routes.kahoot import router as kahoot_router
from app.routes.chamada import router as chamada_router

app = FastAPI(title="SIGA - Sistema Integrado de Gestão Acadêmica", version="1.0.1")

# Templates e arquivos estáticos
app.state.templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Raiz → painel do professor
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/prof/", status_code=302)

# Professor (/prof/...) e Check-in (/checkin/...)
app.include_router(prof_router)     # prefix="/prof" já está no aula.py
app.include_router(public_router)

# Módulos auxiliares
app.include_router(frequencia_router)
app.include_router(notas_router)
app.include_router(kahoot_router)
app.include_router(chamada_router)

# Healthcheck (útil no Render)
@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}
