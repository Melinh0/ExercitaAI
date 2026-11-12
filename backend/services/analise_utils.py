PLACEHOLDERS_ANALISE = {
    "Nao informada automaticamente",
    "Resolucao nao disponivel.",
    "Consulte o enunciado",
    "Nao informada",
    "Não informada",
}


def texto_da_questao(item):
    texto = (item.get('texto') or '').strip()
    if texto:
        return texto
    return "\n\n".join(
        (q.get('enunciado') or '').strip()
        for q in item.get('questoes', [])
    ).strip()


def aplicar_questao_texto(item, nova, texto_base):
    alvos = item.get('questoes') or []
    alvo = alvos[0] if alvos else None
    if alvo is None:
        alvo = {"questao": "1", "whiteboard_img": None}
        item['questoes'] = [alvo]
    alvo.setdefault('questao', '1')
    for campo in ('enunciado', 'resposta', 'explicacao', 'tipo'):
        valor = (nova.get(campo) or '').strip()
        if not valor or valor in PLACEHOLDERS_ANALISE:
            continue
        alvo[campo] = nova[campo]
    item['texto'] = (alvo.get('enunciado') or '').strip() or texto_base
    return alvo
