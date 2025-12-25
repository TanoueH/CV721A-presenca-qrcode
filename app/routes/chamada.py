from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.app_state import STATE, DISCIPLINA, TURMA, TEMPO_QR_MIN
from app.core.http_utils import warn_if_localhost

router = APIRouter(tags=["Chamada"], prefix="/chamada")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    aviso = warn_if_localhost(request)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
body {{
  font-family: Arial, sans-serif;
  padding: 16px;
  margin: 0;
}}
h1 {{ font-size: 24px; margin: 0 0 10px; }}
p, li {{ font-size: 18px; line-height: 1.35; }}
button {{
  width: 100%;
  font-size: 20px;
  padding: 16px;
  margin-top: 12px;
  background: #0b5ed7;
  color: #fff;
  border: 0;
  border-radius: 12px;
}}
img {{ max-width: 100%; height: auto; }}
.card {{
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 12px;
}}
a {{ color: #0b5ed7; font-weight: 600; }}
</style>
</head>
<body>

<h1>Presença por QR – {DISCIPLINA}</h1>
<p><strong>Turma:</strong> {TURMA}</p>
{aviso}

<ol>
  <li>Clique em <strong>Gerar QR</strong> no início da aula.</li>
  <li>Projete o QR por <strong>{TEMPO_QR_MIN} min</strong>.</li>
  <li>Alunos fazem check-in com RA e Nome.</li>
</ol>

<form action="/chamada/aula/nova" method="post">
  <button type="submit">Gerar QR (início da aula)</button>
</form>
"""

    if STATE.token and STATE.expira_em:
        html += f"""
<div class="card">
  <p><strong>QR válido até:</strong> {STATE.expira_em.strftime("%H:%M:%S")}</p>
  <p>
    O QR é servido na área do professor. Abra o painel:
    <a href="/prof/" target="_blank">/prof/</a>
  </p>
</div>
"""

    html += """
</body>
</html>
"""
    return HTMLResponse(html)


@router.post("/aula/nova", response_class=HTMLResponse)
def aula_nova():
    STATE.nova_aula()
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
body {{ font-family: Arial, sans-serif; padding: 16px; margin: 0; }}
h2 {{ font-size: 22px; margin: 0 0 10px; }}
a {{ font-size: 18px; color:#0b5ed7; font-weight:600; }}
img {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
  <h2>QR Code gerado com sucesso</h2>
  <p><strong>Válido por:</strong> {TEMPO_QR_MIN} min</p>
  <p><a href="/chamada/">Voltar</a></p>
  <p>
    Abra o painel do professor para projetar o QR:
    <a href="/prof/" target="_blank">/prof/</a>
  </p>
</body>
</html>
""")
