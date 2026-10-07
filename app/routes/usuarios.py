from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from ..db import consultar, novo_id, executar, um, transacao
from ..security import exigir_admin, hash_senha

router = APIRouter()


Papel = Literal["ADMIN", "RECEPCAO"]


class UsuarioIn(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=255)
    papel: Papel = "RECEPCAO"

    @field_validator("nome")
    @classmethod
    def nome_limpo(cls, v):
        return " ".join(v.split())


class UsuarioPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=120)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=255)
    papel: Papel | None = None

    @field_validator("nome")
    @classmethod
    def nome_limpo(cls, v):
        return " ".join(v.split()) if v else v


def _usuario(row: dict) -> dict:
    return {
        "id": row["id"],
        "nome": row["nome"],
        "email": row["email"],
        "papel": row["papel"],
        "ativo": True,
        "criado_em": row["criado_em"],
    }


@router.get("")
def listar(_: dict = Depends(exigir_admin)):
    linhas = consultar(
        "SELECT id, nome, email, papel, criado_em FROM operadores ORDER BY nome LIMIT 500"
    )
    return [_usuario(r) for r in linhas]


@router.post("", status_code=201)
def criar(d: UsuarioIn, _: dict = Depends(exigir_admin)):
    email = d.email.lower()
    if um("SELECT id FROM operadores WHERE email=%s", (email,)):
        raise HTTPException(409, "E-mail já cadastrado")
    uid = novo_id()
    executar(
        "INSERT INTO operadores (id, nome, email, senha_hash, papel) VALUES (%s,%s,%s,%s,%s)",
        (uid, d.nome, email, hash_senha(d.senha), d.papel),
    )
    return {"id": uid}


@router.patch("/{usuario_id}")
def atualizar(usuario_id: str, d: UsuarioPatch, op: dict = Depends(exigir_admin)):
    atual = um("SELECT id, nome, email, papel FROM operadores WHERE id=%s", (usuario_id,))
    if not atual:
        raise HTTPException(404, "Usuário não encontrado")

    if d.email is not None:
        email = d.email.lower()
        outro = um("SELECT id FROM operadores WHERE email=%s AND id<>%s", (email, usuario_id))
        if outro:
            raise HTTPException(409, "E-mail já cadastrado")
    else:
        email = atual["email"]

    papel = d.papel or atual["papel"]
    if usuario_id == op["sub"] and papel != "ADMIN":
        raise HTTPException(400, "O administrador logado não pode remover a própria função administrativa")
    if atual["papel"] == "ADMIN" and papel != "ADMIN":
        qtd = um("SELECT COUNT(*) AS total FROM operadores WHERE papel='ADMIN'")["total"]
        if qtd <= 1:
            raise HTTPException(400, "Mantenha pelo menos um administrador cadastrado")

    nome = d.nome or atual["nome"]
    with transacao() as cur:
        cur.execute("UPDATE operadores SET nome=%s, email=%s, papel=%s WHERE id=%s",
                    (nome, email, papel, usuario_id))
        if d.senha:
            cur.execute("UPDATE operadores SET senha_hash=%s WHERE id=%s",
                        (hash_senha(d.senha), usuario_id))
    return {"ok": True}


@router.delete("/{usuario_id}", status_code=204)
def remover(usuario_id: str, op: dict = Depends(exigir_admin)):
    atual = um("SELECT id, nome, papel FROM operadores WHERE id=%s", (usuario_id,))
    if not atual:
        raise HTTPException(404, "Usuário não encontrado")
    if usuario_id == op["sub"]:
        raise HTTPException(400, "Você não pode excluir o próprio usuário logado")
    if atual["papel"] == "ADMIN":
        qtd = um("SELECT COUNT(*) AS total FROM operadores WHERE papel='ADMIN'")["total"]
        if qtd <= 1:
            raise HTTPException(400, "Mantenha pelo menos um administrador cadastrado")
    dependencias = um("SELECT COUNT(*) AS total FROM log_liberacoes WHERE operador_id=%s", (usuario_id,))["total"]
    if dependencias:
        raise HTTPException(409, "Este usuário possui liberações registradas no histórico e não pode ser apagado")
    try:
        executar("DELETE FROM operadores WHERE id=%s", (usuario_id,))
    except Exception as exc:
        raise HTTPException(409, "Não foi possível apagar este usuário porque existem registros vinculados") from exc
