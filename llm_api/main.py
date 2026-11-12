import asyncio
import logging

from fastapi import FastAPI

from llm import provedores
from llm.ollama_client import chaves_do_usuario
from routers import analise, correcoes, geracao, modelos, ocr, utilitarios, vetores
from core.vector_store import VectorStore

logger = logging.getLogger(__name__)

app = FastAPI(title="RAG LLM Service")


class MiddlewareChavesOllama:
    def __init__(self, aplicacao):
        self.aplicacao = aplicacao

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.aplicacao(scope, receive, send)
            return
        bruto = ""
        for nome, valor in scope.get("headers", []):
            if nome.lower() == b"x-ollama-keys":
                bruto = valor.decode("latin-1", "ignore")
                break
        chaves = [c.strip() for c in bruto.split(",") if c.strip()]
        chaves_ollama, chaves_provedor = provedores.separar_chaves(chaves)
        token = chaves_do_usuario.set(chaves_ollama or None)
        token_provedores = provedores.chaves_de_provedores.set(chaves_provedor or None)
        try:
            await self.aplicacao(scope, receive, send)
        finally:
            chaves_do_usuario.reset(token)
            provedores.chaves_de_provedores.reset(token_provedores)


app.add_middleware(MiddlewareChavesOllama)

for router in (
    modelos.router,
    geracao.router,
    analise.router,
    ocr.router,
    vetores.router,
    correcoes.router,
    utilitarios.router,
):
    app.include_router(router)


def warmup_vector_store():
    try:
        logger.info("Pre-carregando VectorStore (download do modelo ONNX)...")
        store = VectorStore(collection_name="documents")
        store.query("dummy", n_results=1)
        logger.info("VectorStore pronto.")
    except Exception as e:
        logger.warning(f"Warmup falhou: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(asyncio.to_thread(warmup_vector_store))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
