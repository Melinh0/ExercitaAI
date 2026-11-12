import logging

from servicos.chunks import is_usable_chunk

logger = logging.getLogger(__name__)

MAX_RAG_TOTAL_CHARS = 2000
MAX_RAG_CHUNK_CHARS = 800
MIN_RAG_CHUNK_CHARS = 100
MIN_RAG_TOTAL_CHARS = 150


def build_context_block(context_texts):
    rag_chunks = []
    other_chunks = []
    for text in context_texts or []:
        if text.startswith("[RAG_BASE]"):
            rag_chunks.append(text[len("[RAG_BASE]"):].strip())
        else:
            other_chunks.append(text)

    block = ""

    if rag_chunks:
        cleaned_chunks = []
        for chunk in rag_chunks:
            if not chunk:
                continue
            chunk = chunk.strip()
            if len(chunk) < MIN_RAG_CHUNK_CHARS:
                continue
            if not is_usable_chunk(chunk):
                logger.info(
                    f"[build_context_block] Chunk descartado (TOC/capa/baixo sinal): "
                    f"{chunk[:80]!r}"
                )
                continue
            if len(chunk) > MAX_RAG_CHUNK_CHARS:
                chunk = chunk[:MAX_RAG_CHUNK_CHARS] + "... (chunk truncado)"
            cleaned_chunks.append(chunk)

        combined_rag = ""
        for chunk in cleaned_chunks:
            separator = "\n\n" if combined_rag else ""
            if len(combined_rag) + len(separator) + len(chunk) > MAX_RAG_TOTAL_CHARS:
                remaining = MAX_RAG_TOTAL_CHARS - len(combined_rag) - len(separator)
                if remaining > 300:
                    combined_rag += separator + chunk[:remaining] + "... (contexto truncado)"
                break
            combined_rag += separator + chunk

        if len(combined_rag.strip()) >= MIN_RAG_TOTAL_CHARS:
            block += (
                "\n\n**===== CONTEXTO RECUPERADO DA BASE DE CONHECIMENTO DO TOPICO =====**\n"
                "O texto abaixo foi recuperado automaticamente da base de conhecimento deste topico "
                "e e um SUPLEMENTO da sua resposta: use-o para enriquecer conceitos, metodos e "
                "definicoes sempre que ele ajudar a responder a pergunta. Se ele for sobre outro "
                "assunto, indice, sumario ou material sem relacao com a pergunta, IGNORE-O em "
                "silencio e responda normalmente. EM NENHUM CASO mencione o contexto, a base de "
                "conhecimento ou o fato de o material ter (ou nao ter) coberto o topico: nao escreva "
                "avisos, justificativas ou disclaimers sobre o uso do contexto — a resposta deve "
                "comecar ja pela analise da questao. O contexto so pode acrescentar, nunca limitar: "
                "a resposta deve cobrir todos os pontos da questao com a mesma completude, clareza "
                "e estrutura que teria sem contexto. Ele NUNCA e motivo para encurtar: escreva "
                "todos os passos, subitens e exemplos que escreveria sem contexto e, antes de "
                "finalizar, confira se a resposta nao ficou mais curta ou menos detalhada — se "
                "ficou, acrescente o que faltou. Nao introduza duvidas, parenteses alternativos, "
                "leituras concorrentes ou 'auto-correcoes' desencadeadas pelo contexto: mantenha "
                "uma unica interpretacao e uma notacao consistentes do inicio ao fim. "
                "Se a pergunta trouxer dados especificos "
                "(numeros, matrizes, valores, figuras ou tabelas), resolva usando EXCLUSIVAMENTE "
                "esses dados: o contexto serve apenas para metodo, definicao ou conceito, e os "
                "exemplos numericos dele NUNCA devem substituir os dados da pergunta.\n\n"
                f"{combined_rag}\n"
                "**===== FIM DO CONTEXTO RECUPERADO =====**\n"
            )
        else:
            logger.info(
                f"[build_context_block] Conteudo RAG util insuficiente "
                f"({len(combined_rag.strip())} chars < {MIN_RAG_TOTAL_CHARS}). "
                f"Bloco de contexto NAO sera injetado."
            )

    if other_chunks:
        block += "\n\n**Exemplos de questoes ja resolvidas (apenas como referencia de estilo):**\n"
        for i, text in enumerate(other_chunks[:3], 1):
            block += f"\n--- Exemplo {i} ---\n{text[:800]}\n"

    return block, len(rag_chunks), sum(len(c) for c in rag_chunks)
