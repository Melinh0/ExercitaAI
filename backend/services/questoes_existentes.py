from models.topic_model import TopicModel


def listar_questoes_existentes(user, topic_name, limite=120):
    itens = []
    vistos = set()
    for item in TopicModel.get_resolutions(user, topic_name):
        for questao in item.get('questoes', []):
            texto = ' '.join((questao.get('enunciado') or '').split())[:200]
            if not texto or texto in vistos:
                continue
            vistos.add(texto)
            itens.append(texto)
            if len(itens) >= limite:
                return itens
    return itens
