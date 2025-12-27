from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.services.frequencia import calcular_frequencia

router = APIRouter()

@router.get("/frequencia", response_class=HTMLResponse)
def frequencia(request: Request):
    total_aulas, alunos = calcular_frequencia()
    total_alunos = len(alunos)

    return request.app.state.templates.TemplateResponse(
        "frequencia.html",
        {
            "request": request,
            "total_aulas": total_aulas,
            "total_alunos": total_alunos,
            "alunos": alunos,
        },
    )
