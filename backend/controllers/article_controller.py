from flask import Blueprint, request, jsonify
from flask_login import login_required
from services.ollama_guard import require_ollama_key
from services.rag_client import post_llm_api
from config import Config
import requests
import logging
import concurrent.futures
import re
import unicodedata

article_bp = Blueprint('article', __name__)
logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
    "and", "or", "by", "from", "as", "is", "are", "was", "were",
    "study", "research", "approach", "analysis", "review", "paper",
    "article", "journal", "method", "methods", "using", "based"
}


def _normalize_title(title):
    if not title:
        return ""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def _token_set(text):
    if not text:
        return set()
    text = text.lower()
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    tokens = re.findall(r'[a-z]{3,}', text)
    return {t for t in tokens if t not in STOPWORDS}


def _is_relevant(title, abstract, query_tokens):
    if not query_tokens:
        return True
    combined = (title or "") + " " + (abstract or "")
    candidate_tokens = _token_set(combined)
    if not candidate_tokens:
        return False
    overlap = query_tokens & candidate_tokens
    if len(overlap) >= 2:
        return True
    if len(overlap) == 1 and len(query_tokens) <= 2:
        return True
    return False


def search_crossref(query, rows=20):
    url = f"https://api.crossref.org/works?query={query}&rows={rows}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            items = resp.json().get('message', {}).get('items', [])
            results = []
            for item in items:
                title = item.get('title', [''])[0]
                if not title:
                    continue
                doi = item.get('DOI')
                authors = ', '.join([
                    f"{a.get('family', '')} {a.get('given', '')}".strip()
                    for a in item.get('author', [])
                ])
                source = item.get('container-title', [''])[0] if item.get('container-title') else ''
                link = f"https://doi.org/{doi}" if doi else None
                abstract = item.get('abstract', '')
                if abstract:
                    abstract = re.sub('<[^<]+?>', '', abstract)
                results.append({
                    'title': title,
                    'authors': authors or 'Autor não informado',
                    'source': source or 'Fonte não informada',
                    'link': link,
                    'doi': doi,
                    'abstract': abstract,
                    'database': 'CrossRef'
                })
            return results
    except Exception as e:
        logger.warning(f"CrossRef error: {e}")
    return []


def search_arxiv(query, max_results=20):
    url = "http://export.arxiv.org/api/query"
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            import xml.etree.ElementTree as ET
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            root = ET.fromstring(resp.text)
            entries = root.findall('atom:entry', ns)
            results = []
            for entry in entries:
                title_elem = entry.find('atom:title', ns)
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ''
                if not title:
                    continue
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None and name.text:
                        authors.append(name.text)
                authors_str = ', '.join(authors) if authors else 'Autor não informado'
                link_elem = entry.find('atom:link', ns)
                link = link_elem.get('href') if link_elem is not None else None
                arxiv_id_elem = entry.find('atom:id', ns)
                arxiv_id = arxiv_id_elem.text.split('/')[-1] if arxiv_id_elem is not None and arxiv_id_elem.text else ''
                summary_elem = entry.find('atom:summary', ns)
                abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ''
                results.append({
                    'title': title,
                    'authors': authors_str,
                    'source': 'arXiv',
                    'link': link,
                    'doi': None,
                    'arxiv_id': arxiv_id,
                    'abstract': abstract,
                    'database': 'arXiv'
                })
            return results
    except Exception as e:
        logger.warning(f"arXiv error: {e}")
    return []


