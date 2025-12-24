from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/kahoot", tags=["Kahoot"])

@router.get("/", response_class=HTMLResponse)
def kahoot_home():
    return "<h1>Importar Kahoot (em construção)</h1>"
