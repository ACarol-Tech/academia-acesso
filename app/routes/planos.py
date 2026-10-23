import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import consultar, data_hoje, novo_id, transacao, um
from ..security import exigir_login

router = APIRouter(dependencies=[Depends(exigir_login)])


class PagamentoIn(BaseModel):
    plano_id: str
    valor: Decimal = Field(gt=0)
    data_pagamento: date
    forma_pagamento: Literal["PIX", "CARTAO_CREDITO", "DINHEIRO", "BOLETO"]


def meses_do_plano(nome: str) -> int:
    """Duração do plano em meses, pelo nome (Anual, Semestral, Trimestral; o resto é mensal)."""
    n = nome.lower()
    return 12 if "anual" in n else 6 if "semestral" in n else 3 if "trimestral" in n else 1


def somar_meses(d: date, meses: int) -> date:
    """Soma meses de calendário; se o dia não existir no mês de destino, usa o último dia dele."""
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


@router.get("")
def listar_planos():
    return consultar("SELECT id, nome, valor, dias_tolerancia FROM planos ORDER BY nome")


@router.post("/alunos/{aluno_id}/pagamentos")
def registrar_pagamento(aluno_id: str, d: PagamentoIn, op: dict = Depends(exigir_login)):
    # tolerância de 1 dia: a tela ainda sugere a data pelo relógio UTC, que passa de meia-noite antes de Belém
    if d.data_pagamento > data_hoje() + timedelta(days=1):
        raise HTTPException(400, "A data do pagamento não pode ser no futuro")
    aluno = um("SELECT id FROM alunos WHERE id=%s AND ativo=TRUE", (aluno_id,))
    plano = um("SELECT id, nome FROM planos WHERE id=%s", (d.plano_id,))
    if not aluno or not plano:
        raise HTTPException(404, "Aluno ou plano não encontrado")
    m = um("""SELECT id, vencimento FROM matriculas WHERE aluno_id=%s AND status='ATIVO'
              ORDER BY criado_em DESC LIMIT 1""", (aluno_id,))
    if not m:
        raise HTTPException(400, "Aluno sem matrícula ativa")

    # adiantado: o novo ciclo começa no vencimento atual (não perde dias); atrasado: começa no pagamento
    base = max(m["vencimento"], d.data_pagamento) if m["vencimento"] else d.data_pagamento
    vencimento = somar_meses(base, meses_do_plano(plano["nome"]))

    with transacao() as cur:
        cur.execute("UPDATE matriculas SET plano_id=%s, vencimento=%s WHERE id=%s",
                    (d.plano_id, vencimento, m["id"]))
        cur.execute("""INSERT INTO pagamentos
                      (id, aluno_id, matricula_id, plano_id, valor, data_pagamento, forma_pagamento)
                      VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (novo_id(), aluno_id, m["id"], d.plano_id, d.valor, d.data_pagamento, d.forma_pagamento))
    return {"ok": True, "aluno_id": aluno_id, "operador_id": op["sub"], "novo_vencimento": vencimento}