def search_pubmed(query, max_results=20):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_url = f"{base_url}/esearch.fcgi?db=pubmed&term={query}&retmax={max_results}&retmode=json"
    try:
        resp = requests.get(search_url, timeout=15)
        if resp.status_code != 200:
            return []
        ids = resp.json().get('esearchresult', {}).get('idlist', [])
        if not ids:
            return []
        id_str = ','.join(ids)
        fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={id_str}&retmode=xml"
        resp = requests.get(fetch_url, timeout=15)
        if resp.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        results = []
        for article in root.findall('.//PubmedArticle'):
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ''
            if not title:
                continue
            authors = []
            for author in article.findall('.//Author'):
                last = author.find('LastName')
                fore = author.find('ForeName')
                if last is not None and fore is not None:
                    authors.append(f"{fore.text} {last.text}".strip())
                elif last is not None and last.text:
                    authors.append(last.text)
            authors_str = ', '.join(authors) if authors else 'Autor não informado'
            pmid = article.find('.//PMID')
            pmid_id = pmid.text if pmid is not None else ''
            journal = article.find('.//Journal/Title')
            journal_name = journal.text if journal is not None else ''
            abstract_parts = []
            for abst in article.findall('.//AbstractText'):
                if abst.text:
                    abstract_parts.append(abst.text)
            abstract = " ".join(abstract_parts)
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid_id}/" if pmid_id else None
            results.append({
                'title': title,
                'authors': authors_str,
                'source': journal_name or 'PubMed',
                'link': link,
                'doi': None,
                'pmid': pmid_id,
                'abstract': abstract,
                'database': 'PubMed'
            })
        return results
    except Exception as e:
        logger.warning(f"PubMed error: {e}")
    return []


def search_semantic_scholar(query, max_results=20):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': query,
        'limit': max_results,
        'fields': 'title,authors,venue,externalIds,url,abstract'
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            items = resp.json().get('data', [])
            results = []
            for item in items:
                title = item.get('title', '')
                if not title:
                    continue
                authors = ', '.join([a.get('name', '') for a in item.get('authors', []) if a.get('name')])
                source = item.get('venue', '')
                link = item.get('url')
                doi = item.get('externalIds', {}).get('DOI')
                arxiv = item.get('externalIds', {}).get('ArXiv')
                abstract = item.get('abstract', '') or ''
                results.append({
                    'title': title,
                    'authors': authors or 'Autor não informado',
                    'source': source or 'Semantic Scholar',
                    'link': link,
                    'doi': doi,
                    'arxiv_id': arxiv,
                    'abstract': abstract,
                    'database': 'Semantic Scholar'
                })
            return results
    except Exception as e:
        logger.warning(f"Semantic Scholar error: {e}")
    return []


@article_bp.route('/search_articles', methods=['POST'])
@login_required
@require_ollama_key
def search_articles():
    data = request.get_json()
    user_query = data.get('query')
    if not user_query:
        return jsonify({'error': 'Query é obrigatória'}), 400

    refined_query = user_query
    try:
        resp = post_llm_api(
            "/refine_search_query",
            json={"query": user_query},
            timeout=30
        )
        if resp.ok:
            refined_query = resp.json().get('refined_query', user_query) or user_query
            logger.info(f"[search_articles] refined_query='{refined_query}'")
        else:
            logger.warning(f"Falha no refinamento: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Erro ao chamar refine_search_query: {e}")

    query_tokens = _token_set(refined_query)

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_crossref = executor.submit(search_crossref, refined_query, 20)
        future_arxiv = executor.submit(search_arxiv, refined_query, 20)
        future_pubmed = executor.submit(search_pubmed, refined_query, 20)
        future_semantic = executor.submit(search_semantic_scholar, refined_query, 20)

        for future in concurrent.futures.as_completed(
            [future_crossref, future_arxiv, future_pubmed, future_semantic]
        ):
            try:
                results = future.result()
                if results:
                    all_results.extend(results)
            except Exception as e:
                logger.warning(f"Erro em uma fonte: {e}")

    relevant_results = []
    for r in all_results:
        title = r.get('title', '')
        abstract = r.get('abstract', '')
        if _is_relevant(title, abstract, query_tokens):
            relevant_results.append(r)

    if not relevant_results:
        logger.warning(
            f"[search_articles] Nenhum resultado relevante para '{refined_query}'. "
            f"Retornando os primeiros brutos."
        )
        relevant_results = all_results

    seen_titles = set()
    unique_results = []
    for r in relevant_results:
        title_key = _normalize_title(r.get('title', ''))
        if not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        r.pop('abstract', None)
        unique_results.append(r)

    unique_results = unique_results[:30]

    logger.info(
        f"[search_articles] refined='{refined_query}' "
        f"raw={len(all_results)} relevantes={len(relevant_results)} finais={len(unique_results)}"
    )

    return jsonify({
        'success': True,
        'results': unique_results,
        'refined_query': refined_query,
        'total_sources': 4
    })