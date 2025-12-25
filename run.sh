#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8000}"

cd "$APP_DIR"

# 1) Garantir que estamos no venv (se existir)
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

# 2) Mostrar variáveis importantes
echo "=============================================="
echo "CV721A Presença QR — Runner"
echo "Diretório: $APP_DIR"
echo "PORT: $PORT"
echo "SPREADSHEET_ID set? -> ${SPREADSHEET_ID:+YES}"
echo "BASE_URL set?       -> ${BASE_URL:+YES}"
echo "=============================================="
echo

# 3) Encerrar instâncias antigas do uvicorn para não ficar trocando porta
pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true

# 4) Mostrar IPs (WSL) e instruções
WSL_IPS="$(hostname -I 2>/dev/null || true)"
echo "IPs (WSL): ${WSL_IPS:-N/A}"
echo
echo "Abra no NOTEBOOK (recomendado):"
echo "  - Windows IP (Wi-Fi): rode 'ipconfig' no PowerShell e use o IPv4 do Wi-Fi"
echo "  - Ex.: http://<IP_DO_WINDOWS>:$PORT"
echo
echo "Teste rápido:"
echo "  - http://localhost:$PORT/health"
echo
echo "IMPORTANTE para o QR funcionar no celular:"
echo "  - Abra o sistema pelo IP do Windows (ou pelo IP correto da rede), NÃO por localhost."
echo "=============================================="
echo "⚠️  ATENÇÃO (IMPORTANTE)"
echo "Use o IP do WINDOWS (Wi-Fi), NÃO o IP do WSL"
echo "Exemplo correto para o celular:"
echo "  http://192.168.15.43:$PORT"
echo "=============================================="


# 5) Subir o servidor
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
