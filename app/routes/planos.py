from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import agora, novo_id, transacao, consultar, um
from ..security import exigir_login

router = APIRouter(dependencies=[Depends(exigir_login)])

class PagamentoIn(BaseModel):
    plano_id: str
    valor: Decimal = Field(gt=0)
    data_pagamento: date
    forma_pagamento: Literal['PIX','CARTAO_CREDITO','DINHEIRO','BOLETO']

@router.get("")
def listar_planos():
    return consultar("SELECT id, nome, valor, dias_tolerancia FROM planos ORDER BY nome")

@router.post("/alunos/{aluno_id}/pagamentos")
def registrar_pagamento(aluno_id: str, d: PagamentoIn, op: dict = Depends(exigir_login)):
    aluno = um("SELECT id FROM alunos WHERE id=%s", (aluno_id,))
    plano = um("SELECT id FROM planos WHERE id=%s", (d.plano_id,))
    if not aluno or not plano:
        raise HTTPException(404, "Aluno ou plano não encontrado")
    m = um("""SELECT id FROM matriculas WHERE aluno_id=%s AND status='ATIVO'
              ORDER BY criado_em DESC LIMIT 1""", (aluno_id,))
    if not m:
        raise HTTPException(400, "Aluno sem matrícula ativa")
    plano_nome = um("SELECT nome FROM planos WHERE id=%s", (d.plano_id,))
    if not plano_nome:
        raise HTTPException(404, "Plano não encontrado")
    nome = plano_nome["nome"].lower()
    meses = 12 if "anual" in nome else 6 if "semestral" in nome else 3 if "trimestral" in nome else 1
    from datetime import timedelta
    vencimento = d.data_pagamento + timedelta(days=30 * meses)
    with transacao() as cur:
        cur.execute("UPDATE matriculas SET plano_id=%s, vencimento=%s WHERE id=%s",
                    (d.plano_id, vencimento, m["id"]))
        cur.execute("""INSERT INTO pagamentos
                      (id, aluno_id, matricula_id, plano_id, valor, data_pagamento, forma_pagamento)
                      VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (novo_id(), aluno_id, m["id"], d.plano_id, d.valor, d.data_pagamento, d.forma_pagamento))
    return {"ok": True, "aluno_id": aluno_id, "operador_id": op["sub"]}
