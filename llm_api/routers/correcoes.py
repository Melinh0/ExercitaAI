import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import BASE_DIR
from core.corrections_store import corrections_store
from servicos.pesos_correcao import correction_weights, save_correction_weights
from core.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter()


class AddCorrectionRequest(BaseModel):
    original_json: dict
    corrected_json: dict
    metadata: dict = {}


@router.post("/add_correction")
def add_correction(req: AddCorrectionRequest):
    try:
        import uuid
        correction_id = str(uuid.uuid4())
        corrections_store.add_correction(
            correction_id, req.original_json, req.corrected_json, req.metadata
        )
        doc_id = (
            f"{req.metadata.get('topic', '')}_"
            f"{req.metadata.get('image', '')}_"
            f"{req.metadata.get('q_idx', '')}"
        )
        if doc_id:
            correction_weights[doc_id] = correction_weights.get(doc_id, 1.0) + 0.1
            save_correction_weights()
        return {"status": "ok", "id": correction_id}
    except Exception as e:
        logger.exception(f"Erro ao adicionar correcao: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AddExampleRequest(BaseModel):
    document: str
    metadata: dict


@router.post("/add_example")
def add_example(req: AddExampleRequest):
    try:
        vector_store = VectorStore(collection_name="examples")
        metadata = req.metadata
        topic = metadata.get("topic", "")
        image = metadata.get("image", "")
        question_num = metadata.get("question_index", "")
        if topic and image and question_num is not None:
            dono = metadata.get("user_id")
            prefixo = f"{dono}:" if dono not in (None, "") else ""
            doc_id = f"{prefixo}{topic}:{image}:{question_num}"
        else:
            import uuid
            doc_id = str(uuid.uuid4())
        try:
            vector_store.collection.delete(ids=[doc_id])
        except Exception:
            pass
        vector_store.add_documents([doc_id], [req.document], [metadata])
        return {"status": "ok", "id": doc_id}
    except Exception as e:
        logger.exception(f"Erro ao adicionar exemplo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RetrieveExamplesRequest(BaseModel):
    query: str
    n_results: int = 3
    include_images: bool = False
    user_id: int | None = None


class RetrieveExamplesResponse(BaseModel):
    examples: list = []


@router.post("/retrieve_examples", response_model=RetrieveExamplesResponse)
def retrieve_examples(req: RetrieveExamplesRequest):
    try:
        vector_store = VectorStore(collection_name="examples")
        where_user = (
            {"user_id": {"$eq": str(req.user_id)}}
            if req.user_id is not None else None
        )
        results = vector_store.query(
            req.query, n_results=req.n_results, where=where_user
        )
        examples = []
        if results["metadatas"] and results["metadatas"][0]:
            for meta in results["metadatas"][0]:
                example = meta.copy()
                if req.include_images:
                    whiteboard_path = meta.get("whiteboard_img_path")
                    if whiteboard_path:
                        full_path = BASE_DIR / "backend" / "static" / whiteboard_path
                        if full_path.exists():
                            with open(full_path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode("utf-8")
                                example["whiteboard_img_base64"] = img_data
                examples.append(example)
        return {"examples": examples}
    except Exception:
        return {"examples": []}
