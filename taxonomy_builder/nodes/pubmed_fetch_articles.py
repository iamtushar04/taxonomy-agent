import urllib.request
import xml.etree.ElementTree as ET
from taxonomy_builder.pubmed_state import PubMedGenerationState

def fetch_pubmed_abstract(pmid: str) -> dict:
    url = f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            title_elem = root.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else 'No Title'
            
            authors = []
            for author in root.findall('.//Author'):
                last = author.find('LastName')
                first = author.find('ForeName')
                if last is not None and first is not None:
                    authors.append(f"{first.text} {last.text}")
                elif last is not None:
                    authors.append(last.text)

            journal_elem = root.find('.//Title')
            journal = journal_elem.text if journal_elem is not None else 'Unknown Journal'

            abstract_texts = []
            for abstract_text in root.findall('.//AbstractText'):
                label = abstract_text.get('Label', '')
                text = ''.join(abstract_text.itertext())
                if label:
                    abstract_texts.append(f'{label}: {text}')
                else:
                    abstract_texts.append(text)
            
            abstract = '\n'.join(abstract_texts) if abstract_texts else 'No Abstract'
            
            return {
                "title": title,
                "authors": authors,
                "journal": journal,
                "abstract": abstract,
                "full_text": f"Title: {title}\nJournal: {journal}\n\nAbstract:\n{abstract}"
            }
    except Exception as e:
        print(f"Failed to fetch PMID {pmid}: {e}")
        return {}

def pubmed_fetch_articles(state: PubMedGenerationState) -> dict:
    print("--- FETCHING PUBMED ARTICLES ---")
    pmids = state.get("pmids", [])
    pubmed_data = {}
    
    for pmid in pmids:
        print(f"Fetching {pmid}...")
        data = fetch_pubmed_abstract(pmid)
        if data:
            pubmed_data[pmid] = data
            
    return {"pubmed_data": pubmed_data}
