from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/kahoot", tags=["Kahoot"])

@router.get("/", response_class=HTMLResponse)
def page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "importar_kahoot.html",
        {"request": request},
    )
