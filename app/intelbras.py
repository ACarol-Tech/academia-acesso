"""Integração com a catraca Intelbras.

ATENÇÃO: os caminhos e o corpo das requisições variam conforme o modelo. Confira no manual
da API do SEU aparelho (ou teste no Postman) e ajuste aqui e no .env. Alguns modelos usam
Digest Auth em vez de Basic: nesse caso troque a linha `auth=` por httpx.DigestAuth(...).

Com CATRACA_SIMULADA=true no .env, nada é enviado à catraca (útil para desenvolver sem o aparelho).
"""
import httpx

from .config import settings


def _cliente() -> httpx.Client:
    return httpx.Client(base_url=f"http://{settings.catraca_host}", timeout=5,
                        auth=(settings.catraca_user, settings.catraca_pass))


def abrir_porta() -> None:
    if settings.catraca_simulada:
        print("[catraca simulada] porta aberta")
        return
    with _cliente() as c:
        c.post(settings.catraca_path_abrir).raise_for_status()


def cadastrar_face(user_id: str, nome: str, foto_base64: str) -> None:
    if settings.catraca_simulada:
        print(f"[catraca simulada] face cadastrada: {nome}")
        return
    with _cliente() as c:
        c.post(settings.catraca_path_usuario,
               json={"userId": user_id, "name": nome, "photo": foto_base64}).raise_for_status()