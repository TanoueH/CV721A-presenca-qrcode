from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from app.services.sheets import get_ws  # ajuste se seu sheets.py usa outro helper


def calcular_frequencia() -> Tuple[int, List[Dict]]:
    """
    Lê a aba 'Checkins' (log de presenças) e calcula, por RA:
      - nome (último ou mais frequente)
      - presenças (número de aulas com check-in)
      - frequência (%)

    Requisitos esperados no Sheets:
      - Uma aba chamada 'Checkins'
      - Colunas (case-insensitive): 'RA', 'Nome'
      - Uma coluna de data/hora (ex.: 'Timestamp', 'Data', 'Hora'...) — usada para contar aulas únicas.
        Se não existir, conta cada check-in como uma presença.
    """
    ws = get_ws("Checkins")  # se sua aba tiver outro nome, ajuste aqui

    rows = ws.get_all_records()  # lista de dicts
    if not rows:
        return 0, []

    # Detecta chaves (tolerante a variações)
    def pick_key(d: Dict, candidates: List[str]) -> str | None:
        keys = {k.lower(): k for k in d.keys()}
        for c in candidates:
            if c.lower() in keys:
                return keys[c.lower()]
        return None

    sample = rows[0]
    k_ra = pick_key(sample, ["ra", "RA"])
    k_nome = pick_key(sample, ["nome", "Nome"])
    k_ts = pick_key(sample, ["timestamp", "datahora", "data_hora", "data", "hora", "registrado_em"])

    if not k_ra or not k_nome:
        # Falta coluna essencial
        raise ValueError("A aba 'Checkins' precisa ter colunas 'RA' e 'Nome'.")

    # Agrupar presenças
    presencas_por_ra = defaultdict(set)   # ra -> set de aulas (data) ou tokens
    nome_por_ra = {}                      # ra -> nome

    for r in rows:
        ra = str(r.get(k_ra, "")).strip()
        nome = str(r.get(k_nome, "")).strip()
        if not ra:
            continue

        if nome:
            nome_por_ra[ra] = nome

        # Define "aula" para contagem: se tiver timestamp/data, usa o valor cru normalizado;
        # senão, conta cada linha como uma presença.
        if k_ts and r.get(k_ts):
            aula_key = str(r.get(k_ts)).strip()
        else:
            # fallback: cada linha conta como 1 presença
            aula_key = f"row_{id(r)}"

        presencas_por_ra[ra].add(aula_key)

    # Total de aulas: número de "aulas" únicas no log (pelo timestamp) ou, se não houver timestamp, máximo de presenças
    if k_ts:
        aulas_unicas = set()
        for ra, aulas in presencas_por_ra.items():
            aulas_unicas |= aulas
        total_aulas = len(aulas_unicas)
    else:
        total_aulas = max((len(v) for v in presencas_por_ra.values()), default=0)

    alunos = []
    for ra, aulas in presencas_por_ra.items():
        presencas = len(aulas)
        freq = (presencas / total_aulas * 100.0) if total_aulas > 0 else 0.0
        alunos.append(
            {
                "ra": ra,
                "nome": nome_por_ra.get(ra, ""),
                "presencas": presencas,
                "frequencia": round(freq, 1),
            }
        )

    # Ordena por nome (ou RA)
    alunos.sort(key=lambda x: (x["nome"] or "ZZZ", x["ra"]))
    return total_aulas, alunos
