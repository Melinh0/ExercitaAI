Você recebe o **conteúdo atual de uma questão já salva** em um tópico de estudos e sua tarefa é **reescrever a questão aplicando as instruções do usuário**, preservando o resto.

Este texto **não veio de uma imagem**: é o registro editável da questão (enunciado, alternativas, resposta e resolução). Por isso **não basta transcrever** — você deve alterar exatamente o que foi pedido.

**Prioridade das instruções:**

1. Se houver, acima deste texto, o bloco **INSTRUÇÕES PRIORITÁRIAS DO USUÁRIO**, ele é a ordem principal: aplique-o literalmente nos campos correspondentes (enunciado, resposta, explicacao). Exemplos: "corrija o erro do enunciado", "encurte o enunciado", "reescreva de forma mais simples", "melhore a resolução com um exemplo".
2. Sem instruções, mantenha o enunciado e a resposta como estão (corrigindo apenas erros óbvios de escrita) e entregue a resolução completa da questão.
3. Quando as instruções pedirem alteração só de um campo, **mantenha os outros campos exatamente como estão** (copie `resposta` e `explicacao` sem reescrever).
4. **Preserve o que não foi pedido para mudar**: alternativas, subitens (a, b, c / I, II / 1, 2, 3), dados numéricos, fórmulas e a resolução que continua correta. Não adicione nem remova partes do enunciado por conta própria.
5. Se houver bloco de contexto recuperado da base de conhecimento, use-o apenas para enriquecer conceitos, sem encurtar a resolução e sem mencioná-lo.

**Regras dos campos:**

- `numero`: "1".
- `tipo`: mantenha o tipo atual da questão (interpretacao, objetiva ou discursiva).
- `enunciado`: a questão completa, com alternativas e subitens, já com as instruções aplicadas.
- `resposta`: a conclusão final da própria `explicacao` — copie literalmente a linha que encerra o raciocínio ("Resposta final: ..."), sem recalcular e sem inventar valor que não exista no corpo.
- `explicacao`: resolução completa em Markdown/LaTeX, passo a passo, terminando com "Resposta final: ..." e, em seguida, a seção `Auto-verificação:`.

**Formato de saída:** apenas JSON válido, sem nenhum texto fora dele:

{
  "questions": [
    {
      "numero": "1",
      "tipo": "interpretacao | objetiva | discursiva",
      "enunciado": "string",
      "resposta": "string",
      "explicacao": "string"
    }
  ]
}

Conteúdo atual da questão:

{ocr_text}

Aplique as instruções recebidas e devolva o JSON com a questão atualizada.
