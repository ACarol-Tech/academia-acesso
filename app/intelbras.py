"""Integração com os leitores faciais Intelbras (SS 3531 MF Lite): entrada e saída.

ATENÇÃO: os comandos abaixo seguem o padrão CGI que essa linha costuma usar (Digest + /cgi-bin/...),
mas NÃO FORAM VALIDADOS com o manual da Intelbras nem com os leitores. O primeiro teste deve ser a
rota de status (só leitura). Se algum comando for recusado, ajuste apenas as constantes e funções
deste arquivo: o resto do sistema não muda.

Com CATRACA_SIMULADA=true nada é enviado aos leitores (desenvolvimento e testes).
"""
import base64
import binascii
from datetime import date, datetime
from io import BytesIO

import httpx
from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings

# --- Comandos (ajustar aqui quando o manual da API chegar) ---------------------------------
CMD_INFO = "/cgi-bin/magicBox.cgi?action=getSystemInfo"
CMD_ABRIR = "/cgi-bin/accessControl.cgi?action=openDoor&channel=1&Type=Remote"
CMD_USUARIO = "/cgi-bin/AccessUser.cgi?action={acao}"
CMD_FACE = "/cgi-bin/AccessFace.cgi?action={acao}"
# ----------------------------------------------------------------------------------------

LIMITE_FOTO = 98 * 1024  # o leitor aceita fotos de até 100 KB


class FalhaLeitor(Exception):
    """O leitor não respondeu ou recusou o comando."""


def leitores() -> list[tuple[str, str]]:
    lista = [("entrada", settings.catraca_host)]
    if settings.catraca_host_saida:
        lista.append(("saida", settings.catraca_host_saida))
    return lista


def _cliente(host: str) -> httpx.Client:
    esquema = "https" if settings.catraca_https else "http"
    return httpx.Client(base_url=f"{esquema}://{host}", timeout=8, verify=False,
                        auth=httpx.DigestAuth(settings.catraca_user, settings.catraca_pass))


def _chamar(host: str, metodo: str, caminho: str, json=None, params=None) -> str:
    try:
        with _cliente(host) as c:
            r = c.request(metodo, caminho, json=json, params=params)
    except httpx.HTTPError as exc:
        raise FalhaLeitor(f"O leitor {host} não respondeu.") from exc
    texto = r.text.strip()
    if r.status_code != 200 or texto.lower().startswith("error"):
        raise FalhaLeitor(f"O leitor {host} recusou o comando (código {r.status_code}: {texto[:80]!r}).")
    return texto


def _data(d) -> str:
    return d.strftime("%Y-%m-%d 23:59:59") if isinstance(d, (date, datetime)) else str(d)


def _usuario(user_id: str, nome: str, validade) -> dict:
    return {"UserID": user_id, "UserName": nome[:30], "UserType": 0, "Authority": 1, "Doors": [0],
            "TimeSections": [255], "ValidFrom": "2020-01-01 00:00:00", "ValidTo": _data(validade)}


def preparar_foto(foto_base64: str) -> str:
    """Corrige a rotação, reduz e comprime a foto para JPEG de até ~98 KB e 600x1200 px."""
    try:
        img = Image.open(BytesIO(base64.b64decode(foto_base64, validate=True)))
        img.load()
    except (binascii.Error, UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, "Foto inválida. Envie uma imagem JPEG ou PNG.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < 150:
        raise HTTPException(400, "Foto muito pequena. Tire outra, com o rosto bem visível.")
    img.thumbnail((600, 1200))
    for qualidade in (90, 85, 80, 75, 70, 60, 50):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=qualidade, optimize=True)
        if buf.tell() <= LIMITE_FOTO:
            return base64.b64encode(buf.getvalue()).decode()
    raise HTTPException(400, "Não foi possível reduzir a foto ao limite do leitor. Tire outra.")


def status_leitores() -> list[dict]:
    """Consulta de leitura: diz se cada leitor está online. Não altera nada."""
    saida = []
    for nome, host in leitores():
        item = {"leitor": nome, "host": host, "online": False, "modelo": None, "serie": None, "erro": None}
        if settings.catraca_simulada:
            item.update(online=True, modelo="simulado")
        else:
            try:
                info = dict(l.split("=", 1) for l in _chamar(host, "GET", CMD_INFO).splitlines() if "=" in l)
                item.update(online=True, modelo=info.get("deviceType") or info.get("updateSerial"),
                            serie=info.get("serialNumber"))
            except FalhaLeitor as exc:
                item["erro"] = str(exc)
        saida.append(item)
    return saida


def abrir_porta(sentido: str = "entrada") -> None:
    if settings.catraca_simulada:
        print(f"[catraca simulada] porta aberta ({sentido})")
        return
    host = dict(leitores()).get(sentido) or settings.catraca_host
    _chamar(host, "GET", CMD_ABRIR + "&UserID=sistema")


def cadastrar_face(user_id: str, nome: str, foto_base64: str, validade) -> None:
    """Cadastra o aluno e o rosto em todos os leitores. Se algum falhar, desfaz nos que já receberam."""
    foto = preparar_foto(foto_base64)
    if settings.catraca_simulada:
        print(f"[catraca simulada] aluno {user_id} cadastrado: {nome}, válido até {_data(validade)}")
        return
    feitos = []
    try:
        for _, host in leitores():
            _chamar(host, "POST", CMD_USUARIO.format(acao="insertMulti"), json={"UserList": [_usuario(user_id, nome, validade)]})
            feitos.append(host)
            _chamar(host, "POST", CMD_FACE.format(acao="insertMulti"), json={"FaceList": [{"UserID": user_id, "PhotoData": [foto]}]})
    except FalhaLeitor:
        for host in feitos:
            try:
                remover_usuario(user_id, [host])
            except FalhaLeitor:
                pass
        raise


def atualizar_validade(user_id: str, nome: str, validade) -> None:
    """Atualiza até quando o aluno pode entrar (vencimento + tolerância) em todos os leitores."""
    if settings.catraca_simulada:
        print(f"[catraca simulada] validade de {user_id}: {_data(validade)}")
        return
    for _, host in leitores():
        _chamar(host, "POST", CMD_USUARIO.format(acao="updateMulti"), json={"UserList": [_usuario(user_id, nome, validade)]})


def remover_usuario(user_id: str, hosts: list[str] | None = None) -> None:
    if settings.catraca_simulada:
        print(f"[catraca simulada] aluno {user_id} removido")
        return
    for host in hosts or [h for _, h in leitores()]:
        _chamar(host, "GET", CMD_USUARIO.format(acao="removeMulti") + f"&UserIDList[0]={user_id}")