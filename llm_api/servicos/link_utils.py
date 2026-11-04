import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def fetch_doi_metadata(doi):
    try:
        url = f"https://api.crossref.org/works/{doi}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            message = data.get('message', {})
            title = message.get('title', [''])[0]
            abstract = message.get('abstract', '')
            if abstract:
                abstract = re.sub('<[^<]+?>', '', abstract)
            return {
                'title': title,
                'abstract': abstract,
                'doi': doi,
                'source': message.get('container-title', [''])[0] if message.get('container-title') else ''
            }
    except Exception as e:
        logger.warning(f"Erro ao buscar DOI {doi}: {e}")
    return None

def extract_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = '\n'.join(lines)
        if len(text) < 200:
            return None
        return text
    except Exception as e:
        logger.warning(f"Erro ao extrair texto da URL {url}: {e}")
        return None

def is_article_url(url):
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    domain = parsed.netloc.lower()
    academic_domains = ['doi.org', 'sciencedirect.com', 'springer.com', 'nature.com', 'ieee.org', 'acm.org', 'arxiv.org', 'pubmed.ncbi.nlm.nih.gov', 'ncbi.nlm.nih.gov', 'plos.org', 'wiley.com', 'tandfonline.com', 'sagepub.com', 'jstor.org', 'cambridge.org', 'oup.com']
    if any(d in domain for d in academic_domains):
        return True
    if 'doi' in url.lower() or '10.' in url:
        return True
    return False

def extract_doi_from_text(text):
    pattern = r'10\.\d{4,9}/[-._;()/:A-Z0-9]+'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(0)
    return None

def get_link_summary(url):
    if not url:
        return None
    if 'doi.org' in url:
        doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', url, re.IGNORECASE)
        if doi_match:
            doi = doi_match.group(0)
            meta = fetch_doi_metadata(doi)
            if meta:
                return meta
    if not is_article_url(url):
        return None
    text = extract_text_from_url(url)
    if not text:
        return None
    doi = extract_doi_from_text(text)
    if doi:
        meta = fetch_doi_metadata(doi)
        if meta:
            return meta
    return {'title': 'Conteúdo extraído', 'abstract': text[:3000], 'source': url}