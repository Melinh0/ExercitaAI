# ExercitaAI — Documento de Requisitos, Regras de Negócio e Decisões de Projeto

**Versão:** 1.0 (outubro de 2026)
**Autor:** Yago Melo da Costa
**Finalidade:** formalizar requisitos, regras de negócio e decisões de projeto do ExercitaAI como base para qualquer trabalho que tenha por objetivo analisar o projeto.

---

## 1. Propósito, escopo e como citar

### 1.1 Propósito

Este documento formaliza os requisitos do ExercitaAI e, sobretudo, registra o **racional por trás de cada escolha**: por que cada funcionalidade funciona da forma como funciona, por que tais regras de negócio foram adotadas, por que tais decisões de arquitetura e tecnologia foram tomadas e como cada uma delas foi validada. Cada item traz uma referência bibliográfica quando o suporte é teórico e, quando não há, é assinalado honestamente como justificativa de engenharia.

O documento se destina a **qualquer trabalho que tenha por objetivo analisar o projeto** — acadêmico, técnico ou de manutenção —, fornecendo a base formal para entender, avaliar ou contestar as escolhas do sistema sem recorrer à leitura do código-fonte.

### 1.2 Escopo do documento

- Requisitos funcionais e não funcionais, histórias de usuário, regras de negócio, decisões de arquitetura/tecnologia, rastreabilidade e evidências de validação.
- O sistema ExercitaAI como um todo: frontend (SPA React), backend (Flask) e serviço de IA (FastAPI).

### 1.3 Fora do escopo deste documento

| Assunto | Onde está documentado |
|---|---|
| Instalação, variáveis de ambiente e execução | `README.md` (Guia de Execução) |
| Protocolo, benchmark e resultados dos experimentos | TCC — capítulos 4 a 6 (`sec:metodologia-avaliacao-llm`, `cap:resultados`) |
| Relatório de testes automatizados com gráficos | `README.md` (Relatório de Testes) |
| Conteúdo teórico das técnicas de estudo | TCC — Seção 5.3 (`subsec:fundamentacao_referencias`) |
| Imagens da interface em execução | TCC — Apêndice C (`ap:interface`) |

### 1.4 Convenções de identificação

| Prefixo | Significado | Formato do item |
|---|---|---|
| `RF-nn` | Requisito funcional | Finalidade, descrição, prioridade, histórico de origem, critérios de aceite, implementação, validação |
| `US-nn` | História de usuário | "Como…, quero…, para…" + critérios de aceite + prioridade |
| `RN-nn` | Regra de negócio | Enunciado, racional/motivação, referência, garantia no código, validação, consequência da violação |
| `RNF-nn` | Requisito não funcional | Categoria ISO/IEC 25010, meta mensurável, evidência, referência |
| `AD-nn` | Decisão de arquitetura/tecnologia | Contexto, decisão, alternativas, justificativa com referência, consequências |

Prioridades seguem o método MoSCoW: **E**ssencial, **D**esejável, **C**onforto, **N**ão exigido nesta versão (com referência a Wiegers e Beatty, 2013; Cohn, 2004 para o formato de histórias e INVEST). A taxonomia requisito funcional / requisito não funcional / regra de negócio segue a norma ISO/IEC/IEEE 29148:2018.

### 1.5 Como citar

No TCC, o documento é o **Apêndice D** (`\label{ap:requisitos}`), inserido no ambiente `apendicesenv` após o Apêndice C. Exemplos de referência interna:

- No texto: "…conforme formalizado no Apêndice D, Seção D.7 (RN-04)".
- Tabelas do apêndice podem ser citadas pelo identificador: "(RN-05)", "(RF-07)".

Referência ABNT (ajustar data e disponível em conforme a versão publicada):

> COSTA, Y. M. **Documento de requisitos, regras de negócio e decisões de projeto do ExercitaAI.** 2026. Material de apoio ao Trabalho de Conclusão de Curso em Ciência da Computação, Universidade Estadual do Ceará, Fortaleza, 2026.

Arquivos relacionados: `docs/apendice-requisitos.tex` (versão LaTeX do mesmo conteúdo) e `docs/resumo-requisitos-apresentacao.md` (resumo de uma página). Para citações em outros trabalhos, usar a referência ABNT acima (ex.: "a correção de respostas segue o formato de gabarito descrito em COSTA, 2026") e os identificadores RF/RN/RNF da Seção 5, Seção 7 e Seção 8.

---

## 2. Visão geral e atores

O ExercitaAI é uma plataforma de estudo que transforma material bruto (fotos, PDFs, textos) em resoluções, questões, flashcards e planos de estudo gerados por modelos de linguagem, com recuperação aumentada por geração (RAG) sobre o material do próprio usuário e busca integrada de literatura científica.

A arquitetura em três componentes (frontend, backend e serviço de IA) e suas integrações estão descritas na Seção 4.1 do TCC (`cap:metodologia`, Figura `fig:architecture`), que este documento referencia e não duplica.

**Atores do sistema:**

| Ator | Descrição | Autenticação |
|---|---|---|
| Visitante | Página pública de divulgação e formulário; não acessa conteúdo | Não |
| Estudante | Usuário autenticado; cria tópicos, envia material, gera conteúdo e estuda | Sim (sessão) |
| Sistema de IA (Ollama e provedores) | Executa geração, extração e avaliação; ator não humano | Chaves segregadas |
| Integrações acadêmicas | Crossref, arXiv, PubMed, Semantic Scholar (busca de artigos) | Não (APIs públicas) |
| Suíte de testes | Executa verificações de ponta a ponta na conta de teste | Sim (conta de teste) |

---

## 3. Partes interessadas e personas

| Persona | Perfil | Necessidade central | Requisitos atendidos |
|---|---|---|---|
| **Estudante autodirigido** | Acadêmico que estuda sozinho, com material disperso (fotos de apostilas, PDFs, artigos) | Transformar material em estudo acionável sem perder tempo organizando | RF-02 a RF-12, RF-17 |
| **Estudante com pouco material** | Estuda um tópico com poucos recursos disponíveis | Saber que o material é insuficiente e como enriquecê-lo, em vez de receber conteúdo genérico | RF-14, RF-20, RN-02, RN-03 |
| **Orientador/pesquisador** | Avalia a plataforma (avaliação por LLM Judge e questionário de usabilidade) | Evidências de qualidade e método verificável | RNF-08, Seção 12 |
| **Mantenedor do projeto** | Desenvolvedor que evolui o sistema | Decisões documentadas, código modular e testes reexecutáveis | AD-01 a AD-13, RNF-11 |

---

## 4. Glossário

| Termo | Definição |
|---|---|
| Tópico | Unidade organizadora do material de um usuário (imagens, questões, notas, sessões) |
| Questão | Registro com enunciado, resposta/gabarito e explicação; pode ser objetiva, verdadeiro/falso ou aberta |
| Flashcard | Cartão pergunta–resposta exibido com a resposta oculta até revelação deliberada |
| Quadro branco | Superfície de desenho e anotação com caixas de texto por questão, exportável como imagem |
| Sessão de estudo | Registro histórico de respostas do usuário em uma questão, com data e aproveitamento |
| Estratégia de estudo | Plano recomendado pela IA a partir do tempo de dedicação e do material do tópico |
| RAG | *Retrieval-Augmented Generation* — geração com contexto recuperado de base vetorial |
| Chunk | Fragmento de texto indexado para recuperação vetorial |
| Embedding | Representação vetorial de texto (aqui, `intfloat/multilingual-e5-base`) |
| Limiar de similaridade | Valor mínimo de similaridade coseno para um trecho ser admitido no contexto |
| Juiz (LLM-as-a-Judge) | Modelo que avalia respostas geradas em critérios objetivos (precisão, completude, clareza, raciocínio) |
| Braço COM/SEM RAG | Condições experimentais de geração com e sem contexto recuperado |
| Provedor | Fonte de modelos (Ollama, OpenAI, Groq, Google Gemini, OpenRouter, DeepSeek, Anthropic, NVIDIA) |
| Tarefa assíncrona | Processamento longo executado em segundo plano, acompanhado por *polling* |
| Instruções de personalização | Texto livre do usuário que direciona gerações e sugestões |

---

## 5. Requisitos funcionais

### RF-01 — Contas, sessão e segurança de acesso

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-01, US-02 |
| Finalidade | Permitir que o usuário tenha conta própria, com dados segregados e recuperação segura. |

**Descrição.** Cadastro, login e logout por sessão (*cookie* de Flask-Login), recuperação de senha por token de uso único e gestão de chaves de API por usuário.

**Critérios de aceite.**
- Senha armazenada exclusivamente como *hash* (Werkzeug); nunca em texto puro.
- Token de redefinição: SHA-256 armazenado, validade de 30 minutos, uso único.
- Limitação de taxa por IP: 5 tentativas de login em 15 minutos, 5 cadastros por hora, 5 redefinições por hora e *cooldown* de 60 segundos para o mesmo e-mail.
- Chaves de API segregadas por usuário e provedor; ocultáveis na interface.

**Implementação.** `backend/auth.py`; `backend/services/rate_limit.py`; `backend/models/user_model.py`; rotas `/register`, `/login`, `/logout`, `/current_user`, `/forgot_password`, `/reset_password`, `/update_keys`; páginas `frontend/src/pages/{Login,Register,ForgotPassword,ResetPassword}.js`.

**Validação.** Login da conta de teste exercitado pela suíte de integração (`README.md`, Seções 1–3); limitação de taxa sem cobertura automatizada (ver Seção 12.5).

**Referência.** OWASP ASVS (2021) para verificação de autenticação e controle de força bruta; ISO/IEC 25010:2011 (segurança).

---

### RF-02 — Gestão de tópicos

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-03 |

