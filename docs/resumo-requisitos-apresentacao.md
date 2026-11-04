# ExercitaAI — Resumo de Requisitos e Decisões

**Versão:** 1.0 (outubro de 2026) · **Autor:** Yago Melo da Costa
**Finalidade:** visão de uma página do documento de requisitos (`docs/documento-de-requisitos.md`), para qualquer trabalho cujo objetivo seja analisar o projeto.

## Composição do documento

| Requisitos funcionais | Histórias de usuário | Regras de negócio | Requisitos não funcionais | Decisões de arquitetura | Referências novas na bibliografia |
|---|---|---|---|---|---|
| **20 RF** | **18 US** | **15 RN** | **12 RNF** | **13 AD** | **13** |

Cada item traz racional, referência (ou a marca explícita de *justificativa de engenharia*), garantia no código e validação. A Seção 11 é a matriz de rastreabilidade RF → US/RN → implementação → evidência → seção do TCC.

## Regras de negócio essenciais

| ID | Regra | Por quê |
|---|---|---|
| RN-01 | Dados e vetores isolados por usuário (`user_id` em toda rota; `questions` é corpus compartilhado) | Privacidade do material pessoal de estudo |
| RN-02 | Aviso obrigatório quando o contexto usado fica abaixo de 3000 caracteres | Evita resposta genérica que parece completa |
| RN-04 | Temperatura idêntica nos braços COM e SEM RAG (ambas 0,0) | Sem confundimento no experimento |
| RN-05 | Juiz: mediana de 3 execuções, *seeds* fixos, sem *nonces* no prompt | Juízes LLM são instáveis e enviesados |
| RN-06 | Recuperação com limiar de similaridade e filtro de auto-correspondência | Evita contexto irrelevante ou duplicado |
| RN-09 | Correção segue o formato do enunciado (letra do gabarito quando houver) | Rótulo declarado pelo LLM pode estar errado |
| RN-14 | Interface em pt-BR, sem emojis, tema claro/escuro | Identidade e legibilidade consistentes |

## Decisões de arquitetura essenciais

| ID | Decisão | Alternativa descartada |
|---|---|---|
| AD-01 | Três componentes independentes (frontend / backend / serviço de IA) por HTTP | Monolítico com LLM embutido |
| AD-05 | ChromaDB com metadados por coleção | FAISS/pgvector |
| AD-07 | Ollama + registro de 6 provedores externos (`provedor/modelo`) | API única fechada |
| AD-09 | SQLite (WAL) com chaves estrangeiras; JSON legado congelado | Manter JSON sem integridade |
| AD-12 | Avaliação por LLM-as-a-Judge com reserva e mediana | Avaliação humana em escala |
| AD-08 | Tarefas em *thread* com *polling* (sem fila externa) | Celery/RQ |

## Validação (evidências)

- **Suíte oficial** (`readme.py`, execução de 30/09/2026): 3 serviços online, **18 endpoints 100 % OK**, **9 páginas 100 % OK**, carga de 50 requisições com **100 % de sucesso, média 0,024 s, P95 0,036 s**.
- **Qualidade (LLM *judge*, com RAG):** flashcards 8,4 · estratégia 8,2 · artigos 7,6 · questões 7,0 · clareza global 6,91.
- **Impacto do RAG (50 casos COM vs SEM):** Δ precisão **+0,14** · Δ completude **+0,12** · Δ clareza **0,00** · Δ raciocínio **+0,12** — com 7 regressões registradas (hipótese: auto-correspondência), base da regra RN-06.
- **Interface:** 43/43 verificações (suíte auxiliar, não versionada — a oficial é o `readme.py`).

## Pendências honestas

- **Usabilidade (SUS/TAM):** instrumento pronto e fundamentado, **coleta não concluída** — nenhuma nota perceptiva é reportada.
- **Sem cobertura automatizada:** isolamento por usuário, limitação de taxa, anotações, downloads, configurações, reuso de *chunks* idênticos e a suíte de interface (todos com justificativa registrada).
- **`.env.example`** traz temperaturas desiguais (0,3/0,0) enquanto a regra e a produção usam 0,0/0,0 — alinhar o exemplo.

## Arquivos

| Conteúdo | Arquivo |
|---|---|
| Documento completo | `docs/documento-de-requisitos.md` |
| Apêndice em LaTeX | `docs/apendice-requisitos.tex` |
| Esta visão de uma página | `docs/resumo-requisitos-apresentacao.md` |
| Referências novas | `docs/referencias-adicionais.bib` |
