"""Aplica as migrations de sql/migrations em ordem e anota quais já rodaram.
Uso: python -m app.migrar
"""
import re
from pathlib import Path

from .db import consultar, executar, transacao

PASTA = Path(__file__).resolve().parent.parent / "sql" / "migrations"
JA_NO_SCHEMA = {"001_alunos_crud.sql", "002_planos_integracao.sql"}  # já incluídas no schema.sql


def comandos(texto: str) -> list[str]:
    texto = re.sub(r"--[^\n]*", "", texto)  # tira comentários
    return [c.strip() for c in texto.split(";") if c.strip()]


def main() -> None:
    executar("CREATE TABLE IF NOT EXISTS schema_migracoes ("
             "nome VARCHAR(120) PRIMARY KEY, aplicada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    feitas = {r["nome"] for r in consultar("SELECT nome FROM schema_migracoes")}
    for arq in sorted(PASTA.glob("*.sql")):
        if arq.name in feitas or arq.name in JA_NO_SCHEMA:
            continue
        print("aplicando", arq.name)
        with transacao() as cur:
            for cmd in comandos(arq.read_text(encoding="utf-8")):
                cur.execute(cmd)
            cur.execute("INSERT INTO schema_migracoes (nome) VALUES (%s)", (arq.name,))
    print("Banco atualizado.")


if __name__ == "__main__":
    main()