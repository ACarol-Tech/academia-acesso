import httpx
import hmac

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from ..acesso import processar
from ..config import settings
from ..db import novo_id, transacao, um, consultar
from ..intelbras import abrir_porta
from ..realtime import manager
from ..security import exigir_login

router = APIRouter()


class EventoIn(BaseModel):  # ajuste ao formato que o seu modelo de catraca envia
    model_config = ConfigDict(populate_by_name=True)
    user_id: str = Field(alias="userId", min_length=1)


class LiberarIn(BaseModel):
    aluno_id: str
    motivo: str = Field(min_length=3, max_length=120)
    observacao: str | None = Field(default=None, max_length=300)


@router.post("/evento", status_code=204)
async def evento(dados: EventoIn, x_webhook_secret: str = Header(default="")):
    if not hmac.compare_digest(x_webhook_secret.encode(), settings.webhook_secret.encode()):
        raise HTTPException(401)
    r = await run_in_threadpool(processar, dados.user_id)
    if r:
        await manager.enviar({"tipo": "novo_acesso", **r})


@router.post("/simular-evento")
def simular_evento(aluno_id: str, op: dict = Depends(exigir_login)):
    aluno = um("SELECT id, intelbras_user_id FROM alunos WHERE id=%s AND ativo=TRUE", (aluno_id,))
    if not aluno or not aluno["intelbras_user_id"]:
        raise HTTPException(404, "Aluno sem identificador da catraca")
    return processar(aluno["intelbras_user_id"]) or {"alunoId": aluno_id, "resultado": "NEGADO", "motivo": "Aluno não encontrado"}


@router.post("/liberar-manual")
def liberar(d: LiberarIn, op: dict = Depends(exigir_login)):
    if not um("SELECT id FROM alunos WHERE id=%s AND ativo=TRUE", (d.aluno_id,)):
        raise HTTPException(404, "Aluno não encontrado")
    try:
        with transacao() as cur:
            cur.execute("INSERT INTO log_liberacoes (id, aluno_id, operador_id, motivo, observacao) VALUES (%s,%s,%s,%s,%s)",
                        (novo_id(), d.aluno_id, op["sub"], d.motivo, d.observacao))
            cur.execute("INSERT INTO historico_acessos (id, aluno_id, resultado, motivo) VALUES (%s,%s,'LIBERADO_MANUAL',%s)",
                        (novo_id(), d.aluno_id, d.motivo))
            abrir_porta()  # se a catraca falhar, nada fica gravado
    except httpx.HTTPError:
        raise HTTPException(502, "A catraca não respondeu. Nada foi registrado.")
    return {"ok": True}


@router.get("/historico")
def historico(
    inicio: date | None = Query(default=None),
    fim: date | None = Query(default=None),
    resultado: str | None = Query(default=None),
    _: dict = Depends(exigir_login),
):
    if not inicio:
        inicio = date.today()
    if not fim:
        fim = inicio
    fim_exclusivo = datetime.combine(fim + timedelta(days=1), time.min)
    params = [datetime.combine(inicio, time.min), fim_exclusivo]
    where = "h.data_hora >= %s AND h.data_hora < %s"
    if resultado in {"APROVADO", "NEGADO", "LIBERADO_MANUAL"}:
        where += " AND h.resultado=%s"
        params.append(resultado)
    rows = consultar(f"""SELECT h.id, h.aluno_id, a.nome, h.data_hora, h.resultado, h.motivo
        FROM historico_acessos h JOIN alunos a ON a.id=h.aluno_id
        WHERE {where} ORDER BY h.data_hora DESC LIMIT 5000""", tuple(params))
    return rows


@router.get("/dashboard")
def dashboard(_: dict = Depends(exigir_login)):
    hoje = date.today()
    inicio = datetime.combine(hoje, time.min)
    fim = datetime.combine(hoje + timedelta(days=1), time.min)
    r = um("""SELECT
      SUM(resultado IN ('APROVADO','LIBERADO_MANUAL')) AS entradas,
      SUM(resultado='NEGADO') AS negados,
      SUM(resultado='LIBERADO_MANUAL') AS manuais
      FROM historico_acessos WHERE data_hora >= %s AND data_hora < %s""", (inicio, fim)) or {}
    dentro = um("""SELECT COUNT(DISTINCT aluno_id) AS total FROM historico_acessos
      WHERE resultado IN ('APROVADO','LIBERADO_MANUAL') AND data_hora >= %s""", (inicio,)) or {}
    por_hora = consultar("""SELECT HOUR(data_hora) AS hora, COUNT(*) AS total
      FROM historico_acessos WHERE resultado IN ('APROVADO','LIBERADO_MANUAL') AND data_hora >= %s AND data_hora < %s
      GROUP BY HOUR(data_hora) ORDER BY hora""", (inicio, fim))
    recentes = consultar("""SELECT h.id, h.aluno_id, a.nome, h.data_hora, h.resultado, h.motivo
      FROM historico_acessos h JOIN alunos a ON a.id=h.aluno_id
      WHERE h.data_hora >= %s AND h.data_hora < %s ORDER BY h.data_hora DESC LIMIT 12""", (inicio, fim))
    return {"entradas": int(r.get("entradas") or 0), "negados": int(r.get("negados") or 0),
            "manuais": int(r.get("manuais") or 0), "dentro": int(dentro.get("total") or 0),
            "por_hora": por_hora, "recentes": recentes}