**Descrição.** O usuário cria, lista, abre, renomeia e exclui tópicos; a exclusão remove conteúdo e vetores associados.

**Critérios de aceite.**
- Criação com nome sanitizado (`[^\w\-_]` → `_`) apenas na criação/renomeação; rotas aceitam nomes crus na URL.
- Renomear atualiza URL, nome exibido e limpa/reescreve vetores do tópico (`rename_topic_vectors`).
- Excluir remove tópico, as pastas de imagens, quadros, questões e material de apoio, arquivos legados e vetores (`remove_topic_vectors`); tarefa em execução não recria o tópico excluído.
- Erros de renomeação (nome repetido, nome vazio) aparecem no próprio modal e somem ao reabrir.
- Tópico sem conteúdo apresenta, junto da orientação de material, as ferramentas de estudo (gerar questões, flashcards, estratégia de estudo e pesquisar artigos), cada uma com atalho direto.
- Nome genérico (ex.: "novo") avisa na criação e o aluno pode pedir uma sugestão de nome mais específica pela IA, a partir do nome digitado ou apenas de uma descrição opcional do foco; a sugestão preenche o campo de nome automaticamente (refazível alterando a descrição), a área abre e fecha por um único controle e tópicos com nomes simples abrem normalmente.

**Implementação.** `backend/controllers/topic_controller.py`; `backend/controllers/api_controller.py`; `backend/models/topic_model.py`; `llm_api/prompts/suggest_topic_name.md`; `frontend/src/pages/TopicView.js`, `frontend/src/pages/TopicsList.js`, `frontend/src/components/NewTopicModal.js`; rotas `/api/topics`, `/api/topics/suggest-name`, `/topic/<nome>`, `/topic/<antigo>/rename`, `/topic/<nome>/delete`.

**Validação.** Relatório de testes: `GET/POST /api/topics` e `GET /api/topics/TesteTemp` OK (≤ 0,010 s); suíte de interface: 10 verificações de renomeação (abrir popup, pré-preencher, renomear, erro de nome repetido, limpeza de erro).

---

### RF-03 — Ingestão de material do tópico

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-04, US-15 |

**Descrição.** Envio de imagens (PNG/JPG/JPEG) e PDFs por tópico, com processamento assíncrono, pré-visualização, colagem de área de transferência e exclusão por arquivo.

**Critérios de aceite.**
- Até 50 arquivos por envio; pré-visualização antes do envio; envio não bloqueante a interface.
- O envio cria a tarefa `upload_images`, visível no indicador de tarefas com rótulo próprio.
- Ao excluir arquivo, vetores e imagens derivadas são removidos.
- Textos de apoio (`upload_rag`) seguem o mesmo fluxo e alimentam a indexação vetorial.
- As duas funcionalidades têm listas separadas: "Adicionar arquivos" lista apenas as imagens e PDFs enviados por ela; "Adicionar material de apoio" lista apenas o material indexado, com opção de excluí-lo.
- Um botão de interrogação ao lado do bloco "Material" explica, em um modal curto, a diferença entre as duas funcionalidades.
- O visualizador do tópico filtra a navegação por arquivo de origem (cada PDF vira um grupo com suas páginas) e por questões geradas; com filtro ativo, contador e setas percorrem só o grupo escolhido, e o filtro não aparece quando não há o que separar.

**Implementação.** `backend/controllers/upload_controller.py`; `frontend/src/components/UploadFilesModal.js`, `UploadRAGModal.js`, `Sidebar.js`, `ImageViewer.js`, `frontend/src/pages/TopicView.js`; rotas `/topic/<nome>/upload`, `/upload_rag`, `/topic/<nome>/files`, `/topic/<nome>/material_files`, `/topic/<nome>/delete_image/<arquivo>`.

**Validação.** Suíte de interface: modal abre com texto esperado, 2 imagens no pré-visualização, modal fecha após envio, indicador de tarefas aparece, tarefa concluída, tópico atualizado com as imagens; suíte de material: listas separadas por funcionalidade e modal de ajuda; relatório de testes: rotas de upload de imagem, PDF e RAG OK.

---

### RF-04 — Extração de conteúdo (OCR e transcrição)

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-05 |

**Descrição.** Extração do texto das imagens e PDFs enviados, por OCR local (Tesseract, línguas `por` e `eng`) com reserva para serviço externo, e transcrição por modelo de visão.

**Critérios de aceite.**
- PDFs extraídos com correção de ordem de colunas e descarte de capas/índices.
- Análise de página única e de documento completo funcionam como tarefas assíncronas.
- Texto extraído é normalizado (remoção de controles e *backslashes* de LaTeX) antes de persistir.

**Implementação.** `backend/services/{ocr_service,image_service,analise_utils,json_modelo}.py`; rotas `/analyze_with_image`, `/analyze_full_document`; componentes `OCRInfoModal.js`, `VisionInfoModal.js`.

**Validação.** Relatório de testes: `POST /analyze_with_image` OK (24,684 s com geração); qualidade da resolução extraída avaliada pelo LLM Judge (ver Seção 12.2).

---

### RF-05 — Resolução e registro de questões

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-05, US-06 |

**Descrição.** Para cada questão extraída, a IA gera resolução completa (passo a passo e explicação), que o usuário confere, edita e salva; respostas dadas em sessão também são persistidas.

**Critérios de aceite.**
- Resolução gerada com ou sem contexto RAG, conforme disponibilidade do material.
- Respostas de sessão são salvas por questão e consultáveis no histórico.
- Conteúdo gerado passa por camadas de reparo de LaTeX antes de persistir e renderizar.

**Implementação.** `backend/controllers/question_controller.py` (`/save`, `/save_answers`); `backend/services/resposta_utils.py`; `llm_api/main.py` (`/generate`, `/verify_response`).

**Validação.** Relatório de testes: `POST /save_answers` OK (0,037 s); notas do LLM Judge para clareza das resoluções (Seção 12.2).

---

### RF-06 — Edição e complementação manual de questões

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-06 |

**Descrição.** Editor completo de questões (enunciado, resposta, explicação) em Markdown, criação manual de questões (inclusive a partir de texto colado) e exclusão.

**Critérios de aceite.**
- Edição pré-visualiza Markdown; salvar regrava somente os campos alterados.
- "Enriquecer questão" gera melhoria via tarefa `enhance_question`, sem alterar sem confirmação.
- Adição de questões de texto cria um registro por questão (navegação por índice), com marcador de origem para as que vêm do gerador — é ele que alimenta o filtro do visualizador.
- Texto de questão pode ser baixado individualmente.

**Implementação.** `backend/controllers/question_controller.py` (`/add_question`, `/add_text_question(s)`, `/delete_question`, tarefa `enhance_question`); `frontend/src/components/QuestionEditor.js`, `EditableMarkdown.js`.

**Validação.** Suíte de interface utiliza a injeção de questões de texto como cenário das verificações da aba Responder (RF-07).

---

### RF-07 — Aba Responder e correção automática

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-07, US-08 |

**Descrição.** Aba de prática com seleção da questão, exibição do enunciado, resposta pelo formato adequado ao tipo e conferência imediata com veredito, gabarito e explicação.

**Critérios de aceite.**
- **Objetiva** (≥ 2 alternativas `A)`–`F)` no enunciado): alternativas saem do enunciado e viram rádios; enunciado não as repete.
- **Verdadeiro/Falso sem alternativas no enunciado**: rádios `A) Verdadeiro` / `B) Falso` (independentemente do campo `tipo` declarado conter `vf`).
- **Aberta**: campo de texto livre.
- Gabarito oculto antes de conferir; "Conferir" desabilitado sem resposta; conferência compara por letra (`B)`, `B`, `b`, `B.`) e, na ausência de letra, textualmente normalizada (remove prefixo `X) `); gabarito vazio → sem veredito.
- Após conferir: "Você acertou!" ou aviso de não confere + gabarito + explicação; "Tentar de novo" reoculta o gabarito.
- Questão aberta: a resposta escrita é avaliada pela IA contra o gabarito, com julgamento por sentido (outra redação, resumo ou exemplos a mais não invalidam a resposta) e apresentação de um parecer; texto sem sentido ou resposta em branco é dado como incorreto.
- Gabarito de "Verdadeiro" ou "Falso" é tratado como questão de duas alternativas mesmo quando o tipo gravado é "aberta"; gabarito prefixado por "Resposta final:" é lido pelo valor da resposta, e não pelo prefixo.
- Área de rolagem própria; quebras de linha do enunciado preservadas.
- A aba "Responder" é a aba padrão do Conteúdo da resolução: ao abrir o tópico ou trocar de imagem, o usuário já cai nela.

**Implementação.** `frontend/src/components/ResponderQuestao.js`, `frontend/src/utils/questoes.js`; `backend/controllers/question_controller.py` (rota `/evaluate_answer`), `backend/services/resposta_utils.py`; `llm_api/main.py` (rota `/evaluate_answer`); estilos `.responder-*` em `frontend/src/App.css`.

**Validação.** Suíte de interface: 13 verificações (radios objetivos, enunciado sem duplicidade, rolagem, gabarito oculto, conferir desabilitado, erro/acierto, gabarito letra simples, vf com alternativas, vf sem alternativas, botão desabilitado, gabarito textual `Falso`, aberta em textarea) e suíte de avaliação: 6 verificações (aba RespondER ativa, gabarito verdadeiro/falso vira alternativa, questão aberta mantém campo de texto, resposta avaliada pela IA como correta e parecer exibido).

---

### RF-08 — Anotações por questão e insight

| Campo | Conteúdo |
|---|---|
| Prioridade | Desejável |
| Histórias | US-09 |

**Descrição.** O usuário escreve anotações por questão (persistidas por questão), e pode pedir um *insight* gerado pela IA sobre o conteúdo da anotação/resolução.

