import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Cookie, HTTPException

from .config import settings
from .db import um

_ph = PasswordHasher()
_chave = base64.b64decode(settings.encryption_key)
_chave_hash = base64.b64decode(settings.hash_key)


def hash_senha(s: str) -> str:
    return _ph.hash(s)


def senha_confere(h: str, s: str) -> bool:
    try:
        return _ph.verify(h, s)
    except VerifyMismatchError:
        return False


def cifrar(t: str) -> str:  # AES-256-GCM: CPF e foto são cifrados antes de ir ao banco
    n = os.urandom(12)
    return base64.b64encode(n + AESGCM(_chave).encrypt(n, t.encode(), None)).decode()


def decifrar(b: str) -> str:
    r = base64.b64decode(b)
    return AESGCM(_chave).decrypt(r[:12], r[12:], None).decode()


def hmac_hex(t: str) -> str:  # hash com chave: busca/duplicidade sem guardar o CPF em claro
    return hmac.new(_chave_hash, t.encode(), hashlib.sha256).hexdigest()


def mascarar_cpf(c: str) -> str:
    return f"***.{c[3:6]}.{c[6:9]}-**"


def criar_token(op: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({"sub": op["id"], "papel": op["papel"], "nome": op["nome"], "exp": exp},
                      settings.jwt_secret, algorithm="HS256")


def ler_token(t: str) -> dict:
    return jwt.decode(t, settings.jwt_secret, algorithms=["HS256"])


def exigir_login(token: str | None = Cookie(default=None)) -> dict:
    try:
        return ler_token(token or "")
    except jwt.PyJWTError:
        raise HTTPException(401, "Faça login para continuar")


def exigir_admin(token: str | None = Cookie(default=None)) -> dict:
    op = exigir_login(token)
    atual = um("SELECT id, nome, papel FROM operadores WHERE id=%s", (op.get("sub"),))
    if not atual:
        raise HTTPException(401, "Usuário não encontrado")
    if atual["papel"] != "ADMIN":
        raise HTTPException(403, "Acesso administrativo necessário")
    return {**op, "papel": atual["papel"], "nome": atual["nome"]}
