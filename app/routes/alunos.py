import re
from .planos import somar_meses
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..db import agora, consultar, executar, novo_id, transacao, um
from ..intelbras import cadastrar_face
from ..security import cifrar, decifrar, exigir_admin, exigir_login, hmac_hex, mascarar_cpf

router = APIRouter(dependencies=[Depends(exigir_login)])  # nenhuma rota daqui responde sem login


FormaPagamento = Literal["PIX", "CARTAO_CREDITO", "DINHEIRO", "BOLETO"]


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores e recusa sequências como 111.111.111-11."""
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tam in (9, 10):
        soma = sum(int(cpf[i]) * (tam + 1 - i) for i in range(tam))
        if (soma * 10 % 11) % 10 != int(cpf[tam]):
            return False
    return True


class AlunoIn(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    cpf: str
    data_nascimento: date | None = None
    endereco: str | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, max_length=30)
    plano_id: str
    vencimento: date
    foto: str = Field(max_length=300_000)  # JPEG em base64, sem o prefixo data:
    valor_pago: Decimal
    data_pagamento: date
    forma_pagamento: FormaPagamento
    meses: int | None = Field(default=None, ge=1, le=36)  # meses pagos; vazio = usa o vencimento enviado
    consentimento: Literal[True]  # LGPD: consentimento obrigatório

    @field_validator("cpf")
    @classmethod
    def so_digitos(cls, v):
        v = re.sub(r"\D", "", v)
        if not cpf_valido(v):
            raise ValueError("CPF inválido")
        return v

    @field_validator("foto")
    @classmethod
    def base64_ok(cls, v):
        if not re.fullmatch(r"[A-Za-z0-9+/=]+", v):
            raise ValueError("Foto inválida")
        return v


class AlunoPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=120)
    cpf: str | None = None
    data_nascimento: date | None = None
    endereco: str | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, max_length=30)

    @field_validator("cpf")
    @classmethod
    def cpf_digitos(cls, v):
        if v is None:
            return v
        v = re.sub(r"\D", "", v)
        if not cpf_valido(v):
            raise ValueError("CPF inválido")
        return v

    @field_validator("nome")
    @classmethod
    def nome_limpo(cls, v):
        return " ".join(v.split()) if v else v


def _aluno(row: dict) -> dict:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "cpf": mascarar_cpf(decifrar(row["cpf_cript"])),
        "data_nascimento": row["data_nascimento"],
        "endereco": row["endereco"],
        "telefone": row["telefone"],
        "plano": row["plano"],
        "plano_id": row["plano_id"],
        "valor_plano": row["valor_plano"],
        "dias_tolerancia": row["dias_tolerancia"] or 0,
        "vencimento": row["vencimento"],
        "status": row["status"],
        "ativo": bool(row["ativo"]),
        "visitas_mes": int(row.get("visitas_mes") or 0),
        "ultima_visita": row.get("ultima_visita"),
    }


ALUNO_SELECT = """SELECT a.id, a.nome, a.cpf_cript, a.data_nascimento, a.endereco, a.telefone,
    a.ativo, p.id AS plano_id, p.nome AS plano, p.valor AS valor_plano, p.dias_tolerancia,
    m.vencimento, m.status,
    (SELECT COUNT(*) FROM historico_acessos h WHERE h.aluno_id=a.id AND h.resultado IN ('APROVADO','LIBERADO_MANUAL')
       AND h.data_hora >= DATE_FORMAT(CURRENT_DATE, '%%Y-%%m-01')) AS visitas_mes,
    (SELECT MAX(h.data_hora) FROM historico_acessos h WHERE h.aluno_id=a.id AND h.resultado IN ('APROVADO','LIBERADO_MANUAL')) AS ultima_visita
    FROM alunos a
    LEFT JOIN matriculas m ON m.id = (SELECT id FROM matriculas WHERE aluno_id=a.id ORDER BY criado_em DESC LIMIT 1)
    LEFT JOIN planos p ON p.id = m.plano_id"""


@router.get("")
def listar():
    linhas = consultar(ALUNO_SELECT + " WHERE a.ativo=TRUE ORDER BY a.nome LIMIT 200")
    return [_aluno(r) for r in linhas]


@router.get("/{aluno_id}")
def detalhar(aluno_id: str):
    r = um(ALUNO_SELECT + " WHERE a.id=%s", (aluno_id,))
    if not r:
        raise HTTPException(404, "Aluno não encontrado")
    out = _aluno(r)
    out["pagamentos"] = consultar(
        """SELECT id, valor, data_pagamento, forma_pagamento, plano_id, criado_em
           FROM pagamentos WHERE aluno_id=%s ORDER BY data_pagamento DESC, criado_em DESC LIMIT 100""",
        (aluno_id,),
    )
    return out


@router.post("", status_code=201)
def criar(d: AlunoIn, op: dict = Depends(exigir_login)):
    cpf_hash = hmac_hex(d.cpf)
    existente = um("SELECT id, codigo, ativo FROM alunos WHERE cpf_hash=%s", (cpf_hash,))
    if existente and existente["ativo"]:
        raise HTTPException(409, "CPF já cadastrado")
    plano = um("SELECT id, meses FROM planos WHERE id=%s", (d.plano_id,))
    if not plano:
        raise HTTPException(400, "Plano inexistente")
    meses = d.meses or plano["meses"]
    vencimento = somar_meses(d.data_pagamento, d.meses) if d.meses else d.vencimento

    with transacao() as cur:
        if existente:  # aluno que voltou: reativa o cadastro antigo e mantém o histórico
            aluno_id = existente["id"]
            cur.execute("""UPDATE alunos SET ativo=TRUE, nome=%s, foto_cript=%s, consentimento_lgpd_em=%s,
                           data_nascimento=%s, endereco=%s, telefone=%s WHERE id=%s""",
                        (d.nome, cifrar(d.foto), agora(), d.data_nascimento, d.endereco, d.telefone, aluno_id))
        else:
            aluno_id = novo_id()
            cur.execute("""INSERT INTO alunos
                           (id, nome, cpf_cript, cpf_hash, foto_cript, consentimento_lgpd_em,
                            data_nascimento, endereco, telefone, ativo)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)""",
                        (aluno_id, d.nome, cifrar(d.cpf), cpf_hash, cifrar(d.foto), agora(),
                         d.data_nascimento, d.endereco, d.telefone))
        cur.execute("SELECT codigo FROM alunos WHERE id=%s", (aluno_id,))
        codigo = cur.fetchone()["codigo"]
        cur.execute("UPDATE alunos SET intelbras_user_id=%s WHERE id=%s", (str(codigo), aluno_id))
        matricula_id = novo_id()
        cur.execute("INSERT INTO matriculas (id, aluno_id, plano_id, vencimento) VALUES (%s,%s,%s,%s)",
                    (matricula_id, aluno_id, d.plano_id, vencimento))
        cur.execute("""INSERT INTO pagamentos
                       (id, aluno_id, matricula_id, plano_id, valor, data_pagamento, forma_pagamento, meses, operador_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (novo_id(), aluno_id, matricula_id, d.plano_id, d.valor_pago, d.data_pagamento,
                     d.forma_pagamento, meses, op["sub"]))
        # por último: se a catraca falhar, tudo acima é desfeito e nada fica salvo
        cadastrar_face(str(codigo), d.nome, d.foto)
    return {"id": aluno_id}