**Critérios de aceite.**
- Anotações listadas, criadas, atualizadas e excluídas por questão.
- Insight gerado por tarefa `analyze_image_insight` e exibido sem sobrescrever a nota.

**Implementação.** `backend/controllers/note_controller.py` (`list_notes`, `add_note`, `update_note`, `delete_note`); `frontend/src/components/AnnotationEditor.js`; rota `/save_example`; tarefa `analyze_image_insight`.

**Validação.** Sem cobertura automatizada específica (Seção 12.5); fluxo exercitado manualmente.

---

### RF-09 — Quadro branco por questão

| Campo | Conteúdo |
|---|---|
| Prioridade | Desejável |
| Histórias | US-10 |

**Descrição.** Área de desenho livre com seletor de ferramentas (Selecionar, Pincel e Borracha), caixas de texto, formas geométricas e setas livres, acoplada a cada questão, com persistência e exportação como imagem.

**Critérios de aceite.**
- Seletor de ferramentas explícito: Selecionar (padrão) move e seleciona itens, Pincel desenha traços e Borracha apaga; as cores escolhidas valem para traços, textos, formas e setas.
- Elementos do quadro (traços, caixas, formas, setas e imagens coladas) persistidos localmente por questão: reabertos editáveis e re-renderizados no tema claro/escuro vigente, sem reassentar a aparência antiga.
- Caixas de texto digitáveis, arrastáveis e redimensionáveis em largura e altura; o texto digitado parte do tamanho indicado pelo controle "Texto", o redimensionamento ajusta a fonte proporcionalmente (para mais e para menos) e a altura nunca fica menor que o conteúdo; o duplo clique reabre a edição.
- O que foi desenhado no quadro não muda ao entrar ou sair da tela cheia: caixas, formas, setas e tamanho da letra permanecem exatamente iguais, e o canvas apenas passa a mostrar mais área.
- Formas geométricas planas básicas (círculo, quadrado, retângulo e triângulo) criadas por clique, arrastáveis e redimensionáveis; nas formas com texto, o texto permanece centralizado e contido dentro da forma mesmo após ampliá-la.
- O corpo do texto independe do modo de exibição: entrar ou sair da tela cheia não altera o tamanho da letra.
- Setas como figuras livres: escolhidas em "Formas", traçadas com o mouse no sentido e ângulo desejados, selecionadas, movidas e com as pontas ajustadas; Delete remove o item selecionado.
- Download de um quadro ou de todos os quadros do tópico pelo modal dedicado.

**Implementação.** `frontend/src/components/Whiteboard.js`, `EmptyDownloadModal.js`; `backend/controllers/download_controller.py`; rotas `/save_whiteboard`, `/whiteboard_image/<tópico>/<arquivo>`, `/topic/<nome>/download_question_whiteboard/...`, `/download_whiteboards`.

**Validação.** Relatório de testes: `POST /save_whiteboard` OK (0,013 s); exportação sem teste automatizado dedicado.

---

### RF-10 — Geração de questões com IA

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-11, US-18 |
| Relacionados | RN-02, RN-03, RN-15 |

**Descrição.** Modal de geração com tipos (objetiva, aberta, verdadeiro/falso), quantidade, instruções personalizadas e sugestões de *prompt*; resultados exibidos em lista editável antes de inserir no tópico.

**Critérios de aceite.**
- Dica estática antes do envio orienta sobre material de apoio.
- Sugestões de *prompt* aparecem apenas no campo acionado (RN-13).
- Resultado carrega o metadado `contexto` (`chars`, `com_rag`, `insuficiente`, `instrucoes`) para orientar o usuário.
- Com material insuficiente, exibe aviso e sugestões de busca personalizadas (RF-20).
- Com chave de provedor, o enunciado é gerado no contexto do usuário dono da chave (propagação via `contextvars` nos workers paralelos).

**Implementação.** `frontend/src/components/QuestionGeneratorModal.js`, `GeneratedQuestionsView.js`; `backend/controllers/task_controller.py` (`_worker_generate_questions`); rota `/generate_questions`; prompt `llm_api/prompts/generate_questions.md`; correção de contexto nos workers (`llm_api/core/contexto.py`).

**Validação.** Relatório: `POST /generate_questions` OK (4,904 s); juiz: 7,0 (com RAG); suíte de interface: dica de material no gerador; correção de geração com chave de provedor validada com chave ativa (enunciado real retornado).

---

### RF-11 — Flashcards

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-12 |
| Relacionados | RN-02, RN-10 |

**Descrição.** Geração de cartões a partir de assunto/instruções, exibição com resposta oculta até revelação deliberada e persistência das sessões para revisitação.

**Critérios de aceite.**
- Resposta só é exibida após ação explícita do usuário (recuperação ativa).
- Sessão salva com carimbo de tempo, instruções e metadado de contexto.
- Aviso de pouco material com sugestões de busca personalizadas (RF-20).

**Implementação.** `frontend/src/components/FlashcardGeneratorModal.js`, `FlashcardsViewer.js`; `_worker_generate_flashcards`; rota `/generate_flashcards`.

**Validação.** Relatório: `POST /generate_flashcards` OK (36,109 s); juiz: 8,4 (com RAG) — maior nota entre as funcionalidades de geração.

---

### RF-12 — Estratégia de estudo

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-13 |
| Relacionados | RN-10, RN-02 |

**Descrição.** Recomendação de plano de estudo a partir do tempo de dedicação, instruções personalizadas e conteúdo do tópico, com técnicas devidamente referenciadas e histórico de recomendações.

**Critérios de aceite.**
- Plano fundamentado no compêndio de técnicas com referência científica (Seção 10).
- Termos sugeridos para busca já vêm como consultas prontas para o navegador.
- Histórico de estratégias revisitável sem nova geração.
- Aviso de pouco material com sugestões personalizadas (RF-20).

**Implementação.** `frontend/src/components/StudyStrategyModal.js`; `_worker_study_strategy`; rotas `POST/GET /topic/<nome>/study_strategy`; prompt `recommend_study_strategy`.

**Validação.** Relatório: `POST /topic/.../study_strategy` OK (10,682 s) e `GET` (0,005 s); juiz: 8,2 (com RAG).

---

### RF-13 — Busca de artigos científicos

| Campo | Conteúdo |
|---|---|
| Prioridade | Desejável |
| Histórias | US-14 |
| Relacionados | RN-03, RN-13 |

**Descrição.** Busca em quatro bases acadêmicas (Crossref, arXiv, PubMed, Semantic Scholar) com refino, sugestões automáticas do que pesquisar e leitura do resultado.

**Critérios de aceite.**
- Sugestões de busca aparecem automaticamente em toda abertura do modal, rotuladas "Sugestões do que pesquisar", considerando o foco do usuário quando houver (RN-03).
- Estado inicial orienta o que digitar; estado vazio explica como refinar.
- Clique em sugestão de outras telas abre a consulta no navegador do usuário (nova aba).

**Implementação.** `backend/controllers/article_controller.py` (Crossref/arXiv/PubMed/Semantic Scholar); `frontend/src/components/ArticleSearchModal.js`; tarefa `search_articles`; prompt `suggest_search_articles`.

**Validação.** Relatório: `POST /search_articles` OK (3,919 s); juiz: 7,6 (condição única); suíte de interface: estado inicial e sugestões automáticas.

---

### RF-14 — Recuperação e enriquecimento de contexto (RAG)

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-15 |
| Relacionados | RN-06, RN-07, RN-08 |

**Descrição.** Indexação do material em base vetorial (`documents`, `examples`, `corrections`) com recuperação filtrada por tópico e usuário, uso nas gerações e limpeza quando o conteúdo sai do sistema.

**Critérios de aceite.**
- Embeddings com prefixos obrigatórios `query:`/`passage:` (RN-07).
- Recuperação com limiar de similaridade e filtro de auto-correspondência (RN-06).
- Indexação pula *chunks* idênticos já existentes (reuso); exclusão/renomeação de tópico sincroniza os vetores (RN-08).
- Isolamento por `user_id` em `documents` e `examples`; coleção `questions` é compartilhada por desenho (RN-01).
- Índice de remoção por tópico/arquivo disponível para a suíte de testes.

**Implementação.** `llm_api/rag.py`, `embeddings.py`, `data_loader.py`; `llm_api/main.py` (`/retrieve_context`, `/retrieve_examples`, `/index_documents`, `/remove_topic_vectors`, `/rename_topic_vectors`); `backend/services/rag_client.py`.

**Validação.** Experimento controlado COM vs SEM RAG (Seção 12.3); relatório: `POST llm_api/index` OK.

---

### RF-15 — Catálogo de modelos e provedores

| Campo | Conteúdo |
|---|---|
| Prioridade | Desejável |
| Histórias | US-02, US-16 |
| Relacionados | RN-11 |

**Descrição.** Catálogo dinâmico de modelos (Ollama + seis provedores externos), com listas obtidas das próprias APIs, filtros de modelo livre e seleção por usuário.

**Critérios de aceite.**
- `/models` só oferece provedor com chave disponível (usuário ou ambiente).
- Nomes Ollama ocultos para usuário sem chave Ollama; `provedor/id` no seletor.
- *Allowlists* por provedor (`<PROV>_MODELS`): vazio → padrão do registro; `*` → tudo.
- Padrões de geração sensíveis ao usuário (usuário só de provedor não recebe modelo Ollama padrão).

**Implementação.** `llm_api/provedores.py`, `model_info.py`; `backend/controllers/api_controller.py` (`/api/models`, `/provedores`), `auth.py` (`/update_keys`); `frontend/src/components/ConfigModal.js`.

**Validação.** Relatório: `GET /api/models` e `GET llm_api/models` OK (0,003 s / 0,002 s).

---

