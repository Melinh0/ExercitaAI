import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from servicos.rag import index_all
from servicos.chunks import is_usable_chunk
from servicos.pesos_correcao import correction_weights
from core.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.60"))
DEFAULT_RETRIEVE_N_RESULTS = int(os.getenv("RAG_N_RESULTS", "8"))


@router.post("/index", response_model=dict)
def index():
    return index_all()


class IndexDocumentsRequest(BaseModel):
    chunks: List[str]
    metadatas: List[dict]


def _indice_responde(vector_store, topic, texto):
    if not topic or not texto:
        return False
    try:
        from core.embeddings import embedder
        embedding = embedder.encode_queries([texto])[0]
        resposta = vector_store.collection.query(
            query_embeddings=[embedding],
            n_results=1,
            where={"topic": {"$eq": topic}},
        )
        documentos = (resposta or {}).get("documents") or []
        return bool(documentos and documentos[0])
    except Exception as e:
        logger.warning(f"[index_documents] verificacao de visibilidade falhou: {e}")
        return False


@router.post("/index_documents")
def index_documents(req: IndexDocumentsRequest):
    try:
        if len(req.chunks) != len(req.metadatas):
            return {
                "status": "error",
                "message": "Numero de chunks e metadatas nao coincide"
            }
        vector_store = VectorStore(collection_name="documents")
        ids = []
        kept_chunks = []
        kept_metadatas = []
        skipped = 0
        for i, (chunk, meta) in enumerate(zip(req.chunks, req.metadatas)):
            if not is_usable_chunk(chunk):
                skipped += 1
                continue
            meta_dict = meta if isinstance(meta, dict) else {}
            global_idx = meta_dict.get('chunk_index', i)
            dono = meta_dict.get('user_id')
            prefixo_dono = f"{dono}_" if dono not in (None, "") else ""
            doc_id = (
                f"{prefixo_dono}"
                f"{meta_dict.get('topic', 'unknown')}_"
                f"{meta_dict.get('source', 'unknown')}_"
                f"{global_idx}"
            )
            ids.append(doc_id)
            kept_chunks.append(chunk)
            kept_metadatas.append(meta)
        if kept_chunks:
            try:
                existentes = vector_store.collection.get(
                    ids=ids, include=["documents", "metadatas"]
                )
                docs_prev = dict(
                    zip(existentes.get("ids") or [],
                        existentes.get("documents") or [])
                )
                metas_prev = dict(
                    zip(existentes.get("ids") or [],
                        existentes.get("metadatas") or [])
                )
            except Exception as e:
                logger.warning(
                    f"[index_documents] leitura de chunks existentes falhou: {e}"
                )
                docs_prev, metas_prev = {}, {}
            novos_ids, novos_chunks, novos_metas = [], [], []
            reaproveitados = 0
            for uid, chunk, meta in zip(ids, kept_chunks, kept_metadatas):
                if (uid in docs_prev and docs_prev.get(uid) == chunk
                        and metas_prev.get(uid) == meta):
                    reaproveitados += 1
                    continue
                novos_ids.append(uid)
                novos_chunks.append(chunk)
                novos_metas.append(meta)
            if novos_ids:
                vector_store.upsert_documents(
                    novos_ids, novos_chunks, novos_metas
                )
            topico_alvo = next(
                (m.get("topic") for m in kept_metadatas
                 if isinstance(m, dict) and m.get("topic")),
                None,
            )
            visivel = _indice_responde(vector_store, topico_alvo, kept_chunks[0])
            logger.info(
                f"[index_documents] aceitos={len(kept_chunks)} novos={len(novos_ids)} "
                f"reaproveitados={reaproveitados} descartados={skipped} "
                f"visivel={visivel} (total recebidos={len(req.chunks)})"
            )
            return {
                "status": "ok",
                "count": len(kept_chunks),
                "novos": len(novos_ids),
                "reaproveitados": reaproveitados,
                "visivel": visivel,
                "skipped": skipped,
            }
        logger.warning(
            f"[index_documents] nenhum chunk utilizavel em {len(req.chunks)} recebidos."
        )
        return {
            "status": "ok",
            "count": 0,
            "novos": 0,
            "reaproveitados": 0,
            "visivel": False,
            "skipped": skipped,
        }
    except Exception as e:
        logger.exception(f"Erro no index_documents: {e}")
        return {"status": "error", "message": str(e)}


