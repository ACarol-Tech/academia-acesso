from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .limite import limiter
from .realtime import manager
from .routes import alunos, auth, catraca, planos, relatorios, usuarios
from .security import ler_token

# em produção a documentação automática fica desligada
app = FastAPI(title="Academia · Controle de acesso",
              docs_url=None if settings.producao else "/docs", redoc_url=None,
              openapi_url=None if settings.producao else "/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def erro_validacao(request: Request, exc: RequestValidationError):
    """Devolve uma mensagem curta em vez da lista técnica de erros do pydantic."""
    e = exc.errors()[0]
    msg = str(e.get("msg", ""))
    if msg.startswith("Value error, "):
        texto = msg.removeprefix("Value error, ")
    else:
        texto = f"Dado inválido no campo '{e['loc'][-1]}'"
    return JSONResponse(status_code=422, content={"detail": texto})


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url], allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse("docs/demo-completo.html", media_type="text/html")


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next):
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                      "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                      "Strict-Transport-Security": "max-age=31536000"})
    return r


app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(alunos.router, prefix="/api/v1/alunos")
app.include_router(catraca.router, prefix="/api/v1/catraca")
app.include_router(planos.router, prefix="/api/v1/planos")
app.include_router(usuarios.router, prefix="/api/v1/usuarios")
app.include_router(relatorios.router, prefix="/api/v1/relatorios")


@app.websocket("/ws")  # acessos em tempo real: só para quem está logado e vem do nosso site
async def ws(ws: WebSocket):
    try:
        if ws.headers.get("origin") != settings.frontend_url:
            raise ValueError
        ler_token(ws.cookies.get("token", ""))
    except Exception:
        await ws.close(code=1008)
        return
    await manager.conectar(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.sair(ws)