### RF-16 — Tarefas assíncronas e acompanhamento

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-16 |

**Descrição.** Trabalhos longos rodam como tarefas com progresso, mensagem e resultado; a interface acompanha por *polling* e permite reabrir resultados concluídos.

**Critérios de aceite.**
- Início, progresso, conclusão e erro visíveis no indicador de tarefas (rótulo por tipo).
- Cliques repetidos na mesma funcionalidade não duplicam a execução: a tarefa em andamento é reaproveitada (mesmo identificador) e o indicador mostra uma única entrada; a proteção vale no servidor, por chave de negócio da tarefa, e no botão, que fica bloqueado enquanto houver execução do mesmo tipo.
- Trabalho genuinamente diferente (outro documento, outra página, outra consulta) segue em paralelo.
- A seta de progresso gira centrada no indicador, tanto na bola quanto ao lado do rótulo de processamento.
- A lista de execução fica aberta por padrão enquanto houver tarefa em andamento, e o usuário pode ocultá-la quando quiser.
- Resultado concluído pode ser reaberto ("Ver resultado") **apenas** quando pertence ao tópico aberto (filtro por `params.topic`/`topic_name`).
- Falha de tarefa não derruba a interface.

**Implementação.** `backend/services/task_manager.py` (`create_task` com `dedup_key`); `backend/controllers/task_controller.py` (`_chave_dedup`, `/tasks`, `/tasks/start`, `/tasks/<id>`), `controllers/upload_controller.py`; `frontend/src/contexts/TaskContext.js` (`isRunning`), `components/TaskIndicator.js`, `ImageViewer.js`, `QuestionGeneratorModal.js`, `FlashcardGeneratorModal.js`, `StudyStrategyModal.js`, `AnnotationEditor.js`, `QuestionEditor.js`; `App.css` (`.task-fab-spinner`, `.girando-processando`).

**Validação.** Suíte de interface: indicador aparece, tarefa concluída, rótulo correto; filtro de tópico verificado por sonda (tela nova abre sem modal de geração antiga sobreposta); suíte de tarefas: cliques repetidos reaproveitam a mesma execução, o painel lista uma única entrada, o botão fica bloqueado e a seta gira centrada.

---

### RF-17 — Sessões de estudo e histórico

| Campo | Conteúdo |
|---|---|
| Prioridade | Desejável |
| Histórias | US-17 |

**Descrição.** Registro histórico de respostas por questão, listagem e exclusão de sessões e reabertura de estratégias anteriores.

**Critérios de aceite.**
- Sessão salva com data, questão, respostas e resultado.
- Histórico navegável por tópico; sessões antigas podem ser removidas.
- Anotações ficam salvas por questão entre sessões.
- Em "Editar respostas", além da resposta do usuário, é possível editar a resposta (gabarito) e a resolução (explicação) depois de abrir "Ver explicação".
- Quando a questão já está no tópico, um aviso informa isso e, ao salvar, a resposta e a resolução editadas são aplicadas também na questão do tópico, mantendo histórico e tópico iguais.

**Implementação.** `backend/controllers/topic_controller.py` (rotas `/topic/<nome>/sessions`); tabela `study_session` (`backend/models/topic_tables.py`); `frontend/src/components/SessionsViewer.js`.

**Validação.** Relatório: `GET /topic/.../sessions` OK (0,005 s).

---

### RF-18 — Exportação e downloads

| Campo | Conteúdo |
|---|---|
| Prioridade | Conforto |
| Histórias | US-17 |

**Descrição.** Exportação de imagens, quadros brancos, resoluções em texto e status de processamento, sempre por modal dedicado (RN-13).

**Critérios de aceite.**
- Download individual ou em lote por tópico.
- Downloads de imagens e quadros **somente** via `EmptyDownloadModal`.
- Baixar resoluções em texto para uso externo.

**Implementação.** `backend/controllers/download_controller.py`; rotas `/download_all_images`, `/download_image/<a>`, `/download_whiteboards`, `/download_text_resolutions`, `/download_status`; `frontend/src/components/EmptyDownloadModal.js`.

**Validação.** Sem teste automatizado dedicado (Seção 12.5); fluxo exercitado manualmente.

---

### RF-19 — Configurações e tema

| Campo | Conteúdo |
|---|---|
| Prioridade | Conforto |
| Histórias | US-18 |

**Descrição.** Modal de configurações com chaves por provedor, modelo padrão, seção de provedores e informações auxiliares; tema claro/escuro persistido localmente.

**Critérios de aceite.**
- Chaves cadastradas/ocultáveis; listagem de provedores sem expor segredos.
- Tema alternável e persistido; sem dependência de servidor para o tema.

**Implementação.** `frontend/src/components/ConfigModal.js`; estilos `body.dark-mode` em `frontend/src/App.css`; rotas `/update_keys`, `/provedores`.

**Validação.** Sem teste automatizado dedicado (Seção 12.5).

---

### RF-20 — Transparência de contexto e orientação com pouco material

| Campo | Conteúdo |
|---|---|
| Prioridade | Essencial |
| Histórias | US-11, US-12, US-13 |
| Relacionados | RN-02, RN-03 |

**Descrição.** Quando o material recuperado é insuficiente, o sistema informa isso de forma explícita e orienta o próximo passo, em vez de entregar conteúdo genérico sem aviso.

**Critérios de aceite.**
- Metadado `contexto` (`chars`, `com_rag`, `insuficiente` < 3000 caracteres, `instrucoes`) presente nas tarefas de questões, flashcards e estratégia.
- Aviso em caixa destacada nos três resultados, com ações "Adicionar material de apoio" e "Pesquisar artigos".
- Chips "Sugestões do que pesquisar" exibidas dentro do próprio aviso, buscadas automaticamente.
- Clicar numa sugestão abre a busca no navegador padrão (nova aba), não outro modal.
- As sugestões consideram o foco do usuário (instruções de personalização) além do tópico e do RAG.
- Sessões antigas sem metadado não exibem o aviso (sem falsos positivos).

**Implementação.** `backend/controllers/task_controller.py` (metadado nas três tarefas); `backend/controllers/question_controller.py` (`_contexto_sugestoes` com foco rotulado); `llm_api/prompts/suggest_search_articles.md`; `frontend/src/components/{SugestoesContexto,GeneratedQuestionsView,FlashcardsViewer,StudyStrategyModal,ArticleSearchModal}.js`.

**Validação.** Suíte de interface: dica de material, sugestões automáticas na busca; teste de API: `/suggest_prompts` com `instrucoes` de foco em correlação retornou sugestões específicas (`"Pearson correlation" AND "Spearman correlation"…`) em vez de termos genéricos.

---

### RF-21 — Ajuda embutida de uso

| Campo | Conteúdo |
|---|---|
| Prioridade | Conforto |
| Histórias | US-03 |

**Descrição.** A marca "Exercita AI" na barra superior da lista de tópicos abre um modal de documentação breve, organizado por funcionalidade, para o usuário entender o app sem sair dele.

**Critérios de aceite.**
- Clicar na marca (ou teclar Enter/Espaço com ela focada) abre o modal "Como usar o Exercita AI".
- O conteúdo cobre material do tópico, ferramentas de estudo, verificação de resposta, quadro branco, sessões, tarefas e histórico, em linguagem direta e sem jargão.
- O modal fecha pelo botão de fechar, pelo fundo e pela tecla Escape, como os demais modais.

**Implementação.** `frontend/src/components/HelpModal.js`; `frontend/src/pages/TopicsList.js` (marca clicável).

**Validação.** Suíte de interface: marca abre a ajuda com as seções principais e a tecla Escape fecha.

---

## 6. Histórias de usuário

Formato conforme Cohn (2004); prioridades conforme MoSCoW (Wiegers e Beatty, 2013). Histórias seguem o acrônimo INVEST (independente, negociável, valiosa, estimável, pequena, testável).