class RemoveTopicVectorsRequest(BaseModel):
    topic: str
    user_id: int | None = None
    source: str | None = None


def _montar_where_tema(topic, user_id=None, source=None):
    conditions = [{"topic": {"$eq": topic}}]
    if user_id is not None:
        conditions.append({"user_id": {"$eq": str(user_id)}})
    if source:
        conditions.append({"source": {"$eq": source}})
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


@router.post("/remove_topic_vectors")
def remove_topic_vectors(req: RemoveTopicVectorsRequest):
    try:
        where_filter = _montar_where_tema(req.topic, req.user_id, req.source)
        removidos = 0
        for nome_colecao in ("documents", "examples"):
            try:
                vector_store = VectorStore(collection_name=nome_colecao)
                alvo = vector_store.collection.get(where=where_filter)
                ids = (alvo or {}).get("ids") or []
                if ids:
                    vector_store.collection.delete(ids=ids)
                    removidos += len(ids)
            except Exception as e:
                logger.warning(
                    f"[remove_topic_vectors] falha na colecao "
                    f"'{nome_colecao}': {e}"
                )
        logger.info(
            f"[remove_topic_vectors] topico='{req.topic}' "
            f"user_id={req.user_id} source={req.source} "
            f"-> {removidos} vetor(es) removidos."
        )
        return {
            "status": "ok",
            "topic": req.topic,
            "removidos": removidos,
        }
    except Exception as e:
        logger.exception(f"Erro no remove_topic_vectors: {e}")
        return {"status": "error", "message": str(e)}


class RenameTopicVectorsRequest(BaseModel):
    old_topic: str
    new_topic: str
    user_id: int | None = None


@router.post("/rename_topic_vectors")
def rename_topic_vectors(req: RenameTopicVectorsRequest):
    try:
        where_filter = _montar_where_tema(req.old_topic, req.user_id)
        migrados = 0
        for nome_colecao in ("documents", "examples"):
            try:
                vector_store = VectorStore(collection_name=nome_colecao)
                alvo = vector_store.collection.get(
                    where=where_filter,
                    include=["documents", "metadatas", "embeddings"],
                )
                ids = (alvo or {}).get("ids") or []
                if not ids:
                    continue
                docs = (alvo or {}).get("documents") or []
                metas = (alvo or {}).get("metadatas") or []
                embs = (alvo or {}).get("embeddings")
                if embs is None:
                    logger.warning(
                        f"[rename_topic_vectors] embeddings ausentes na "
                        f"colecao '{nome_colecao}'; colecao ignorada."
                    )
                    continue
                novos_ids = []
                novas_metas = []
                for i, old_id in enumerate(ids):
                    novo_id = (
                        old_id.replace(req.old_topic, req.new_topic, 1)
                        if req.old_topic in old_id else old_id
                    )
                    meta = dict(metas[i] or {})
                    meta["topic"] = req.new_topic
                    novos_ids.append(novo_id)
                    novas_metas.append(meta)
                vector_store.collection.delete(ids=ids)
                vector_store.collection.add(
                    ids=novos_ids,
                    embeddings=embs,
                    documents=docs,
                    metadatas=novas_metas,
                )
                migrados += len(ids)
            except Exception as e:
                logger.warning(
                    f"[rename_topic_vectors] falha na colecao "
                    f"'{nome_colecao}': {e}"
                )
        logger.info(
            f"[rename_topic_vectors] '{req.old_topic}' -> '{req.new_topic}' "
            f"user_id={req.user_id} -> {migrados} vetor(es) migrados."
        )
        return {
            "status": "ok",
            "old_topic": req.old_topic,
            "new_topic": req.new_topic,
            "migrados": migrados,
        }
    except Exception as e:
        logger.exception(f"Erro no rename_topic_vectors: {e}")
        return {"status": "error", "message": str(e)}


class RetrieveContextRequest(BaseModel):
    topic: str
    query: str
    n_results: int = DEFAULT_RETRIEVE_N_RESULTS
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    user_id: int | None = None
    ollama_keys: List[str] | None = None
    exclude_source: str | None = None
    debug: bool = False


