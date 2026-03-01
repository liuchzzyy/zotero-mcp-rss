"""
classify_shortterms.py
======================
Route items from 01_SHORTTERMS to the correct inbox collection.

Routing rules:
  No AI分析 tag          → 00_INBOXS_AA
  AI分析 + 0 PDFs        → 00_INBOXS_AA
  AI分析 + 1 PDF review  → 00_INBOXS_BB
  AI分析 + 1 PDF SI/main → 00_INBOXS_AA  (attempts SI download for main)
  AI分析 + 2+ PDFs       → 00_INBOXS_CC  (distinct: main + SI)
                         → 00_INBOXS_DD  (duplicate: same article twice)

Commands:
  uv run python scripts/classify_shortterms.py           # route 01_SHORTTERMS
  uv run python scripts/classify_shortterms.py recheck   # re-check DD and CC
"""
import os
import sys
import re
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from dotenv import load_dotenv
from openai import OpenAI
import pyzotero.zotero as zotero
import requests

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

# ── Config ────────────────────────────────────────────────────────────────────
LIBRARY_ID        = os.environ['ZOTERO_LIBRARY_ID']
API_KEY           = os.environ['ZOTERO_API_KEY']
DEEPSEEK_API_KEY  = os.environ['DEEPSEEK_API_KEY']
DEEPSEEK_BASE_URL = os.environ['DEEPSEEK_BASE_URL']
ELSEVIER_API_KEY  = os.environ['ELSEVIER_API_KEY']

SHORTTERMS_KEY = os.environ['ZOTERO_SHORTTERMS_KEY']   # 01_SHORTTERMS (source)
AA_KEY         = os.environ['ZOTERO_INBOXS_AA_KEY']    # 00_INBOXS_AA
BB_KEY         = os.environ['ZOTERO_INBOXS_BB_KEY']    # 00_INBOXS_BB
CC_KEY         = os.environ['ZOTERO_INBOXS_CC_KEY']    # 00_INBOXS_CC
DD_KEY         = os.environ['ZOTERO_INBOXS_DD_KEY']    # 00_INBOXS_DD

ZOTERO_STORAGE = Path(os.environ['ZOTERO_STORAGE_PATH'])
SI_DIR         = Path(os.environ['SHORTTERMS_SI_DIR'])
BLOCKED_FILE   = Path(os.environ['SHORTTERMS_BLOCKED_FILE'])
SI_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT    = {'.pdf', '.docx', '.doc'}
MAX_MMC        = 8
PDF_MAX_CHARS  = 2000
PDF_MAX_PAGES  = 3
OLE_MAGIC      = b'\xd0\xcf\x11\xe0'

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}
PII_RE       = re.compile(r'pii[/=](S\w+)', re.I)
SI_KEYWORDS  = ['supporting', 'suppl', '_si_', '_si.', 'si_00', 'supp_', 'mmc', 'suppdata']

# ── Clients ───────────────────────────────────────────────────────────────────
_orig_post = httpx.post
def _timeout_post(*a, **kw):
    kw['timeout'] = httpx.Timeout(600.0, connect=60.0)
    return _orig_post(*a, **kw)
httpx.post = _timeout_post

zot = zotero.Zotero(LIBRARY_ID, 'user', API_KEY)
zot.client = httpx.Client(
    timeout=httpx.Timeout(600.0, connect=60.0),
    headers=dict(zot.client.headers),
)

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ── PDF helpers ───────────────────────────────────────────────────────────────

def local_pdf_path(att: dict) -> Path | None:
    """Return local Zotero storage path for an attachment, or None if absent."""
    filename = att['data'].get('filename', '')
    if not filename:
        return None
    path = ZOTERO_STORAGE / att['key'] / filename
    return path if path.exists() else None


def read_pdf_text(path: Path) -> str:
    """Extract text from first PDF_MAX_PAGES pages. Returns '' on failure."""
    try:
        doc = fitz.open(str(path))
        text = ''.join(doc[i].get_text() for i in range(min(PDF_MAX_PAGES, len(doc))))
        doc.close()
        return text[:PDF_MAX_CHARS].strip()
    except Exception:
        return ''