| ID | História | RF | Prioridade | Critérios de aceite (resumo) |
|---|---|---|---|---|
| US-01 | Como estudante, quero criar conta e entrar, para ter meu material separado dos outros | RF-01 | Essencial | Cadastro valida e-mail/senha; login estabelece sessão; senha nunca armazenada em claro; logout encerra a sessão |
| US-02 | Como usuário, quero recuperar minha senha e cadastrar chaves de API, para retomar o acesso sem depidar de suporte | RF-01, RF-15 | Essencial | Token de redefinição válido por 30 min e uso único; chaves segregadas e ocultáveis; limite de tentativas respeitado |
| US-03 | Como estudante, quero organizar meus tópicos (criar, renomear, excluir), para agrupar o material por assunto | RF-02 | Essencial | Renomear muda URL e limpa vetores; excluir remove conteúdo e vetores; erro de nome repetido aparece no modal e some ao reabrir |
| US-04 | Como estudante, quero enviar fotos e PDFs de uma vez, para ter meu material digitalizado e indexado | RF-03 | Essencial | Pré-visualização antes do envio; envio assíncrono com indicador; tópico atualizado ao concluir; exclusão remove vetores do arquivo |
| US-05 | Como estudante, quero que a plataforma leia e resolva as questões das minhas imagens, para não transcrever à mão | RF-04, RF-05 | Essencial | Texto extraído com OCR/transcrição; resolução com passo a passo e explicação; resultado editável antes de salvar |
| US-06 | Como estudante, quero corrigir e acrescentar questões manualmente, para o material refletir o que sei que importa | RF-05, RF-06 | Essencial | Edição em Markdown com pré-visualização; criação manual/texto; enriquecimento opcional por IA; exclusão com confirmação |
| US-07 | Como estudante, quero responder questões objetivas com uma bolinha e conferir na hora, para praticar com correção imediata | RF-07 | Essencial | Rádios para objetivas; gabarito oculto; veredito e explicação após conferir; tentar de novo reoculta |
| US-08 | Como estudante, quero questões de verdadeiro/falso e discursivas na mesma aba, para praticar em diferentes formatos | RF-07 | Essencial | V/F com rádios Verdadeiro/Falso (mesmo sem alternativas no enunciado); aberta em texto livre; mesmo fluxo de conferência |
| US-09 | Como estudante, quero anotar por questão e pedir um insight, para fixar observações no contexto certo | RF-08 | Desejável | Notas persistem por questão; insight gerado sem sobrescrever a nota |
| US-10 | Como estudante, quero desenhar e anotar num quadro branco por questão, para representar visualmente a solução | RF-09 | Desejável | Desenho e caixas de texto salvos e recarregados; exportação individual e em lote pelo modal dedicado |
| US-11 | Como estudante, quero gerar um conjunto de questões sob medida (tipo, quantidade, instruções), para treinar exatamente o que preciso | RF-10, RF-20 | Essencial | Sugestões só no campo acionado; dica antes do envio; aviso + sugestões personalizadas quando o material é curto |
| US-12 | Como estudante, quero criar flashcards e revisar com a resposta oculta, para ativar a recuperação ativa | RF-11, RF-20 | Essencial | Resposta só revela por ação explícita; sessão salva; aviso de pouco material com sugestões |
| US-13 | Como estudante, quero receber um plano de estudo com base no meu tempo, para organizar a rotina | RF-12, RF-20 | Essencial | Plano fundamentado em técnicas referenciadas; histórico revisitável; termos de busca prontos |
| US-14 | Como estudante, quero pesquisar artigos em quatro bases dentro da plataforma, para não abrir várias abas | RF-13 | Desejável | Sugestões automáticas a cada abertura; estado inicial/vazio orienta; resultados navegáveis |
| US-15 | Como estudante, quero adicionar textos de apoio para melhorar o que a IA gera para mim | RF-14 | Essencial | Indexação com prefixos corretos; recuperação com limiar; limpeza ao excluir; isolamento por usuário |
| US-16 | Como usuário, quero escolher modelo/provedor e ver o progresso das tarefas, para controlar custo e espera | RF-15, RF-16 | Essencial | Catálogo só com provedores com chave; progresso visível; resultado reaberto só do tópico atual |
| US-17 | Como estudante, quero revisitar sessões e exportar meu conteúdo, para revisar e arquivar meu progresso | RF-17, RF-18 | Desejável | Histórico navegável; downloads pelo modal dedicado; resoluções em texto |
| US-18 | Como usuário, quero alternar tema e ver informações do modelo, para usar com conforto e transparência | RF-19 | Conforto | Tema persistido localmente; modelo e provedores visíveis nas configurações |

---

## 7. Regras de negócio

Cada regra traz enunciado, racional (motivação), referência, como o sistema a garante e como é validada. Regras sem suporte bibliográfico direto são assinaladas como **justificativa de engenharia**.

### RN-01 — Isolamento de dados por usuário

- **Enunciado.** Conteúdo (tópicos, questões, anotações, sessões) e vetores pertencem exclusivamente ao usuário dono; a coleção `questions` é um corpus compartilhado deliberadamente.
- **Racional.** A plataforma manipula material de estudo pessoal e credenciais; a segregação é pré-requisito de privacidade. O compartilhamento da coleção `questions` existe porque perguntas/padrões de correção não expõem conteúdo pessoal e seu reuso melhora a consistência do módulo de questões — decisão consciente, limitada a metadados anônimos.
- **Referência.** ISO/IEC 25010:2011 (fator segurança: confidencialidade); OWASP ASVS 4.0.3 (controle de acesso).
- **Garantia no código.** Chaves estrangeiras `user.id` com `ON DELETE CASCADE` em `backend/models/topic_tables.py`; filtro opcional `user_id` em toda rota de recuperação (`/retrieve_context`, `/retrieve_examples`, `/generate`) e em `documents`/`examples`; `questions` sem filtro de usuário.
- **Validação.** Verificação estática (código) — sem teste automatizado dedicado (Seção 12.5).
- **Consequência da violação.** Exposição de material entre usuários.

### RN-02 — Aviso obrigatório quando o material é insuficiente

- **Enunciado.** Se o contexto usado numa geração ficar abaixo de 3000 caracteres, o resultado deve informar o usuário e orientar como enriquecer o material.
- **Racional.** Gerar sem avisar entrega conteúdo genérico que parece completo; o aviso transforma uma limitação em orientação acionável e evita que o usuário confie em saída montada sem base.
- **Referência.** Zhou et al. (2024) (mitigação de alucinações em LLMs); Kluibenschadl, Roiter e Oppl (2024) (RAG educacional); Kirschner, Sweller e Clark (2006) (carga cognitiva extrínseca — evitar sobrecarregar a decisão com conteúdo sem direção).
- **Garantia no código.** Metadado `contexto.insuficiente` nos workers de questões, flashcards e estratégia (`backend/controllers/task_controller.py`); banners `.contexto-aviso` em `GeneratedQuestionsView`, `FlashcardsViewer` e `StudyStrategyModal`.
- **Validação.** Suíte de interface: "dica de material no gerador de questões"; ausência de falso positivo em sessões antigas (sem metadado).
- **Consequência da violação.** Usuário recebe conteúdo repetitivo sem entender por quê.

### RN-03 — Foco do usuário propagado às sugestões de busca

- **Enunciado.** As instruções de personalização dadas na geração devem influenciar as sugestões do que pesquisar (no aviso e na busca de artigos), junto do tópico e do RAG.
- **Racional.** Sem o foco, sugestões genéricas ("Data Science AND Machine Learning") conflitam com o que o usuário pediu (ex.: correlação) e desperdiçam a atenção.
- **Referência.** Kirschner, Sweller e Clark (2006) (reduzir carga extrínseca); Lewis et al. (2020) (RAG — o contexto deve ser o mais aderente possível à intenção).
- **Garantia no código.** `instrucoes` incluído no metadado `contexto` das três tarefas; `SugestoesContexto` e `ArticleSearchModal` enviam `instrucoes` no payload; `_contexto_sugestoes` insere a linha rotulada "Foco pedido pelo usuario…" **antes** do trecho de RAG (que é truncado); regra explícita em `suggest_search_articles.md`.
- **Validação.** Teste de API: `/suggest_prompts` com foco em correlação gerou sugestões específicas de correlação.
- **Consequência da violação.** Sugestões irrelevantes e redundantes com as sugestões próprias da busca.

### RN-04 — Temperatura simétrica entre os braços COM e SEM RAG

- **Enunciado.** `ANALYZE_TEMPERATURE_WITH_RAG` e `ANALYZE_TEMPERATURE_WITHOUT_RAG` devem ser iguais (ambas 0,0 em produção).
- **Racional.** Diferença de temperatura entre condições introduz confundimento: a diferença de qualidade passaria a ser atribuída ao RAG quando poderia vir da amostragem.
- **Referência.** Shadish, Cook e Campbell (2002) (controle de variáveis confundidoras em desenhos experimentais).
- **Garantia no código.** Duas variáveis lidas em `llm_api/main.py` (76–77); valor de produção em `.env` (ambas 0,0); documentado em `AGENTS.md`.
- **Validação.** Verificação estática do `.env` e da suíte; atenção registrada: o `.env.example` traz valores desiguais (0,3/0,0) e deve ser alinhado (ver Seção 13).
- **Consequência da violação.** Resultados do experimento COM vs SEM RAG invalidados.

### RN-05 — Juiz com mediana de três execuções, seeds fixos e sem nonces

- **Enunciado.** A avaliação do LLM Judge usa mediana de `TEST_JUDGE_MEDIANA_EXECUCOES` (3) chamadas, temperatura 0, *seeds* determinísticos distintos e **sem** nonces no prompt.
- **Racional.** Avaliadores LLM são instáveis e enviesados; a mediana reduz variância e os nonces fabricariam "instabilidade" que na verdade é ruído de prompt.
- **Referência.** Zheng et al. (2023) (LLM-as-a-Judge); Wang et al. (2023) ("Not Fair" — viéses de juízes LLM).
- **Garantia no código.** `readme.py` (mediana, *seeds* distintos); mesmo tratamento dos braços COM e SEM (sem viés direcional).
- **Validação.** Seção "Consistência do Avaliador" do TCC (`sec:resultados-consistencia`, `tab:consistencia`).
- **Consequência da violação.** Notas infladas ou instáveis, comparabilidade perdida.

### RN-06 — Recuperação vetorial com limiar e filtro de auto-correspondência

- **Enunciado.** Só trechos com similaridade ≥ ao limiar entram no contexto; trechos que são o próprio OCR da imagem analisada (auto-correspondência) são filtrados.
- **Racional.** Sem limiar, trechos fracos entram e degradam a resposta; sem o filtro de auto-*match*, o próprio conteúdo da imagem duplica no prompt e piora completude (fenômeno documentado nas regressões do experimento).
- **Referência.** Reimers e Gurevych (2019) (similaridade de cosseno com embeddings); Kluibenschadl, Roiter e Oppl (2024).
- **Garantia no código.** `RAG_SIMILARITY_THRESHOLD` (0,60 de exemplo no `.env.example`; 0,72 na execução do relatório) e `RAG_N_RESULTS`; filtro `exclude_source` em `llm_api/rag.py`.
- **Validação.** Experimento de impacto do RAG (Seção 12.3): 7 regressões associadas a auto-correspondência, com hipótese registrada.
- **Consequência da violação.** Respostas com contexto irrelevante ou duplicado.

### RN-07 — Prefixos obrigatórios `query:`/`passage:` nos embeddings

