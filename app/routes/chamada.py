from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.http_utils import warn_if_localhost

# Router precisa existir no nível do módulo (para app.main importar)
router = APIRouter(tags=["Chamada"], prefix="/chamada")

# Defaults (não derrubam o app)
DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil FEC – 2026"
TEMPO_QR_MIN = 15

# Estado fallback (não derruba o app)
class _FallbackState:
    def __init__(self):
        self.token = None
        self.expira_em = None

    def nova_aula(self):
        # chamada.py é apenas informativo; o QR real está em /prof
        pass

STATE = _FallbackState()

# Tenta carregar config/estado reais, mas sem quebrar deploy
try:
    import app.core.app_state as app_state

    DISCIPLINA = getattr(app_state, "DISCIPLINA", DISCIPLINA)
    TURMA = getattr(app_state, "TURMA", TURMA)
    TEMPO_QR_MIN = getattr(app_state, "TEMPO_QR_MIN", TEMPO_QR_MIN)
    STATE = getattr(app_state, "STATE", STATE)
except Exception:
    # não derruba o app
    pass


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
  <li>Use o painel do professor em <a href="/prof/" target="_blank">/prof/</a>.</li>
  <li>Projete o QR por <strong>{TEMPO_QR_MIN} min</strong>.</li>
  <li>Alunos fazem check-in com RA e Nome.</li>
</ol>

<div class="card">
  <p>A rota <strong>/chamada</strong> está em modo compatibilidade (não gera QR).</p>
  <p>Para gerar e projetar QR, use: <a href="/prof/" target="_blank">/prof/</a></p>
</div>

</body>
</html>
"""
    return HTMLResponse(html)