def get_item_pdfs(item_key: str) -> tuple[list[dict], list[str]]:
    """Return (pdf_attachments, extracted_texts) for an item."""
    children = zot.children(item_key)
    pdfs = [c for c in children
            if c['data'].get('itemType') == 'attachment'
            and c['data'].get('contentType') == 'application/pdf']
    texts = [read_pdf_text(p) if (p := local_pdf_path(att)) else '' for att in pdfs]
    return pdfs, texts

# ── DeepSeek classification ───────────────────────────────────────────────────

def classify_pdf_type(text: str) -> str:
    """
    Classify a single PDF as 'review', 'si', 'main', or 'unknown'.
    Sends first PDF_MAX_PAGES pages of text to DeepSeek.
    """
    if not text.strip():
        return 'unknown'
    prompt = (
        "以下是一篇学术文献的前3页内容。请判断它属于哪种类型：\n"
        "(A) 综述文章（review article）- 系统回顾某领域研究进展，引用大量文献\n"
        "(B) 支撑信息（supporting information / supplementary materials）- 附加数据、方法细节\n"
        "(C) 研究论文正文（research article）- 报告原创实验结果和发现\n\n"
        f"文献内容（前3页）：\n{text}\n\n"
        "只回答字母 A、B 或 C，不要解释。"
    )
    try:
        resp = deepseek.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=5,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().upper()
        if 'A' in answer: return 'review'
        if 'B' in answer: return 'si'
        if 'C' in answer: return 'main'
        return 'unknown'
    except Exception as e:
        print(f'    ⚠️  DeepSeek classify error: {e}')
        return 'unknown'


def is_duplicate_set(texts: list[str]) -> bool:
    """
    Return True if 2+ PDFs are the same article (preprint+published, double download).
    Return False if they are distinct documents (main paper + SI, different articles).

    Conservative: returns False when texts are too sparse to judge.
    """
    if len(texts) < 2:
        return False
    # If fewer than 2 PDFs have extractable text, cannot determine → treat as non-duplicate
    non_empty = [t for t in texts if t.strip()]
    if len(non_empty) < 2:
        print('    ℹ️  可读PDF不足2个，默认非重复')
        return False
    n = len(non_empty)
    parts = []
    for i, text in enumerate(non_empty, 1):
        snippet = text[:PDF_MAX_CHARS // n]
        parts.append(f"=== PDF {i} ===\n{snippet}")
    prompt = (
        f"以下是同一 Zotero 条目中 {n} 个 PDF 文件的前3页内容。\n\n"
        "任务：判断这些PDF是否为【同一篇文章的重复副本】。\n\n"
        "【YES - 是重复】严格定义：两个PDF包含几乎相同的正文内容\n"
        "  ✓ 同一文章被下载了两次（内容完全相同）\n"
        "  ✓ 预印本版本 + 正式发表版本（标题/作者相同，正文高度相似）\n\n"
        "【NO - 不是重复】以下情况均回答NO：\n"
        "  ✓ 研究论文正文 + 支撑信息/附录（即使来自同一篇论文）\n"
        "  ✓ 两篇不同的文章\n"
        "  ✓ 正文 + 图表数据文件\n"
        "  ✓ 内容长度或格式差异明显\n\n"
        "⚠️ 判断原则：如果不确定，请回答 NO。只有在非常确定是同一文章重复下载时才回答 YES。\n\n"
        + '\n\n'.join(parts) + "\n\n"
        "只回答 YES 或 NO，不要解释。"
    )
    try:
        resp = deepseek.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=5,
            temperature=0,
        )
        return 'YES' in resp.choices[0].message.content.strip().upper()
    except Exception as e:
        print(f'    ⚠️  DeepSeek duplicate error: {e}')
        return False

# ── Publisher detection ───────────────────────────────────────────────────────