- **Enunciado.** Consultas são embeddadas com prefixo `query:` e documentos com `passage:`.
- **Racional.** O modelo exige os prefixos; omiti-los distorce o espaço vetorial e reduz a qualidade da recuperação.
- **Referência.** Reimers e Gurevych (2019) (modelo e5); documentação do `intfloat/multilingual-e5-base`.
- **Garantia no código.** `llm_api/embeddings.py` aplica os prefixos em todas as chamadas.
- **Validação.** Coberto indiretamente pelas fases da suíte de RAG (recuperação com `n_raw` mínimo exigido).
- **Consequência da violação.** Recuperação sistematicamente pior com limiares "corrigidos" por cima.

### RN-08 — Sincronização vetorial e reuso de *chunks* idênticos

- **Enunciado.** Excluir/renomear tópico ou arquivo sincroniza os vetores; a indexação pula *chunks* idênticos já existentes.
- **Racional.** Vetores órfãos contaminam a recuperação; reaproveitar *chunks* idênticos evita *tombstones* que degradam o índice HNSW.
- **Referência.** ChromaDB (2025) (comportamento de coleções e índice); justificativa de engenharia para o reuso.
- **Garantia no código.** `POST /remove_topic_vectors` e `/rename_topic_vectors` (`llm_api/main.py`); resposta de indexação com `reaproveitados` e sonda de leitura `visivel`; ganchos em `topic_controller` e `upload_controller`.
- **Validação.** Limpeza executada ao fim de cada execução da suíte de testes; sem cobertura automatizada dedicada de reuso (Seção 12.5).
- **Consequência da violação.** Respostas vazias ocasionais (degradação do índice) e vazamento de material excluído.

### RN-09 — Tipos de questão e regra de correção

- **Enunciado.** Objetiva: rádios pelas alternativas `A)`–`F)` do enunciado; V/F: rádios `A) Verdadeiro`/`B) Falso` quando não houver alternativas; aberta: texto livre. Correção: letra do gabarito quando houver; senão comparação textual normalizada; gabarito vazio → sem veredito.
- **Racional.** O formato da resposta deve seguir o formato do enunciado, não o rótulo declarado (rótulos vêm de LLM e podem estar errados); comparar por letra tolera `B)`, `B`, `b`, `B.`; normalização tolera texto com prefixo; gabarito vazio não pode virar "errado" falso.
- **Referência.** Alshahrani et al. (2025) (geração e tipagem de questões); Roediger e Karpicke (2006) (correção imediata reforça a recuperação ativa).
- **Garantia no código.** `frontend/src/components/ResponderQuestao.js` (detecção por regex de alternativas, independente de `tipo`; mapeamento `v/f/verdadeiro/falso`).
- **Validação.** Suíte de interface: 13 verificações da aba Responder (inclui gabarito letra simples, V/F com e sem alternativas, aberta em textarea).
- **Consequência da violação.** Questão impossível de responder ou veredito falso-negativo.

### RN-10 — Estratégia de estudo só com técnicas referenciadas

- **Enunciado.** O módulo de estratégia só recomenda técnicas do compêndio com base empírica mapeado no TCC.
- **Racional.** Recomendação sem lastro científico é opinião; o compêndio garante reprodutibilidade e defesa acadêmica.
- **Referência.** Robinson (1941); Thomas e Robinson (1972); Roediger e Karpicke (2006); Cepeda et al. (2006); Leitner (1972); Rohrer (2012); Zimmerman (2000); Bonwell e Eison (1991) — ver Tabela do TCC, `tab:study_strategy_references`.
- **Garantia no código.** `llm_api/prompts/recommend_study_strategy.md`; `_worker_study_strategy`.
- **Validação.** Juiz: 8,2 (com RAG); fundamentação na Seção 5.3 do TCC.
- **Consequência da violação.** Recomendações genéricas ou sem evidência.

### RN-11 — Chaves segregadas por usuário e provedor, com rodízio

- **Enunciado.** Cada usuário usa suas próprias chaves por provedor; na ausência, cai para as chaves do ambiente; requisições percorrem as chaves em rodízio, com *cooldown* em HTTP 429 e descarte temporário de chaves recusadas.
- **Racional.** Separação de credenciais evita contaminação entre usuários; rodízio com degradação controlada evita que um limite de cota derrube o serviço.
- **Referência.** OWASP ASVS 4.0.3 (gestão de credenciais); ISO/IEC 25010:2011 (segurança, confiabilidade).
- **Garantia no código.** `llm_api/provedores.py` (`ChaveInvalida` com HTTP 400 em chave recusada/expirada), `llm_api/ollama_client.py` (escada de parâmetros, *backoff*); `backend/controllers/task_controller.py` (`_worker_generate_questions`/`_worker_generate_flashcards` repassam `user_snap.get_ollama_keys()` ao serviço de IA).
- **Validação.** Relatório: `GET /api/models` OK; suíte com conta de teste autenticada.
- **Consequência da violação.** Vazamento de chaves ou indisponibilidade em cascata.

### RN-12 — Limitação de taxa nas rotas de autenticação

- **Enunciado.** 5 tentativas de login em 15 min; 5 cadastros/hora; 5 redefinições/hora; *cooldown* de 60 s para o mesmo e-mail.
- **Racional.** Controle de força bruta e evitamento de envio abusivo de e-mails.
- **Referência.** OWASP ASVS 4.0.3 (anti automação/força bruta).
- **Garantia no código.** `backend/services/rate_limit.py` (janela deslizante por chave) usado em `backend/auth.py`; limites configuráveis em `backend/config.py`.
- **Validação.** Sem cobertura automatizada (Seção 12.5).
- **Consequência da violação.** Tentativa de força bruta ou inundação de e-mails.

### RN-13 — Intervenções de IA só sob demanda

- **Enunciado.** Sugestões de *prompt* aparecem apenas no campo que o usuário acionou; downloads de imagens/quadros acontecem só pelo modal dedicado.
- **Racional.** Intervenções gerais poluem a interface, criam ruído e ações acidentais; o controle fica com o usuário.
- **Referência.** Nielsen (1993) — heurística "controle e liberdade do usuário" e "visibilidade do estado do sistema".
- **Garantia no código.** `PromptSuggestions.js` com gatilho por campo/`resetKey`; `EmptyDownloadModal` único caminho de download de mídia.
- **Validação.** Suíte de interface: sugestões presentes após acionamento, não antes.
- **Consequência da violação.** Interface ruidosa e perda de previsibilidade.

### RN-14 — Interface em português, sem emojis, tema claro/escuro

- **Enunciado.** Todo texto de interface em pt-BR, sem emojis e sem padrões visuais que remetam a saída de IA; tema claro/escuro alternável e persistido.
- **Racional.** Consistência linguística e de identidade (documentação, mensagens e UI no mesmo idioma) e legibilidade em ambos os temas; ausência de emojis mantém tom neutro e acessível.
- **Referência.** Nielsen (1993) (consistência); W3C (2023) WCAG 2.2 (contraste e legibilidade).
- **Garantia no código.** Convenção de projeto (`AGENTS.md`); revisão em cada alteração de interface.
- **Validação.** Convenção verificada em revisão de código; sem teste automatizado de estilo.
- **Consequência da violação.** Quebra de identidade e inconsistência com a documentação.

### RN-15 — Limites de geração e nova tentativa por baixa saída

- **Enunciado.** Contexto truncado em 12000 caracteres com marcação explícita; limite de tokens por modelo; nova tentativa quando a resposta vem curta demais (`min_chars`).
- **Racional.** Controla custo, latência e risco de respostas truncadas/interrompidas.
- **Referência.** ISO/IEC 25010:2011 (eficiência de desempenho); Ollama (2025) (limites de geração); justificativa de engenharia para a regra de nova tentativa.
- **Garantia no código.** `llm_api/main.py` (`OLLAMA_MAX_TOKENS`, truncamento de contexto) e `llm_api/ollama_client.py` (`min_chars`).
- **Validação.** Relatório: tempos de geração medidos por endpoint (Seção 12.1).
- **Consequência da violação.** Respostas incompletas ou consumo descontrolado de tokens.

---

## 8. Requisitos não funcionais

Classificação pela família de características de qualidade da ISO/IEC 25010:2011.

| ID | Categoria (ISO/IEC 25010) | Requisito e meta mensurável | Evidência | Referência |
|---|---|---|---|---|
| RNF-01 | Adequação funcional | Cobertura dos fluxos principais de estudo: material → extração → resolução → prática → revisão → estratégia | Suíte de integração (18 endpoints + 9 páginas) e experimento COM/SEM RAG | ISO/IEC 25010:2011 |
| RNF-02 | Eficiência de desempenho | Operações CRUD < 1 s no cliente; P95 do teste de carga ≤ 0,05 s | Relatório: CRUD 0,003–0,010 s; carga P95 0,036 s | ISO/IEC 25010; Pressman e Maxim (2014) |
| RNF-03 | Eficiência de desempenho | Suportar 50 requisições com até 10 *threads* concorrentes com 100 % de sucesso | Relatório, Seção "Teste de Carga" | ISO/IEC 25010 |
| RNF-04 | Confiabilidade | Disponibilidade observável dos três serviços (health checks) durante a execução da suíte | Relatório: 3 serviços online (HTTP 200) | ISO/IEC 25010 |
| RNF-05 | Confiabilidade | Tolerância a falhas: *retry* com *backoff* e limite máximo, reserva (*fallback*) de juiz, cache de catálogo com expiração, reexecução de fases incompletas da suíte | `ollama_client.py`, `readme.py` (retries robustos, *clamping*, mediana) | ISO/IEC 25010 |
| RNF-06 | Segurança | Senhas só em *hash*; tokens de redefinição SHA-256 com validade; limitação de taxa nas rotas de autenticação | `auth.py`, `rate_limit.py` (Seção RN-12) | OWASP ASVS 4.0.3; ISO/IEC 25010 |
| RNF-07 | Segurança | Isolamento de dados por usuário; chaves de API segregadas e ocultáveis na interface | RN-01, RN-11 | ISO/IEC 25010 |
| RNF-08 | Usabilidade | Usabilidade percebida medida por instrumento Likert + SUS (metas: SUS ≥ 68, benchmark da literatura) | Protocolo no Apêndice B; **coleta pendente** (Seção 12.6) | Brooke (1996); Davis (1989); Hyzy et al. (2022); Djamaluddin et al. (2024) |
| RNF-09 | Usabilidade | Acessibilidade operacional: foco gerenciado em modais, navegação por teclado, fechamento por teclado/clique externo, contraste nos dois temas, erros de renderização matemático nunca em vermelho | `useModalAcessibilidade.js`; estilos `body.dark-mode`; KaTeX com `errorColor: currentColor` | W3C (2023) WCAG 2.2 |
| RNF-10 | Portabilidade | Execução reproduzível em máquina nova apenas com Docker, `.env` e chaves | `docker-compose.yml`, `README.md` (pré-requisitos) | ISO/IEC 25010 |
| RNF-11 | Manutenibilidade | Código modular (Blueprints no backend, componentes no frontend), documentação executável (guia + relatório de testes) e suíte de integração única e reexecutável | `backend/controllers/*`, `README.md`, `readme.py` | Sommerville (2015); ISO/IEC 25010 |
| RNF-12 | Compatibilidade | Navegadores modernos via SPA compilada e servida por nginx; roteamento declarado explícito no proxy | `frontend/nginx.conf`, build CRA | ISO/IEC 25010 |

