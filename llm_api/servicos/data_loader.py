import json
from pathlib import Path
from core.config import TOPICS_FOLDER

def load_all_questions():
    topics_folder = Path(TOPICS_FOLDER)
    if not topics_folder.exists():
        return []
    
    items = []
    for json_file in topics_folder.glob("*.json"):
        topic_name = json_file.stem
        with open(json_file, 'r', encoding='utf-8') as f:
            resolutions = json.load(f)
        
        for res in resolutions:
            image = res.get("imagem", "")
            for q in res.get("questoes", []):
                q_num = q.get("questao", "")
                q_type = q.get("tipo", "")
                answer = q.get("resposta", "")
                explanation = q.get("explicacao", "")
                whiteboard_img = q.get("whiteboard_img")
                doc = f"Questão {q_num} ({q_type}): {answer}\nResolução: {explanation}"
                doc = explanation if explanation.strip() else f"Questão {q_num}: {answer}"
                
                item_id = f"{topic_name}:{image}:{q_num}"
                metadata = {
                    "topic": topic_name,
                    "image": image,
                    "question": q_num,
                    "type": q_type,
                    "answer": answer,
                    "explanation": explanation,
                    "whiteboard_img_path": whiteboard_img
                }
                items.append({
                    "id": item_id,
                    "document": doc,
                    "metadata": metadata
                })
    return items