def detect_publisher(item: dict) -> str:
    doi = item['data'].get('DOI', '').lower()
    pub = item['data'].get('publisher', '').lower()
    if doi.startswith('10.1016/') or doi.startswith('10.1053/') or 'elsevier' in pub:
        return 'elsevier'
    if doi.startswith('10.1039/') or 'royal' in pub or 'rsc' in pub:
        return 'rsc'
    if doi.startswith('10.1021/') or 'american chemical' in pub:
        return 'acs'
    if doi.startswith('10.1038/') or doi.startswith('10.1007/') or 'springer' in pub or 'nature' in pub:
        return 'springer'
    if doi.startswith('10.1088/') or doi.startswith('10.1149/') or 'iop' in pub:
        return 'iop'
    if 'wiley' in pub or doi.startswith('10.1002/'):
        return 'wiley'
    return 'unknown'

# ── File download ─────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path) -> tuple[bool, float]:
    """Download url to dest. Returns (success, size_mb). Deletes dest on failure."""
    try:
        r = requests.get(url, timeout=120, stream=True, headers=BROWSER_HEADERS)
        if r.status_code != 200:
            return False, 0.0
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        size_mb = dest.stat().st_size / 1024 / 1024
        with open(dest, 'rb') as f:
            magic = f.read(8)
        if magic[:5].lower() in (b'<html', b'<!doc', b'<?xml'):
            dest.unlink()
            return False, 0.0
        return True, size_mb
    except Exception:
        if dest.exists():
            dest.unlink()
        return False, 0.0


def docx_to_pdf(docx_path: Path) -> Path | None:
    """Convert docx/doc to PDF via win32com. Returns pdf path or None on failure."""
    import win32com.client
    pdf_path  = docx_path.with_suffix('.pdf')
    open_path = docx_path
    if docx_path.suffix.lower() == '.docx':
        with open(docx_path, 'rb') as f:
            if f.read(4) == OLE_MAGIC:
                open_path = docx_path.with_suffix('.doc')
                docx_path.rename(open_path)
    word = None
    try:
        word = win32com.client.Dispatch('Word.Application')
        word.Visible = False
        doc = word.Documents.Open(str(open_path.resolve()))
        doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)
        doc.Close()
        return pdf_path
    except Exception as e:
        print(f'    DOCX→PDF failed: {e}')
        return None
    finally:
        if word:
            try: word.Quit()
            except: pass


def upload_to_zotero(files: list[Path], item_key: str) -> int:
    """Upload files as attachments to item_key. Returns number of successes."""
    n_uploaded = 0
    for path in files:
        try:
            result = zot.attachment_simple([str(path)], parentid=item_key)
            if result.get('success') or result.get('unchanged'):
                label = 'unchanged' if result.get('unchanged') else 'uploaded'
                print(f'    ✓ {label}: {path.name}')
                n_uploaded += 1
            else:
                print(f'    ✗ upload failed: {path.name} | {result}')
        except Exception as e:
            print(f'    ✗ upload error ({path.name}): {str(e)[:80]}')
    return n_uploaded

# ── SI download ───────────────────────────────────────────────────────────────

def has_si(item_key: str) -> bool:
    """Return True if item already has an SI attachment."""
    try:
        for c in zot.children(item_key):
            if c['data'].get('itemType') != 'attachment':
                continue
            name = (c['data'].get('title', '') + c['data'].get('filename', '')).lower()
            if any(kw in name for kw in SI_KEYWORDS):
                return True
    except Exception:
        pass
    return False


def get_elsevier_pii(item: dict) -> str | None:
    """Resolve Elsevier PII from item URL, Elsevier API, or DOI redirect."""
    doi = item['data'].get('DOI', '')
    m = PII_RE.search(item['data'].get('url', ''))
    if m:
        return m.group(1)
    if not doi:
        return None
    try:
        r = requests.get(
            f'https://api.elsevier.com/content/article/doi/{doi}',
            headers={'X-ELS-APIKey': ELSEVIER_API_KEY, 'Accept': 'application/json'},
            timeout=20,
        )
        if r.status_code == 200:
            raw = (r.json().get('full-text-retrieval-response', {})
                           .get('coredata', {}).get('pii', ''))
            if raw:
                return re.sub(r'[-()]', '', raw)
    except Exception:
        pass
    try:
        r2 = requests.get(f'https://doi.org/{doi}', timeout=20,
                          allow_redirects=True, headers=BROWSER_HEADERS)
        m2 = PII_RE.search(r2.url)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return None