---

## 9. Decisões de arquitetura e tecnologia

Formato ADR enxuto, conforme Nygard (2011) e atributos de qualidade conforme Bass, Clements e Kazman (2021).

### AD-01 — Arquitetura em três componentes (microsserviços)

- **Contexto.** Operações de IA têm latência variável e altamente distinta das operações de dados.
- **Decisão.** Frontend, backend e serviço de IA como componentes independentes comunicando por HTTP REST.
- **Alternativas.** Monolítico com LLM embutido; serviço de IA como biblioteca.
- **Justificativa.** Isola latências variáveis, permite escalonamento independente do serviço de IA e testes por componente — Newman (2015); atributos de qualidade (desempenho, escalabilidade) — Bass, Clements e Kazman (2021).
- **Consequências.** Comunicação por rede exige contratos de API estáveis; orquestração por Docker Compose.

### AD-02 — Frontend em React 19 (SPA compilada)

- **Contexto.** Interface rica em modais, pré-visualização de Markdown e edição em tempo real.
- **Decisão.** React 19 com Create React App, servido por nginx.
- **Alternativas.** SSR (Next.js); Vue/Svelte.
- **Justificativa.** Ecossistema amplo (KaTeX, Chart.js), componentes funcionais com hooks e pré-visualização direta — escolha de *framework* por adoção e produtividade, Pressman e Maxim (2014).
- **Consequências.** Cliente único (SEO irrelevante, ok); roteamento de rotas do backend deve ser declarado no nginx.

### AD-03 — Backend em Flask com Blueprints

- **Contexto.** Orquestração de dados, sessão e controle de fluxo.
- **Decisão.** Flask 3.0 com *Blueprints* por domínio (`api`, `topic`, `question`, `upload`, `download`, `note`, `article`, `task`, `auth`).
- **Alternativas.** Django (peso); FastAPI no backend.
- **Justificativa.** Modularização explícita e baixo acoplamento — Sommerville (2015); maturidade do ecossistema — Pressman e Maxim (2014).
- **Consequências.** Sem geração automática de documentação (o serviço de IA a tem).

### AD-04 — Serviço de IA em FastAPI

- **Contexto.** Orquestração de LLMs, OCR e base vetoriais com latência variável.
- **Decisão.** FastAPI com *async/await* e validação por *type hints*.
- **Alternativas.** Flask no serviço de IA; fila externa na frente.
- **Justificativa.** Assíncrono nativo evita bloqueio de requisições simultâneas; documentação OpenAPI — ISO/IEC 25010 (eficiência); justificativa de engenharia.
- **Consequências.** Dois *stacks* Python no projeto (duplicação parcial de utilitários, documentada).

### AD-05 — Base vetorial em ChromaDB

- **Contexto.** Indexar e recuperar trechos com filtros.
- **Decisão.** ChromaDB em disco, coleções `documents`, `examples` e `questions`/`corrections`.
- **Alternativas.** FAISS (sem metadados gerenciados); pgvector; SQLite-VSS.
- **Justificativa.** Leve, embutido e guarda metadados junto aos documentos, permitindo filtro por tópico/usuário/arquivo — ChromaDB (2025).
- **Consequências.** Índice degradável com *tombstones* (motiva RN-08).

### AD-06 — Embeddings multilíngues `intfloat/multilingual-e5-base`

- **Contexto.** O conteúdo é majoritariamente em português, com termos técnicos em inglês.
- **Decisão.** Modelo e5 multilíngue com prefixos `query:`/`passage:`.
- **Alternativas.** Modelos só em inglês; *hash embeddings*.
- **Justificativa.** Cobertura multilíngue e desempenho de similaridade — Reimers e Gurevych (2019).
- **Consequências.** Prefixos obrigatórios (RN-07); custo de inferência local no serviço de IA.

### AD-07 — LLMs via Ollama + catálogo multiprovedor

- **Contexto.** Precisa gerar, transcrever e avaliar sem licença comercial cara.
- **Decisão.** Ollama (local ou nuvem) + registro de seis provedores externos endereçados por `provedor/modelo`.
- **Alternativas.** API única fechada; apenas Ollama.
- **Justificativa.** Código aberto, API REST simples e ausência de custo de licença — Ollama (2025); flexibilidade de custo/limite do catálogo multiprovedor (justificativa de engenharia).
- **Consequências.** Necessidade de rodízio de chaves e *allowlists* (RN-11, RF-15).

### AD-08 — Tarefas assíncronas por *thread* com *polling* (sem fila externa)

- **Contexto.** Gerações e uploads levam de 4 s a 36 s; a requisição HTTP não pode bloquear.
- **Decisão.** Gerenciador de tarefas em processo (com trava, limpeza e histórico) + cliente consultando `/tasks`.
- **Alternativas.** Celery/RQ com Redis; SSE/WebSockets.
- **Justificativa.** Escopo de usuário único com volume baixo: fila externa adicionaria operação sem benefício proporcional — Sommerville (2015) (simplicidade/alinhamento de arquitetura); justificativa de engenharia.
- **Consequências.** Reinício do backend reinicia o estado de tarefas; padrão prevalece para novos endpoints pesados.

### AD-09 — Persistência em SQLite (WAL) com JSON legado congelado

- **Contexto.** O conteúdo era gravado em JSON por tópico: leitura-modificação-escrita sem bloqueio, sem integridade referencial.
- **Decisão.** Tabelas em SQLite (modo WAL) com FKs para `user`; arquivos JSON antigos mantidos como *backup* congelado e importados na subida.
- **Alternativas.** PostgreSQL; manter JSON.
- **Justificativa.** Transações, integridade referencial e migração idempotente — SQLite (2024); justificativa de engenharia.
- **Consequências.** Sistema exige `migrate.py` na subida (feito no CMD do Docker).

### AD-10 — Markdown + KaTeX com camada de reparo de LaTeX

- **Contexto.** LLMs escapam mal caracteres de LaTeX (`\frac` vira `form` + `rac`).
- **Decisão.** Três camadas de reparo: saneamento antes do `json.loads`, reparo de texto persistido e reparo em tempo de renderização, com listas de comandos sincronizadas.
- **Alternativas.** Exigir JSON estrito do modelo; renderizar como texto puro.
- **Justificativa.** Defesa em profundidade sobre saída não confiável — justificativa de engenharia; KaTeX valida cada trecho antes de envolver (evita erros vermelhos).
- **Consequências.** Três cópias sincronizadas de listas de comandos (risco documentado).

### AD-11 — RAG em três coleções com semânticas distintas

- **Contexto.** Material do usuário, exemplos de resolução e padrões de correção têm naturezas diferentes.
- **Decisão.** `documents` (material), `examples` (exemplos) e `corrections` (padrões de correção) + `questions` (corpus compartilhado).
- **Alternativas.** Uma coleção única com metadados.
- **Justificativa.** Recuperação por domínio semântico com filtro por metadados — Lewis et al. (2020); ChromaDB (2025); Kluibenschadl, Roiter e Oppl (2024).
- **Consequências.** Manutenção de limpeza por coleção (RN-08).

### AD-12 — Avaliação por LLM-as-a-Judge com dois avaliadores

- **Contexto.** Milhares de respostas não podem ser avaliadas manualmente.
- **Decisão.** Juiz principal com reserva (*fallback*) e mediana de três execuções (RN-05), isolado de qualquer dado do usuário.
- **Alternativas.** Avaliação humana em escala; juiz único.
- **Justificativa.** Paradigma consolidado — Zheng et al. (2023); viéses conhecidos — Wang et al. (2023).
- **Consequências.** Custo de avaliação; necessidade de controle de confundimento (RN-04).

### AD-13 — OCR local (Tesseract) com reserva externa

- **Contexto.** Extração de texto de fotos e PDFs.
- **Decisão.** Tesseract (`por`, `eng`) como padrão, com API externa de reserva.
- **Alternativas.** Modelo de visão puro; OCR pago por padrão.
- **Justificativa.** Custo zero e execução local; reserva para casos difíceis — justificativa de engenharia (uso de OCR documentado em Smith, 2007 como prática estabelecida de reconhecimento óptico).
- **Consequências.** Qualidade variável em fotos de baixa resolução; transcrição por modelo de visão cobre o caso.

