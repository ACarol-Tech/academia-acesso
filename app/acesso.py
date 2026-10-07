from datetime import date

from .db import consultar, executar, novo_id, um


def processar(intelbras_user_id: str) -> dict | None:
    """Aplica a regra de negócio ao evento recebido da catraca e grava o histórico."""
    aluno = um("SELECT id, nome FROM alunos WHERE intelbras_user_id=%s", (intelbras_user_id,))
    if not aluno:
        return None
    m = um("""SELECT m.vencimento, p.nome AS plano, p.dias_tolerancia
              FROM matriculas m JOIN planos p ON p.id = m.plano_id
              WHERE m.aluno_id=%s AND m.status='ATIVO' ORDER BY m.criado_em DESC LIMIT 1""", (aluno["id"],))
    resultado, motivo, atraso = "NEGADO", "Sem matrícula ativa", 0
    if m:
        atraso = max(0, (date.today() - m["vencimento"]).days)
        if atraso > m["dias_tolerancia"]:
            motivo = f"Inadimplente: {atraso} dias de atraso"
        else:
            resultado, motivo = "APROVADO", None
    executar("INSERT INTO historico_acessos (id, aluno_id, resultado, motivo) VALUES (%s,%s,%s,%s)",
             (novo_id(), aluno["id"], resultado, motivo))
    # só o necessário vai para a tela: nunca CPF, foto ou dados de cobrança completos
    return {"alunoId": aluno["id"], "nome": aluno["nome"], "plano": m and m["plano"],
            "resultado": resultado, "motivo": motivo, "atraso": atraso}
