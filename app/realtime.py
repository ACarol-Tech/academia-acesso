from fastapi import WebSocket


class Gerenciador:
    def __init__(self):
        self.ativos: set[WebSocket] = set()

    async def conectar(self, ws: WebSocket):
        await ws.accept()
        self.ativos.add(ws)

    def sair(self, ws: WebSocket):
        self.ativos.discard(ws)

    async def enviar(self, dado: dict):
        for ws in list(self.ativos):
            try:
                await ws.send_json(dado)
            except Exception:
                self.ativos.discard(ws)


manager = Gerenciador()