---

## 10. Racional pedagógico das funcionalidades

Cada funcionalidade de estudo se apoia em um princípio com base empírica (detalhamento no TCC, Seção 5.3, `subsec:fundamentacao_referencias`).

| Funcionalidade | Princípio | Referência |
|---|---|---|
| Flashcards com resposta oculta | Recuperação ativa / *testing effect* | Roediger e Karpicke (2006); Karpicke e Roediger (2008) |
| Aba Responder com conferência imediata | Recuperação ativa e correção imediata | Roediger e Karpicke (2006); Ericsson (1993) |
| Sessões e histórico com revisitação | Repetição espaçada; sistema Leitner | Cepeda et al. (2006); Leitner (1972); Wozniak e Gorzelanczyk (1994) |
| Estratégia de estudo | SQ3R, PQ4R, intercalação, autorregulação | Robinson (1941); Thomas e Robinson (1972); Rohrer (2012); Zimmerman (2000) |
| Quadro branco e anotações | Pensamento visual e representações externas | Arnheim (1969); TCC Seção 2.8 |
| Questões objetivas e discursivas geradas | Aprendizagem baseada em problemas e aprendizagem ativa; níveis de domínio | Barrows e Tamblyn (1980); Bonwell e Eison (1991); Bloom (1956) |
| Fluxo completo material → prática | Prática deliberada | Ericsson (1993) |
| Recomendação fundamentada | Ensino pela explicação / aprender ensinando | Koh, Lee e Lim (2018) |

---

## 11. Matriz de rastreabilidade

| RF | US | RN/RNF | Implementação principal | Validação | Seção do TCC |
|---|---|---|---|---|---|
| RF-01 | US-01, US-02 | RN-12; RNF-06 | `auth.py`, `rate_limit.py` | Suíte (login), verificação estática (rate limit) | 4.1 |
| RF-02 | US-03 | RNF-01 | `topic_controller.py`, `TopicView.js` | Endpoints `/api/topics`; 10 verificações de rename | 4.1, 5.2 |
| RF-03 | US-04, US-15 | RNF-01 | `upload_controller.py`, `UploadFilesModal.js` | Fluxo de upload completo na suíte de interface | 5.2 |
| RF-04 | US-05 | RNF-05 | `ocr_service.py`, `image_service.py` | Endpoint `/analyze_with_image`; juiz (resoluções) | 4.2 |
| RF-05 | US-05, US-06 | RNF-01 | `question_controller.py` (`/save`) | Endpoint `/save_answers`; juiz (clareza) | 4.2, 5.2 |
| RF-06 | US-06 | RNF-11 | `QuestionEditor.js`, `question_controller.py` | Cenário de questões de texto na suíte | 5.2 |
| RF-07 | US-07, US-08 | RN-09 | `ResponderQuestao.js` | 13 verificações da aba Responder | 5.2 |
| RF-08 | US-09 | RNF-01 | `note_controller.py`, `AnnotationEditor.js` | Manual (sem teste dedicado) | 5.2 |
| RF-09 | US-10 | RNF-01 | `Whiteboard.js`, `download_controller.py` | Endpoint `/save_whiteboard` | 5.2 |
| RF-10 | US-11, US-18 | RN-02, RN-03, RN-15; RNF-08 | `QuestionGeneratorModal.js`, `_worker_generate_questions` | Endpoint `/generate_questions`; juiz 7,0; dica de material | 5.3 |
| RF-11 | US-12 | RN-02, RN-10 | `FlashcardsViewer.js`, `_worker_generate_flashcards` | Endpoint `/generate_flashcards`; juiz 8,4 | 5.3 |
| RF-12 | US-13 | RN-10, RN-02 | `StudyStrategyModal.js`, `_worker_study_strategy` | Endpoints de estratégia; juiz 8,2 | 5.3 |
| RF-13 | US-14 | RN-03, RN-13 | `article_controller.py`, `ArticleSearchModal.js` | Endpoint `/search_articles`; juiz 7,6; sugestões | 5.3 |
| RF-14 | US-15 | RN-01, RN-06, RN-07, RN-08 | `rag.py`, `embeddings.py`, `data_loader.py` | Experimento COM/SEM RAG | 4.4, 5.1 |
| RF-15 | US-02, US-16 | RN-11 | `provedores.py`, `api_controller.py` | Endpoints `/api/models`, `/models` | 4.2 |
| RF-16 | US-16 | RNF-05 | `task_manager.py`, `TaskContext.js` | Indicador de tarefas na suíte; sonda de tópico | 4.2 |
| RF-17 | US-17 | RNF-01 | `SessionsViewer.js`, rotas `sessions` | Endpoint `/sessions` | 5.2 |
| RF-18 | US-17 | RN-13 | `download_controller.py`, `EmptyDownloadModal.js` | Manual (sem teste dedicado) | 5.2 |
| RF-19 | US-18 | RNF-09 | `ConfigModal.js` | Manual (sem teste dedicado) | 5.2 |
| RF-20 | US-11, US-12, US-13 | RN-02, RN-03 | `SugestoesContexto.js`, `_contexto_sugestoes` | Suíte (dica, sugestões) + teste de API com foco | 5.3 |

---

## 12. Validação e conformidade

### 12.1 Desempenho, endpoints e carga

Evidências do Relatório de Testes Automatizados (`README.md`, execução de **30/09/2026**, status final **APROVADO**):

| Métrica | Valor |
|---|---|
| Serviços online | 3/3 (frontend, backend, serviço de IA) |
| Endpoints testados | 18 — 100 % OK |
| Páginas/recursos do frontend | 9 — 100 % OK |
| Teste de carga | 50 requisições, 100 % de sucesso, média 0,024 s, P95 0,036 s, máx 0,037 s |
| Tempo de geração | questões 4,904 s; flashcards 36,109 s; estratégia 10,682 s; artigos 3,919 s; análise de imagem 24,684 s |
| Operações CRUD | 0,003 – 0,119 s |

### 12.2 Qualidade das respostas (LLM Judge)

Notas médias por funcionalidade (condição com RAG; TCC, Seção 6.7, `tab:functionality_avg`):

| Funcionalidade | Nota (0–10) |
|---|---|
| Flashcards | 8,4 |
| Estratégia de estudo | 8,2 |
| Pesquisa de artigos | 7,6 (condição única) |
| Geração de questões | 7,0 |
| Clareza global das resoluções | 6,91 |

### 12.3 Impacto do RAG (COM vs SEM)

Experimento controlado de 50 casos (TCC, Seção 6.8, `tab:rag_delta`): Δ precisão **+0,14**, Δ completude **+0,12**, Δ clareza **0,00**, Δ raciocínio **+0,12**, com 7 regressões registradas e hipótese de auto-correspondência (*self-match*) — base da regra RN-06.

### 12.4 Suíte de verificação da interface

43 verificações automatizadas de navegador executadas durante o desenvolvimento, cobrindo: renomeação de tópico (10), aba Responder e correção em todos os formatos (13), fluxo de upload com tarefas (8), geração com orientação de pouco material (1), busca de artigos e sugestões automáticas (2) e `/suggest_prompts` com instruções de foco (1), além de verificações de abertura/fechamento de modais. Registro de execução: 43/43.

> **Nota.** Esta suíte é auxiliar e não está versionada no repositório; a suíte de integração oficial e reexecutável é `python readme.py` (Seção 12.1).

### 12.5 Itens sem cobertura automatizada

| Item | Justificativa / plano |
|---|---|
| Isolamento por usuário (RN-01) | Verificação estática; incluir teste de dois usuários no plano de expansão |
| Limitação de taxa (RN-12) | Verificação estática da configuração (5/15 min, 5/h) |
| Anotações (RF-08) | Fluxo manual |
| Downloads (RF-18) | Fluxo manual (modal único já garante o caminho) |
| Configurações e tema (RF-19) | Fluxo manual |
| Reuso de *chunks* idênticos (RN-08) | Resposta de indexação (`reaproveitados`) existe; asserção automática pendente |
| Suíte de interface (Seção 12.4) | Não versionada; candidata a entrar no repositório |

### 12.6 Validação perceptiva (pendente)

O questionário do Apêndice B está elaborado e fundamentado (TAM — Davis, 1989; SUS — Brooke, 1996), **sem coleta concluída até esta versão**: nenhuma nota perceptiva é reportada como resultado. O TCC apresenta o modelo de consolidação com as colunas perceptivas em aberto (`tab:usabilidade_vs_judge`), e este documento reforça o mesmo estado (RNF-08).

---

## 13. Fora de escopo e limitações deliberadas

| Item | Natureza da decisão |
|---|---|
| Colaboração multiusuário em um mesmo tópico | Fora de escopo da versão: o sistema é individual (RN-01) |
| Aplicação nativa mobile | Fora de escopo: web responsiva atende ao caso de uso |
| Interface multilíngue | Deliberado: documentação e UI em pt-BR (RN-14) |
| `llm_api` sem autenticação | Deliberado: componente interno atrás do proxy do frontend; não expor publicamente |
| Fila externa de tarefas | Adiado: gerenciador em processo atende ao volume (AD-08) |
| Coleta de usabilidade | Em andamento: instrumento pronto, coleta não concluída (Seção 12.6) |
| `.env.example` com temperaturas desiguais | Inconsistência conhecida do *template*: produção usa 0,0/0,0 (RN-04); alinhar o exemplo |
| Suíte de interface não versionada | Limite de processo (Seção 12.5) |
| Notas de questões históricas sem metadado `contexto` | Avisos só aparecem em gerações a partir desta versão (RF-20) |

---

*Documento elaborado por Yago Melo da Costa (2026), material de apoio ao TCC ExercitaAI.*
