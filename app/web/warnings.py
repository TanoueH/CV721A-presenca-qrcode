def warn_if_localhost(host: str) -> str:
    host = (host or "").lower()
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        return (
            "<p style='color:#b00'>"
            "<strong>Atenção:</strong> você abriu pelo <code>localhost</code>. "
            "No celular isso não funciona. "
            "Use o IP da máquina ou a URL pública."
            "</p>"
        )
    return ""
