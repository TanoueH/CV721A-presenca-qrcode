from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/notas", tags=["Notas"])

@router.get("/", response_class=HTMLResponse)
def notas_home():
    return "<h1>Notas (em construção)</h1>"