@router.patch("/{aluno_id}")
def atualizar(aluno_id: str, d: AlunoPatch):
    atual = um("SELECT id, nome, cpf_cript, cpf_hash, data_nascimento, endereco, telefone, ativo FROM alunos WHERE id=%s", (aluno_id,))
    if not atual:
        raise HTTPException(404, "Aluno não encontrado")
    if not atual["ativo"]:
        raise HTTPException(409, "Este aluno está excluído do cadastro ativo")

    nome = d.nome if d.nome is not None else atual["nome"]
    data_nascimento = d.data_nascimento if d.data_nascimento is not None else atual["data_nascimento"]
    endereco = d.endereco if d.endereco is not None else atual["endereco"]
    telefone = d.telefone if d.telefone is not None else atual["telefone"]

    if d.cpf is not None:
        cpf_hash = hmac_hex(d.cpf)
        outro = um("SELECT id FROM alunos WHERE cpf_hash=%s AND id<>%s AND ativo=TRUE", (cpf_hash, aluno_id))
        if outro:
            raise HTTPException(409, "CPF já cadastrado para outro aluno")
        cpf_cript = cifrar(d.cpf)
    else:
        cpf_hash = atual["cpf_hash"]
        cpf_cript = atual["cpf_cript"]

    executar("""UPDATE alunos SET nome=%s, cpf_cript=%s, cpf_hash=%s,
               data_nascimento=%s, endereco=%s, telefone=%s WHERE id=%s""",
             (nome, cpf_cript, cpf_hash, data_nascimento, endereco, telefone, aluno_id))
    return {"ok": True}


@router.delete("/{aluno_id}", status_code=204, dependencies=[Depends(exigir_admin)])
def remover(aluno_id: str):
    atual = um("SELECT id, nome, ativo FROM alunos WHERE id=%s", (aluno_id,))
    if not atual:
        raise HTTPException(404, "Aluno não encontrado")
    if not atual["ativo"]:
        raise HTTPException(409, "Aluno já excluído")

    # Exclusão lógica: preserva pagamentos, acessos e liberações para auditoria.
    with transacao() as cur:
        cur.execute("UPDATE alunos SET ativo=FALSE WHERE id=%s", (aluno_id,))
        cur.execute("UPDATE matriculas SET status='CANCELADO' WHERE aluno_id=%s AND status<>'CANCELADO'", (aluno_id,))
    return None