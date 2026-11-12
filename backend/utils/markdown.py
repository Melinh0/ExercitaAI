import markdown

def markdown_to_html(text):
    if not text:
        return ""
    return markdown.markdown(text, extensions=['extra'])