def find_elsevier_si(pii: str, item_key: str) -> list[tuple[str, str, str]]:
    """Probe Elsevier CDN for mmc1..MAX_MMC in pdf/docx. Returns (url, fname, ext)."""
    hits = []
    for n in range(1, MAX_MMC + 1):
        found = False
        for ext in ('pdf', 'docx'):
            url = f'https://ars.els-cdn.com/content/image/1-s2.0-{pii}-mmc{n}.{ext}'
            try:
                rh = requests.head(url, timeout=10, headers=BROWSER_HEADERS)
                ct = rh.headers.get('Content-Type', '')
                if rh.status_code == 200 and 'xml' not in ct and 'html' not in ct:
                    hits.append((url, f'{item_key}_mmc{n}.{ext}', ext))
                    found = True
            except Exception:
                pass
        if not found and n > 1:
            break
    return hits


def find_rsc_si(doi: str) -> list[tuple[str, str]]:
    """Scrape RSC article page for suppdata links. Returns (url, filename)."""
    if '10.1039/' not in doi:
        return []
    paper_id = doi.split('10.1039/')[-1].lower()
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=BROWSER_HEADERS)
        links = re.findall(
            r'href="(https://www\.rsc\.org/suppdata/[^"]+\.(pdf|docx))"', r.text, re.I)
        if links:
            return [(url, url.split('/')[-1]) for url, _ in links]
    except Exception:
        pass
    m = re.match(r'([a-z])(\d)([a-z]+)\d', paper_id)
    if m:
        base = f'https://www.rsc.org/suppdata/{m.group(3)}/{m.group(1)}{m.group(2)}/{paper_id}'
        return [
            (f'{base}/{paper_id}1.pdf', f'{paper_id}_si1.pdf'),
            (f'{base}/{paper_id}2.pdf', f'{paper_id}_si2.pdf'),
        ]
    return []


def find_acs_si(doi: str) -> list[dict]:
    """Query ACS figshare API for SI files. Returns list of file dicts."""
    url = ('https://widgets.figshare.com/public/files'
           f'?institution=acs&limit=21&offset=0'
           f'&collectionResourceDOI={urllib.parse.quote(doi, safe="")}')
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            seen, unique = set(), []
            for f in r.json().get('files', []):
                if f['name'] not in seen:
                    seen.add(f['name'])
                    unique.append(f)
            return unique
    except Exception as e:
        print(f'    figshare error: {e}')
    return []


def find_springer_si(doi: str) -> list[tuple[str, str]]:
    """Scrape Springer/Nature article page for ESM PDF links. Returns (url, filename)."""
    results, seen = [], set()
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=BROWSER_HEADERS)
        links = re.findall(
            r'"(https://static-content\.springer\.com/esm/[^"]+\.pdf[^"]*)"', r.text)
        links += re.findall(
            r'"(https://media\.springernature\.com/[^"]+\.pdf[^"]*)"', r.text)
        for link in links:
            if link not in seen:
                seen.add(link)
                fname = re.sub(r'[?#].*', '', link).split('/')[-1]
                if not fname.endswith('.pdf'):
                    fname += '.pdf'
                results.append((link, fname))
    except Exception as e:
        print(f'  Springer scrape error: {e}')
    return results


