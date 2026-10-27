import hmac
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, field_validator

from ..config import settings
from ..db import agora, consultar, executar, novo_id, transacao, um
from ..limite import limiter
from ..security import criar_token, hash_senha, hmac_hex, senha_confere, exigir_login

router = APIRouter()
ERRO_LOGIN = HTTPException(401, "E-mail ou senha incorretos")  # mesma resposta para os dois casos


class LoginIn(BaseModel):
    email: EmailStr
    senha: str


class EmailIn(BaseModel):
    email: EmailStr


class RedefinirIn(BaseModel):
    email: EmailStr
    codigo: str
    nova_senha: str

    @field_validator("nova_senha")
    @classmethod
    def forte(cls, v):
        if len(v) < 8 or not re.search(r"[A-Z]", v) or not re.search(r"\d", v):
            raise ValueError("Senha fraca")
        return v


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, dados: LoginIn, resp: Response):
    op = um("SELECT * FROM operadores WHERE email=%s", (dados.email.lower(),))
    if not op:
        hash_senha("tempo-constante")
        raise ERRO_LOGIN
    if op["bloqueado_ate"] and op["bloqueado_ate"] > agora():
        raise HTTPException(429, "Muitas tentativas. Tente em 15 minutos.")
    if not senha_confere(op["senha_hash"], dados.senha):
        t = op["tentativas"] + 1
        executar("UPDATE operadores SET tentativas=%s, bloqueado_ate=%s WHERE id=%s",
                 (0 if t >= 5 else t, agora() + timedelta(minutes=15) if t >= 5 else None, op["id"]))
        raise ERRO_LOGIN
    executar("UPDATE operadores SET tentativas=0, bloqueado_ate=NULL WHERE id=%s", (op["id"],))
    resp.set_cookie("token", criar_token(op), httponly=True, secure=settings.producao,
                    samesite="strict", max_age=8 * 3600)
    return {"id": op["id"], "nome": op["nome"], "email": op["email"], "papel": op["papel"]}


@router.get("/me")
def me(op: dict = Depends(exigir_login)):
    return {"id": op["sub"], "nome": op["nome"], "papel": op["papel"]}

@router.get("/usuarios-login")
def usuarios_login():
    """Lista apenas os dados públicos necessários para montar os perfis na tela de login.

    Senhas e hashes nunca são retornados. O endpoint é público de propósito: a tela de login
    precisa saber quais contas ativas podem ser selecionadas antes da autenticação.
    """
    linhas = consultar(
        "SELECT id, nome, email, papel FROM operadores ORDER BY nome LIMIT 500"
    )
    return [
        {"id": r["id"], "nome": r["nome"], "email": r["email"], "papel": r["papel"], "ativo": True}
        for r in linhas
    ]


@router.post("/logout", status_code=204)
def logout(resp: Response):
    resp.delete_cookie("token")


@router.post("/esqueci-senha")
@limiter.limit("5/minute")
def esqueci(request: Request, dados: EmailIn):
    op = um("SELECT id, email FROM operadores WHERE email=%s", (dados.email.lower(),))
    if op:
        codigo = str(secrets.randbelow(900000) + 100000)
        executar("INSERT INTO reset_senha (id, operador_id, codigo_hash, expira_em) VALUES (%s,%s,%s,%s)",
                 (novo_id(), op["id"], hmac_hex(codigo), agora() + timedelta(minutes=10)))
        # TODO: enviar por e-mail (Resend, SES, SMTP). Em desenvolvimento só escreve no console.
        if not settings.producao:
            print(f"[email dev] código para {op['email']}: {codigo}")
    return {"ok": True}  # resposta igual exista ou não o e-mail


@router.post("/redefinir-senha")
@limiter.limit("10/minute")
def redefinir(request: Request, dados: RedefinirIn):
    op = um("SELECT id FROM operadores WHERE email=%s", (dados.email.lower(),))
    r = op and um("""SELECT id, codigo_hash FROM reset_senha
                     WHERE operador_id=%s AND usado=0 AND expira_em>%s ORDER BY expira_em DESC LIMIT 1""",
                  (op["id"], agora()))
    if not r or not hmac.compare_digest(r["codigo_hash"], hmac_hex(dados.codigo)):
        raise HTTPException(400, "Código inválido ou vencido")
    with transacao() as cur:
        cur.execute("UPDATE operadores SET senha_hash=%s WHERE id=%s", (hash_senha(dados.nova_senha), op["id"]))
        cur.execute("UPDATE reset_senha SET usado=1 WHERE operador_id=%s", (op["id"],))
    return {"ok": True}