@router.post("/retrieve_context")
def retrieve_context(req: RetrieveContextRequest):
    try:
        from core.embeddings import embedder
        vector_store = VectorStore(collection_name="documents")

        conditions = [{"topic": {"$eq": req.topic}}]
        if req.user_id is not None:
            conditions.append({"user_id": {"$eq": str(req.user_id)}})
        where_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        logger.info(
            f"[retrieve_context] topic={req.topic} user_id={req.user_id} "
            f"n_results={req.n_results} threshold={req.similarity_threshold} "
            f"exclude_source={req.exclude_source}"
        )

        query_embedding = embedder.encode_queries([req.query])[0]

        results = vector_store.collection.query(
            query_embeddings=[query_embedding],
            n_results=req.n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        if not (results and results.get('documents') and results['documents'][0]):
            logger.info(f"[retrieve_context] topic={req.topic} sem documentos")
            if req.debug:
                return {
                    "context": "",
                    "diagnostics": {
                        "topic": req.topic,
                        "query_preview": (req.query or "")[:300],
                        "threshold": req.similarity_threshold,
                        "n_raw": 0,
                        "n_after_threshold": 0,
                        "n_self_match_filtered": 0,
                        "n_unusable_filtered": 0,
                        "chunks": [],
                    }
                }
            return {"context": ""}

        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        ids = results['ids'][0]
        distances = (
            results['distances'][0] if results.get('distances')
            else [1.0] * len(documents)
        )

        exclude_lower = (req.exclude_source or "").strip().lower()

        diagnostics_chunks = []
        passing_docs = []
        n_self_match_filtered = 0
        n_unusable_filtered = 0

        for i, doc in enumerate(documents):
            doc_id = ids[i]
            meta = metadatas[i] if i < len(metadatas) else {}
            source = (meta or {}).get("source", "") if isinstance(meta, dict) else ""
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 - distance

            if exclude_lower and source.lower() == exclude_lower:
                n_self_match_filtered += 1
                diagnostics_chunks.append({
                    "id": doc_id,
                    "rank_original": i,
                    "distance": round(float(distance), 4),
                    "similarity": round(float(similarity), 4),
                    "weight": 0.0,
                    "weighted_score": 0.0,
                    "passed": False,
                    "self_match_filtered": True,
                    "unusable_filtered": False,
                    "source": source,
                    "chunk_index": (
                        (meta or {}).get("chunk_index", None)
                        if isinstance(meta, dict) else None
                    ),
                    "preview": (doc or "")[:200].replace("\n", " "),
                })
                continue

            if not is_usable_chunk(doc):
                n_unusable_filtered += 1
                diagnostics_chunks.append({
                    "id": doc_id,
                    "rank_original": i,
                    "distance": round(float(distance), 4),
                    "similarity": round(float(similarity), 4),
                    "weight": 0.0,
                    "weighted_score": 0.0,
                    "passed": False,
                    "self_match_filtered": False,
                    "unusable_filtered": True,
                    "source": source,
                    "chunk_index": (
                        (meta or {}).get("chunk_index", None)
                        if isinstance(meta, dict) else None
                    ),
                    "preview": (doc or "")[:200].replace("\n", " "),
                })
                continue

            weight = correction_weights.get(doc_id, 1.0)
            weighted_score = similarity * weight
            passed = similarity >= req.similarity_threshold

            diagnostics_chunks.append({
                "id": doc_id,
                "rank_original": i,
                "distance": round(float(distance), 4),
                "similarity": round(float(similarity), 4),
                "weight": round(float(weight), 4),
                "weighted_score": round(float(weighted_score), 4),
                "passed": passed,
                "self_match_filtered": False,
                "unusable_filtered": False,
                "source": source,
                "chunk_index": (
                    (meta or {}).get("chunk_index", None)
                    if isinstance(meta, dict) else None
                ),
                "preview": (doc or "")[:200].replace("\n", " "),
            })

            if passed:
                passing_docs.append((weighted_score, doc, meta))

        passing_docs.sort(key=lambda x: x[0], reverse=True)
        context = "\n\n".join([doc for _, doc, _ in passing_docs])

        logger.info(
            f"[retrieve_context] topic={req.topic} user_id={req.user_id} "
            f"n_raw={len(documents)} n_passou={len(passing_docs)} "
            f"n_self_match_filtered={n_self_match_filtered} "
            f"n_unusable_filtered={n_unusable_filtered} "
            f"ctx_chars={len(context)} threshold={req.similarity_threshold}"
        )

        for diag in diagnostics_chunks:
            if diag.get("self_match_filtered"):
                marker = "SELF"
            elif diag.get("unusable_filtered"):
                marker = "BAD "
            elif diag["passed"]:
                marker = "OK  "
            else:
                marker = "DESC"
            logger.info(
                f"[retrieve_context]   [{marker}] id={diag['id']} "
                f"sim={diag['similarity']:.3f} w={diag['weight']:.2f} "
                f"score={diag['weighted_score']:.3f} | {diag['preview'][:120]}"
            )

        if req.debug:
            return {
                "context": context,
                "diagnostics": {
                    "topic": req.topic,
                    "query_preview": (req.query or "")[:300],
                    "threshold": req.similarity_threshold,
                    "n_raw": len(documents),
                    "n_after_threshold": len(passing_docs),
                    "n_self_match_filtered": n_self_match_filtered,
                    "n_unusable_filtered": n_unusable_filtered,
                    "chunks": diagnostics_chunks,
                }
            }
        return {"context": context}

    except Exception as e:
        logger.exception(f"Erro em /retrieve_context: {e}")
        if req.debug:
            return {"context": "", "diagnostics": {"error": str(e)}}
        return {"context": ""}


class GetTopicChunksRequest(BaseModel):
    topic: str


@router.post("/get_topic_chunks")
def get_topic_chunks(req: GetTopicChunksRequest):
    try:
        vector_store = VectorStore(collection_name="documents")
        collection = vector_store.collection

        all_ids = []
        page_size = 100
        offset = 0
        max_iterations = 1000
        previous_first_id = None
        pagination_ok = True

        for _ in range(max_iterations):
            try:
                res = collection.get(
                    where={"topic": {"$eq": req.topic}},
                    include=["metadatas"],
                    limit=page_size,
                    offset=offset,
                )
            except TypeError:
                pagination_ok = False
                break

            ids = res.get("ids", []) or []
            if not ids:
                break

            current_first_id = ids[0]
            if current_first_id == previous_first_id:
                logger.warning(
                    f"[get_topic_chunks] offset ignorado em offset={offset}. "
                    f"Paginacao falhou. Usando fallback single-call."
                )
                pagination_ok = False
                break
            previous_first_id = current_first_id

            all_ids.extend(ids)
            offset += len(ids)

            if len(ids) < page_size:
                break

        if not pagination_ok:
            logger.warning(
                f"[get_topic_chunks] Paginacao falhou em topic={req.topic}. "
                f"Descartando {len(all_ids)} ids e usando single-call."
            )
            all_ids = []

        if not all_ids:
            try:
                res = collection.get(
                    where={"topic": {"$eq": req.topic}},
                    include=["documents", "metadatas"],
                )
                docs = res.get("documents", []) or []
                metas = res.get("metadatas", []) or []
                ids_full = res.get("ids", []) or []
                logger.info(
                    f"[get_topic_chunks] single-call topic={req.topic} "
                    f"chunks={len(docs)}"
                )
                return {
                    "chunks": docs,
                    "metadatas": metas,
                    "ids": ids_full,
                    "count": len(docs),
                }
            except Exception as e:
                logger.exception(f"[get_topic_chunks] single-call falhou: {e}")
                return {"chunks": [], "metadatas": [], "ids": [], "count": 0}

        all_documents = []
        all_metadatas = []
        all_ids_final = []
        id_batch = 200
        for i in range(0, len(all_ids), id_batch):
            batch_ids = all_ids[i:i + id_batch]
            try:
                res = collection.get(
                    ids=batch_ids,
                    include=["documents", "metadatas"],
                )
                docs = res.get("documents", []) or []
                metas = res.get("metadatas", []) or []
                ids_b = res.get("ids", []) or []
                all_documents.extend(docs)
                all_metadatas.extend(metas)
                all_ids_final.extend(ids_b)
            except Exception as e:
                logger.warning(f"[get_topic_chunks] falha em lote {i}: {e}")

        logger.info(
            f"[get_topic_chunks] topic={req.topic} chunks={len(all_documents)} "
            f"(ids coletados={len(all_ids)})"
        )
        return {
            "chunks": all_documents,
            "metadatas": all_metadatas,
            "ids": all_ids_final,
            "count": len(all_documents),
        }
    except Exception as e:
        logger.exception(f"Erro em /get_topic_chunks: {e}")
        return {"chunks": [], "metadatas": [], "ids": [], "count": 0}
