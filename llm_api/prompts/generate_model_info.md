# Ficha informativa de modelo de LLM

Você redige, para o usuário final do **Exercita AI** (plataforma de estudos que gera questões e flashcards a partir de imagens de prova, recomenda estratégias de estudo, analisa imagens com visão, recupera trechos de PDFs indexados com RAG e busca artigos científicos), uma ficha informativa curta sobre um modelo de LLM integrado ao app (via Ollama, OpenAI, Groq, Google Gemini, OpenRouter, DeepSeek, Anthropic ou NVIDIA).

Modelo a descrever: `{MODELO}`

Pesquisa na página oficial do modelo: {DESCRICAO_FONTE}

Quando a pesquisa acima trouxer uma descrição coletada, use-a como base factual da ficha (o que o modelo faz, idiomas, contexto, capacidades) e não invente detalhes além dela; complete com contexto geral do provedor quando necessário. Se constar que não foi possível coletar, redija a partir do seu conhecimento, sem afirmações muito específicas de versão, preço ou desempenho.

Responda APENAS com um objeto JSON válido (sem cercas de código, sem comentários, sem texto antes ou depois), contendo exatamente estas chaves:

- `"name"`: nome amigável do modelo para exibição (ex.: "GPT-OSS 120B").
- `"tagline"`: chamada curta de até 60 caracteres, sem ponto final.
- `"description"`: 2 a 3 frases em português do Brasil explicando o que é o modelo, onde roda (nuvem ou local) e seu perfil geral de uso.
- `"pros"`: lista com 3 a 5 pontos positivos, frases curtas sem ponto final no fim de cada item.
- `"cons"`: lista com 3 a 5 pontos negativos/limitações, no mesmo formato.
- `"bestFor"`: 1 a 2 frases dizendo para que tarefas do Exercita AI esse modelo é mais indicado.
- `"link"`: URL da página do modelo. Para modelos do Ollama (sem prefixo), a página em https://ollama.com/ (padrão: `https://ollama.com/library/<nome>`). Para modelos com prefixo de provedor, a página específica do modelo no site do provedor (ex.: NVIDIA `https://build.nvidia.com/<org>/<modelo>`, OpenRouter `https://openrouter.ai/<org>/<modelo>`, Groq `https://console.groq.com/docs/model/<modelo>`; se não houver página específica, use a página de modelos do provedor).

Regras:

1. Todo o texto em português do Brasil, tom divulgativo, honesto e sem exageros de marketing.
2. Não invente preços nem garantias de gratuidade; se mencionar disponibilidade, use "conforme disponibilidade e plano da conta".
3. Não repita o nome do modelo desnecessariamente dentro dos textos.
4. Seja objetivo: o usuário lê essa ficha para escolher entre os modelos disponíveis na lista.

Exemplo do formato esperado (conteúdo de OUTRO modelo — use apenas o formato):

{
  "name": "Gemma 4 Cloud",
  "tagline": "Equilíbrio entre velocidade e qualidade",
  "description": "Versão do Gemma 4 hospedada na nuvem do Ollama. Modelo otimizado para tarefas do dia a dia: geração de questões, resumos, análise de imagens simples e criação de flashcards. Boa velocidade de resposta e suporta entrada de imagens (visão).",
  "pros": [
    "Respostas rápidas (segundos em vez de minutos)",
    "Suporta visão para analisar imagens e diagramas",
    "Bom custo-benefício para uso contínuo",
    "Ideal para tarefas curtas e médias"
  ],
  "cons": [
    "Menor precisão em raciocínio matemático complexo",
    "Menor retenção de contexto em textos muito longos",
    "Pode gerar respostas mais genéricas"
  ],
  "bestFor": "Geração de questões objetivas, flashcards, resumos rápidos, análise de imagens de provas, recomendação de estratégia de estudo.",
  "link": "https://ollama.com/library/gemma4:cloud"
}
