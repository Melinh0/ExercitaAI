from fastapi import APIRouter
from pydantic import BaseModel

from servicos.link_utils import get_link_summary

router = APIRouter()


class ExtractLinkRequest(BaseModel):
    url: str


class ExtractLinkResponse(BaseModel):
    valid: bool
    content: dict | None = None
    error: str | None = None


@router.post("/extract_link", response_model=ExtractLinkResponse)
def extract_link(req: ExtractLinkRequest):
    try:
        summary = get_link_summary(req.url)
        if summary:
            return ExtractLinkResponse(valid=True, content=summary)
        return ExtractLinkResponse(
            valid=False, error="Nao foi possivel extrair conteudo valido do link."
        )
    except Exception:
        return ExtractLinkResponse(valid=False, error="Erro ao extrair link.")
