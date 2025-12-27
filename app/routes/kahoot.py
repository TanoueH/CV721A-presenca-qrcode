from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/kahoot", tags=["Kahoot"])

@router.get("/", response_class=HTMLResponse)
def kahoot_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "kahoot.html",
        {
            "request": request,
            "prof_k": request.query_params.get("k", "")
        },
    )