def fetch_si(item: dict) -> bool:
    """Find, download, and upload SI for a main paper. Returns True if SI uploaded."""
    key = item['key']
    doi = item['data'].get('DOI', '')

    if not doi:
        print('    SI: 跳过 (无DOI)')
        return False
    if has_si(key):
        print('    SI: 已有 SI 附件，跳过下载')
        return True

    publisher = detect_publisher(item)
    print(f'    SI: 查找中 (publisher={publisher}, doi={doi[:40]})')

    files: list[Path] = []

    if publisher == 'elsevier':
        pii = get_elsevier_pii(item)
        if not pii:
            print('    SI: 无法获取 PII')
            return False
        hits = find_elsevier_si(pii, key)
        if not hits:
            print('    SI: mmc CDN 无文件')
            return False
        for url, fname, ext in hits:
            dest = SI_DIR / fname
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(url, dest)
                if not ok: continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('docx', 'doc') else dest)

    elif publisher == 'rsc':
        for url, fname in find_rsc_si(doi):
            ext = Path(fname).suffix.lower()
            if ext not in ALLOWED_EXT: continue
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(url, dest)
                if not ok: continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('.docx', '.doc') else dest)

    elif publisher == 'acs':
        for fi in find_acs_si(doi):
            ext = Path(fi['name']).suffix.lower()
            if ext not in ALLOWED_EXT: continue
            dest = SI_DIR / f'{key}_{fi["name"]}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(fi['downloadUrl'], dest)
                if not ok: continue
                print(f'    SI: 下载 {fi["name"]} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('.docx', '.doc') else dest)

    elif publisher == 'springer':
        for url, fname in find_springer_si(doi):
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(url, dest)
                if not ok:
                    with open(BLOCKED_FILE, 'a') as bf:
                        bf.write(f'{doi}\tspringer\t{url}\n')
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(dest)

    else:
        print(f'    SI: publisher "{publisher}" 未支持，记录到 blocked')
        with open(BLOCKED_FILE, 'a') as bf:
            bf.write(f'{doi}\t{publisher}\thttps://doi.org/{doi}\n')
        return False

    return upload_to_zotero(files, key) > 0 if files else False

# ── Collection helpers ────────────────────────────────────────────────────────

def move_item(key: str, src: str, dst: str) -> bool:
    """Move item from src to dst collection. Re-fetches version to avoid conflicts."""
    try:
        fresh = zot.item(key)
        cols = fresh['data'].get('collections', [])
        zot.update_item({
            'key': key,
            'version': fresh['version'],
            'collections': list(set(cols + [dst]) - {src}),
        })
        return True
    except Exception as e:
        print(f'    ❌ 移动失败: {e}')
        return False


def fetch_bib_items(col_key: str) -> list[dict]:
    """Fetch all bibliography items (excluding notes and attachments) from a collection."""
    raw = zot.everything(zot.collection_items(col_key, itemType='-attachment'))
    return [i for i in raw if i['data'].get('itemType') != 'note']

# ── Per-item routing ──────────────────────────────────────────────────────────

def route_item(item: dict, idx: int, total: int) -> str:
    """Route one item from 01_SHORTTERMS to the correct inbox. Returns dest name."""
    key   = item['key']
    title = re.sub(r'<[^>]+>', '', item['data'].get('title', '(无标题)'))[:55]
    year  = item['data'].get('date', '')[:4]
    tags  = {t['tag'] for t in item['data'].get('tags', [])}

    print(f'\n[{idx:04d}/{total}] [{key}] ({year}) {title}')
    print(f'  tags: {", ".join(sorted(tags)) or "(无)"}')

    # Rule 1: no AI分析 tag → AA
    if 'AI分析' not in tags:
        print('  → 无 AI分析 tag')
        ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
        dest = '00_INBOXS_AA' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {dest}')
        return dest

    pdfs, texts = get_item_pdfs(key)
    n_pdfs = len(pdfs)
    print(f'  PDFs: {n_pdfs}')

    # Rule 2: AI分析 + 0 PDFs → AA
    if n_pdfs == 0:
        print('  → 有 AI分析 但无 PDF')
        ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
        dest = '00_INBOXS_AA' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {dest}')
        return dest

    # Rule 3: AI分析 + 1 PDF → classify type
    if n_pdfs == 1:
        pdf_text = texts[0]
        if pdf_text:
            print(f'  PDF文本: {len(pdf_text)} 字符 (前3页)')
        else:
            fname = pdfs[0]['data'].get('filename', '?')
            print(f'  ⚠️  无法提取PDF文本: {fname}')

        print('  🤖 DeepSeek 分类中...')
        pdf_type = classify_pdf_type(pdf_text)
        print(f'  → 类型: {pdf_type}')

        if pdf_type == 'review':
            ok = move_item(key, SHORTTERMS_KEY, BB_KEY)
            dest = '00_INBOXS_BB' if ok else 'move_failed'
            print(f'  {"✅" if ok else "❌"} {dest} (综述)')
            return dest

        if pdf_type == 'si':
            ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
            dest = '00_INBOXS_AA' if ok else 'move_failed'
            print(f'  {"✅" if ok else "❌"} {dest} (支撑信息)')
            return dest

        # main or unknown: attempt SI download, then → AA
        si_ok = fetch_si(item)
        print('  → SI 已补充' if si_ok else '  → SI 未找到 (正常，继续移动)')
        ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
        dest = '00_INBOXS_AA' if ok else 'move_failed'
        label = '正文' if pdf_type == 'main' else '未知类型'
        print(f'  {"✅" if ok else "❌"} {dest} ({label})')
        return dest

    # Rule 4: AI分析 + 2+ PDFs → duplicate check
    print(f'  🤖 DeepSeek 重复检测中... ({n_pdfs} 个PDF)')
    is_dup = is_duplicate_set(texts)
    print(f'  → 有重复: {is_dup}')

    if is_dup:
        ok = move_item(key, SHORTTERMS_KEY, DD_KEY)
        dest = '00_INBOXS_DD' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {dest} (有重复PDF)')
    else:
        ok = move_item(key, SHORTTERMS_KEY, CC_KEY)
        dest = '00_INBOXS_CC' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {dest} (正文+SI)')
    return dest

# ── Main routines ─────────────────────────────────────────────────────────────

def _print_summary(stats: Counter) -> None:
    print('\n' + '=' * 70)
    print('完成！结果汇总：')
    for k, v in sorted(stats.items()):
        print(f'  {k:20s}: {v} 条')


def route_shortterms() -> None:
    """Route all bibliography items from 01_SHORTTERMS to the correct inbox."""
    print('=' * 70)
    print('  01_SHORTTERMS 分类处理')
    print('=' * 70)
    items = fetch_bib_items(SHORTTERMS_KEY)
    print(f'共 {len(items)} 个条目\n')
    stats: Counter = Counter()
    for idx, item in enumerate(items, 1):
        stats[route_item(item, idx, len(items))] += 1
        time.sleep(0.3)
    _print_summary(stats)


def recheck_dd_cc() -> None:
    """
    Re-check duplicate detection for items in DD and CC.
      DD items not truly duplicate → move to CC
      CC items truly duplicate     → move to DD
    """
    print('=' * 70)
    print('  重新检测 DD / CC 重复状态')
    print('=' * 70)
    stats: Counter = Counter()

    for col_key, col_name, should_be_dup in [
        (DD_KEY, '00_INBOXS_DD', True),
        (CC_KEY, '00_INBOXS_CC', False),
    ]:
        items = fetch_bib_items(col_key)
        print(f'\n{col_name}: {len(items)} 个条目\n')

        for idx, item in enumerate(items, 1):
            key   = item['key']
            title = re.sub(r'<[^>]+>', '', item['data'].get('title', '(无标题)'))[:55]
            year  = item['data'].get('date', '')[:4]
            print(f'\n[{idx:04d}/{len(items)}] [{key}] ({year}) {title}')

            pdfs, texts = get_item_pdfs(key)
            n_pdfs = len(pdfs)
            print(f'  PDFs: {n_pdfs}')

            if n_pdfs < 2:
                print(f'  ⚠️  PDF数量 < 2，跳过')
                stats['skip'] += 1
                time.sleep(0.1)
                continue

            print(f'  🤖 DeepSeek 重复检测中... ({n_pdfs} 个PDF)')
            is_dup = is_duplicate_set(texts)
            print(f'  → 有重复: {is_dup}')

            if should_be_dup and not is_dup:
                ok = move_item(key, col_key, CC_KEY)
                stats['DD→CC'] += 1
                print(f'  {"✅" if ok else "❌"} 移到 00_INBOXS_CC (正文+SI)')
            elif not should_be_dup and is_dup:
                ok = move_item(key, col_key, DD_KEY)
                stats['CC→DD'] += 1
                print(f'  {"✅" if ok else "❌"} 移到 00_INBOXS_DD (真重复)')
            else:
                stats['stay'] += 1
                print(f'  ✓ 保留在 {col_name}')

            time.sleep(0.3)

    _print_summary(stats)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'recheck':
        recheck_dd_cc()
    else:
        route_shortterms()
