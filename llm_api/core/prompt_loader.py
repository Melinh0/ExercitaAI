from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

def load_prompt(name):
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

ANALYZE_PROMPT_TEMPLATE = load_prompt("analyze_image")
REFINEMENT_PROMPT_TEMPLATE = load_prompt("refinement")