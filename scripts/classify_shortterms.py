"""
classify_shortterms.py
======================
Process all items in 01_SHORTTERMS one by one and route to correct inbox:

  No AI分析 tag                     → 00_INBOXS_AA
  AI分析 + 0 PDFs                   → 00_INBOXS_AA
  AI分析 + 1 PDF (review)           → 00_INBOXS_BB
  AI分析 + 1 PDF (SI)               → 00_INBOXS_AA
  AI分析 + 1 PDF (main paper)       → find SI, then 00_INBOXS_AA
  AI分析 + 2+ PDFs (no duplicates)  → 00_INBOXS_CC
  AI分析 + 2+ PDFs (has duplicates) → 00_INBOXS_DD

Run:
    uv run python scripts/classify_shortterms.py
"""
from collections import Counter
from pathlib import Path
import re
import time
import urllib.parse

import fitz  # PyMuPDF
import httpx
from openai import OpenAI
import pyzotero.zotero as zotero
import requests

# ── Config ────────────────────────────────────────────────────────────────────
LIBRARY_ID        = '5452188'
API_KEY           = '***ZOTERO_API_KEY***'
DEEPSEEK_API_KEY  = '***DEEPSEEK_API_KEY***'
DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
ELSEVIER_API_KEY  = '***ELSEVIER_API_KEY***'

SHORTTERMS_KEY = '478IFSJ3'  # 01_SHORTTERMS (source)
AA_KEY         = '2PSBFJEI'  # 00_INBOXS_AA
BB_KEY         = '866TNWZ9'  # 00_INBOXS_BB
CC_KEY         = 'H7KTSUR7'  # 00_INBOXS_CC
DD_KEY         = 'UQDFUUYV'  # 00_INBOXS_DD

ZOTERO_STORAGE = Path('C:/Users/chengliu/Zotero/storage')
SI_DIR         = Path('F:/ICMAB-Data/UAB-Thesis/zotero-mcp/.si-downloads/shortterms')
BLOCKED_FILE   = Path('F:/ICMAB-Data/UAB-Thesis/zotero-mcp/.si-downloads/shortterms_blocked.txt')
SI_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {'.pdf', '.docx', '.doc'}
MAX_MMC     = 8
PDF_MAX_CHARS = 2000   # chars to send to DeepSeek per PDF
PDF_MAX_PAGES = 3

HEADERS_BROWSER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}
PII_RE = re.compile(r'pii[/=](S\w+)', re.I)
SI_KEYWORDS = ['supporting', 'suppl', '_si_', '_si.', 'si_00', 'supp_', 'mmc', 'suppdata']

# ── Zotero client (dual-patch for large uploads) ──────────────────────────────
_orig_post = httpx.post
def _patched_post(*a, **kw):
    kw['timeout'] = httpx.Timeout(600.0, connect=60.0)
    return _orig_post(*a, **kw)
httpx.post = _patched_post

zot = zotero.Zotero(LIBRARY_ID, 'user', API_KEY)
zot.client = httpx.Client(
    timeout=httpx.Timeout(600.0, connect=60.0),
    headers=dict(zot.client.headers),
)

deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# ── PDF text extraction ───────────────────────────────────────────────────────

def get_local_pdf_path(att: dict) -> Path | None:
    """Return local Zotero storage path for an attachment, or None if not found."""
    att_key = att['key']
    filename = att['data'].get('filename', '')
    if not filename:
        return None
    path = ZOTERO_STORAGE / att_key / filename
    return path if path.exists() else None


def extract_pdf_text(path: Path, max_pages: int = PDF_MAX_PAGES, max_chars: int = PDF_MAX_CHARS) -> str:
    """Extract text from first N pages of a PDF. Returns empty string on failure."""
    try:
        doc = fitz.open(str(path))
        pages_to_read = min(max_pages, len(doc))
        text = ''
        for page_num in range(pages_to_read):
            text += doc[page_num].get_text()
        doc.close()
        return text[:max_chars].strip()
    except Exception:
        return ''

# ── DeepSeek classification ───────────────────────────────────────────────────

def classify_single_pdf(text: str) -> str:
    """
    Classify PDF content as 'review', 'si', or 'main'.
    Returns: 'review' | 'si' | 'main' | 'unknown'
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
        if 'A' in answer:
            return 'review'
        elif 'B' in answer:
            return 'si'
        elif 'C' in answer:
            return 'main'
        return 'unknown'
    except Exception as e:
        print(f'    ⚠️  DeepSeek classify error: {e}')
        return 'unknown'


def check_duplicates(texts: list[str]) -> bool:
    """
    Check if 2+ PDFs are duplicates (same article, same version downloaded twice).
    Returns True ONLY if two PDFs are the same article in different format/version.
    Returns False if PDFs are complementary (e.g. main paper + supporting info).
    """
    if len(texts) < 2:
        return False
    # Build combined prompt with all PDF snippets
    parts = []
    for i, text in enumerate(texts, 1):
        snippet = text[:PDF_MAX_CHARS // len(texts)] if text else '（无法提取文本）'
        parts.append(f"=== PDF {i} ===\n{snippet}")
    combined = '\n\n'.join(parts)
    n = len(texts)
    prompt = (
        f"以下是同一 Zotero 条目中 {n} 个 PDF 文件的前3页内容。\n\n"
        "请严格按以下标准判断：\n"
        "【YES - 重复】：两个或以上 PDF 是【同一篇文章的不同版本或格式】\n"
        "  例如：预印本 + 正式发表版、同一文章被下载了两次、英文版 + 中文版\n"
        "【NO - 非重复】：这些 PDF 是【不同文档的组合】\n"
        "  例如：研究论文正文 + 支撑信息(Supporting Information/Supplementary)\n"
        "  例如：两篇完全不同主题的文章\n\n"
        "⚠️ 特别注意：即使「正文」和「支撑信息」来自同一篇论文，\n"
        "  它们是完全不同的文档（内容、格式均不同），应回答 NO。\n\n"
        f"{combined}\n\n"
        "只回答 YES 或 NO，不要解释。"
    )
    try:
        resp = deepseek.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=5,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().upper()
        return 'YES' in answer
    except Exception as e:
        print(f'    ⚠️  DeepSeek duplicates error: {e}')
        return False

# ── Publisher detection ───────────────────────────────────────────────────────

def detect_publisher(item: dict) -> str:
    d = item['data']
    doi = d.get('DOI', '').lower()
    pub = d.get('publisher', '').lower()
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


# ── Download + verify ─────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, headers=None) -> tuple[bool, float]:
    h = headers or HEADERS_BROWSER
    try:
        r = requests.get(url, timeout=120, stream=True, headers=h)
        if r.status_code != 200:
            return False, 0.0
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        size_mb = dest.stat().st_size / 1024 / 1024
        with open(dest, 'rb') as f:
            header = f.read(8)
        if header[:5].lower() in (b'<html', b'<!doc', b'<?xml'):
            dest.unlink()
            return False, 0.0
        return True, size_mb
    except Exception:
        if dest.exists():
            dest.unlink()
        return False, 0.0


# ── DOCX → PDF (win32com only) ────────────────────────────────────────────────

OLE_MAGIC = b'\xd0\xcf\x11\xe0'

def docx_to_pdf(docx_path: Path) -> Path | None:
    import win32com.client
    pdf_path = docx_path.with_suffix('.pdf')
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


# ── Zotero upload ─────────────────────────────────────────────────────────────

def upload_files(filepaths: list[Path], item_key: str) -> int:
    success = 0
    for fpath in filepaths:
        try:
            result = zot.attachment_simple([str(fpath)], parentid=item_key)
            if result.get('success') or result.get('unchanged'):
                label = 'unchanged' if result.get('unchanged') else 'uploaded'
                print(f'    ✓ {label}: {fpath.name}')
                success += 1
            else:
                print(f'    ✗ upload failed: {fpath.name} | {result}')
        except Exception as e:
            print(f'    ✗ upload error ({fpath.name}): {str(e)[:80]}')
    return success


# ── Has SI already? ───────────────────────────────────────────────────────────

def has_si_attachment(item_key: str) -> bool:
    try:
        for c in zot.children(item_key):
            if c['data'].get('itemType') != 'attachment':
                continue
            combined = (c['data'].get('title', '') + c['data'].get('filename', '')).lower()
            if any(kw in combined for kw in SI_KEYWORDS):
                return True
    except Exception:
        pass
    return False


# ── ELSEVIER: PII resolution + mmc probing ───────────────────────────────────

def get_pii(item: dict) -> str | None:
    d = item['data']
    url = d.get('url', '')
    doi = d.get('DOI', '')
    m = PII_RE.search(url)
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
            pii_raw = (r.json()
                       .get('full-text-retrieval-response', {})
                       .get('coredata', {}).get('pii', ''))
            if pii_raw:
                return re.sub(r'[-()]', '', pii_raw)
    except Exception:
        pass
    try:
        r2 = requests.get(f'https://doi.org/{doi}', timeout=20,
                          allow_redirects=True, headers=HEADERS_BROWSER)
        m2 = PII_RE.search(r2.url)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return None


def find_elsevier_si(pii: str, item_key: str) -> list[tuple[str, str, str]]:
    hits = []
    for n in range(1, MAX_MMC + 1):
        found_any = False
        for ext in ('pdf', 'docx'):
            url = f'https://ars.els-cdn.com/content/image/1-s2.0-{pii}-mmc{n}.{ext}'
            try:
                rh = requests.head(url, timeout=10, headers=HEADERS_BROWSER)
                if rh.status_code == 200:
                    ct = rh.headers.get('Content-Type', '')
                    if 'xml' not in ct and 'html' not in ct:
                        hits.append((url, f'{item_key}_mmc{n}.{ext}', ext))
                        found_any = True
            except Exception:
                pass
        if not found_any and n > 1:
            break
    return hits


# ── RSC ───────────────────────────────────────────────────────────────────────

def find_rsc_si(doi: str) -> list[tuple[str, str]]:
    if '10.1039/' not in doi:
        return []
    paper_id = doi.split('10.1039/')[-1].lower()
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=HEADERS_BROWSER)
        links = re.findall(
            r'href="(https://www\.rsc\.org/suppdata/[^"]+\.(pdf|docx))"',
            r.text, re.I)
        if links:
            return [(url, url.split('/')[-1]) for url, _ in links]
    except Exception:
        pass
    m = re.match(r'([a-z])(\d)([a-z]+)\d', paper_id)
    if m:
        year_code = m.group(1) + m.group(2)
        journal   = m.group(3)
        base = f'https://www.rsc.org/suppdata/{journal}/{year_code}/{paper_id}'
        return [
            (f'{base}/{paper_id}1.pdf', f'{paper_id}_si1.pdf'),
            (f'{base}/{paper_id}2.pdf', f'{paper_id}_si2.pdf'),
        ]
    return []


# ── ACS ───────────────────────────────────────────────────────────────────────

def find_acs_si(doi: str) -> list[dict]:
    encoded = urllib.parse.quote(doi, safe='')
    url = (f'https://widgets.figshare.com/public/files'
           f'?institution=acs&limit=21&offset=0&collectionResourceDOI={encoded}')
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            files = r.json().get('files', [])
            seen, deduped = set(), []
            for f in files:
                if f['name'] not in seen:
                    seen.add(f['name'])
                    deduped.append(f)
            return deduped
    except Exception as e:
        print(f'    figshare error: {e}')
    return []


# ── Springer/Nature ───────────────────────────────────────────────────────────

def find_springer_si(doi: str) -> list[tuple[str, str]]:
    results = []
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=HEADERS_BROWSER)
        final_url = r.url
        nature_links = re.findall(
            r'"(https://static-content\.springer\.com/esm/[^"]+\.pdf[^"]*)"', r.text)
        nature_links += re.findall(
            r'"(https://media\.springernature\.com/[^"]+\.pdf[^"]*)"', r.text)
        seen = set()
        for link in nature_links:
            if link not in seen:
                seen.add(link)
                fname = re.sub(r'[?#].*', '', link).split('/')[-1]
                if not fname.endswith('.pdf'):
                    fname += '.pdf'
                results.append((link, fname))
    except Exception as e:
        print(f'  Springer scrape error: {e}')
    return results

# ── Move item between collections ─────────────────────────────────────────────

def move_item(key: str, from_col: str, to_col: str) -> bool:
    try:
        fresh = zot.item(key)
        cols = fresh['data'].get('collections', [])
        new_cols = list(set(cols + [to_col]) - {from_col})
        zot.update_item({
            'key': key,
            'version': fresh['version'],
            'collections': new_cols,
        })
        return True
    except Exception as e:
        print(f'    ❌ 移动失败: {e}')
        return False


# ── SI download orchestrator ──────────────────────────────────────────────────

def try_download_si(item: dict) -> bool:
    """Try to find and download SI for a main paper. Returns True if SI was found and uploaded."""
    key = item['key']
    doi = item['data'].get('DOI', '')

    if not doi:
        print('    SI: 跳过 (无DOI)')
        return False

    if has_si_attachment(key):
        print('    SI: 已有 SI 附件，跳过下载')
        return True

    publisher = detect_publisher(item)
    print(f'    SI: 查找中 (publisher={publisher}, doi={doi[:40]})')

    to_upload: list[Path] = []

    if publisher == 'elsevier':
        pii = get_pii(item)
        if not pii:
            print('    SI: 无法获取 PII')
            return False
        hits = find_elsevier_si(pii, key)
        if not hits:
            print('    SI: mmc CDN 无文件')
            return False
        for url, fname, ext in hits:
            dest = SI_DIR / fname
            if dest.exists() and dest.stat().st_size > 500:
                pass  # cached
            else:
                ok, sz = download_file(url, dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            if ext in ('docx', 'doc'):
                converted = docx_to_pdf(dest)
                to_upload.append(converted if converted else dest)
            else:
                to_upload.append(dest)

    elif publisher == 'rsc':
        hits = find_rsc_si(doi)
        for url, fname in hits:
            ext = Path(fname).suffix.lower()
            if ext not in ALLOWED_EXT:
                continue
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(url, dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            if ext in ('.docx', '.doc'):
                converted = docx_to_pdf(dest)
                to_upload.append(converted if converted else dest)
            else:
                to_upload.append(dest)

    elif publisher == 'acs':
        files = find_acs_si(doi)
        for fi in files:
            fname = fi['name']
            suffix = Path(fname).suffix.lower()
            if suffix not in ALLOWED_EXT:
                continue
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(fi['downloadUrl'], dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            if suffix in ('.docx', '.doc'):
                converted = docx_to_pdf(dest)
                to_upload.append(converted if converted else dest)
            else:
                to_upload.append(dest)

    elif publisher == 'springer':
        hits = find_springer_si(doi)
        for url, fname in hits:
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download_file(url, dest)
                if not ok:
                    with open(BLOCKED_FILE, 'a') as bf:
                        bf.write(f'{doi}\tspringer\t{url}\n')
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            to_upload.append(dest)

    else:
        print(f'    SI: publisher "{publisher}" 未支持，记录到 blocked')
        with open(BLOCKED_FILE, 'a') as bf:
            bf.write(f'{doi}\t{publisher}\thttps://doi.org/{doi}\n')
        return False

    if not to_upload:
        return False

    n_ok = upload_files(to_upload, key)
    return n_ok > 0

# ── Per-item processing ───────────────────────────────────────────────────────

def process_item(item: dict, idx: int, total: int) -> str:
    """
    Process one item and route it to the correct collection.
    Returns destination name string.
    """
    key   = item['key']
    data  = item['data']
    title = re.sub(r'<[^>]+>', '', data.get('title', '(无标题)'))[:55]
    year  = data.get('date', '')[:4]
    tags  = {t['tag'] for t in data.get('tags', [])}

    prefix = f'[{idx:04d}/{total}]'
    print(f'\n{prefix} [{key}] ({year}) {title}')
    print(f'  tags: {", ".join(sorted(tags)) or "(无)"}')

    # ── Rule 1: No AI分析 tag → AA ────────────────────────────────────────────
    if 'AI分析' not in tags:
        print('  → 无 AI分析 tag')
        ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
        result = '00_INBOXS_AA' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {result}')
        return result

    # ── Get PDF attachments ────────────────────────────────────────────────────
    children = zot.children(key)
    pdfs = [c for c in children
            if c['data'].get('itemType') == 'attachment'
            and c['data'].get('contentType') == 'application/pdf']
    pdf_count = len(pdfs)
    print(f'  PDFs: {pdf_count}')

    # ── Rule 2: AI分析 + 0 PDFs → AA ─────────────────────────────────────────
    if pdf_count == 0:
        print('  → 有 AI分析 但无 PDF')
        ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
        result = '00_INBOXS_AA' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {result}')
        return result

    # ── Rule 3: AI分析 + 1 PDF → classify ────────────────────────────────────
    if pdf_count == 1:
        pdf = pdfs[0]
        local_path = get_local_pdf_path(pdf)
        text = ''
        if local_path:
            text = extract_pdf_text(local_path)
            if text:
                print(f'  PDF文本: {len(text)} 字符 (前3页)')
            else:
                print(f'  ⚠️  无法提取PDF文本: {local_path.name}')
        else:
            print(f'  ⚠️  本地文件未找到: {pdf["data"].get("filename", "?")}')

        print('  🤖 DeepSeek 分类中...')
        pdf_type = classify_single_pdf(text) if text else 'unknown'
        print(f'  → 类型: {pdf_type}')

        if pdf_type == 'review':
            ok = move_item(key, SHORTTERMS_KEY, BB_KEY)
            result = '00_INBOXS_BB' if ok else 'move_failed'
            print(f'  {"✅" if ok else "❌"} {result} (综述)')
            return result

        elif pdf_type == 'si':
            ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
            result = '00_INBOXS_AA' if ok else 'move_failed'
            print(f'  {"✅" if ok else "❌"} {result} (支撑信息)')
            return result

        else:  # 'main' or 'unknown'
            # Try to find SI
            si_found = try_download_si(item)
            if si_found:
                print('  → SI 已补充')
            else:
                print('  → SI 未找到 (正常，继续移动)')
            ok = move_item(key, SHORTTERMS_KEY, AA_KEY)
            result = '00_INBOXS_AA' if ok else 'move_failed'
            label = '正文' if pdf_type == 'main' else '未知类型'
            print(f'  {"✅" if ok else "❌"} {result} ({label})')
            return result

    # ── Rule 4: AI分析 + 2+ PDFs → duplicate check ───────────────────────────
    texts = []
    for pdf in pdfs:
        local_path = get_local_pdf_path(pdf)
        if local_path:
            texts.append(extract_pdf_text(local_path))
        else:
            texts.append('')

    print(f'  🤖 DeepSeek 重复检测中... ({pdf_count} 个PDF)')
    has_dups = check_duplicates(texts)
    print(f'  → 有重复: {has_dups}')

    if has_dups:
        ok = move_item(key, SHORTTERMS_KEY, DD_KEY)
        result = '00_INBOXS_DD' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {result} (有重复PDF)')
    else:
        ok = move_item(key, SHORTTERMS_KEY, CC_KEY)
        result = '00_INBOXS_CC' if ok else 'move_failed'
        print(f'  {"✅" if ok else "❌"} {result} (多PDF无重复)')
    return result

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('=' * 70)
    print('  01_SHORTTERMS 分类处理脚本')
    print('=' * 70)

    # Only process bibliography items, not notes or attachments
    raw = zot.everything(zot.collection_items(
        SHORTTERMS_KEY, itemType='-attachment'
    ))
    items = [i for i in raw if i['data'].get('itemType') != 'note']
    total = len(items)
    print(f'共 {total} 个条目（已排除笔记和附件）\n')

    stats: Counter = Counter()
    for idx, item in enumerate(items, 1):
        result = process_item(item, idx, total)
        stats[result] += 1
        time.sleep(0.3)   # be gentle with the API

    print('\n' + '=' * 70)
    print('完成！结果汇总：')
    for dest, count in sorted(stats.items()):
        print(f'  {dest:20s}: {count} 条')


# ── Re-classify DD and CC (fix duplicate detection) ──────────────────────────

def reclassify_dd_cc():
    """
    Re-process items in DD and CC with the corrected duplicate detection prompt.
    - DD items that are NOT true duplicates → move to CC
    - CC items that ARE true duplicates     → move to DD
    """
    print('=' * 70)
    print('  重新分类 00_INBOXS_DD 和 00_INBOXS_CC')
    print('=' * 70)

    stats: Counter = Counter()

    for col_key, col_name, expect_dup in [
        (DD_KEY, '00_INBOXS_DD', True),
        (CC_KEY, '00_INBOXS_CC', False),
    ]:
        raw = zot.everything(zot.collection_items(col_key, itemType='-attachment'))
        items = [i for i in raw if i['data'].get('itemType') != 'note']
        print(f'\n{col_name}: {len(items)} 个条目\n')

        for idx, item in enumerate(items, 1):
            key   = item['key']
            data  = item['data']
            title = re.sub(r'<[^>]+>', '', data.get('title', '(无标题)'))[:55]
            year  = data.get('date', '')[:4]

            prefix = f'[{idx:04d}/{len(items)}]'
            print(f'\n{prefix} [{key}] ({year}) {title}')

            children = zot.children(key)
            pdfs = [c for c in children
                    if c['data'].get('itemType') == 'attachment'
                    and c['data'].get('contentType') == 'application/pdf']
            pdf_count = len(pdfs)
            print(f'  PDFs: {pdf_count}')

            if pdf_count < 2:
                print(f'  ⚠️  PDF数量 < 2，跳过（保留在 {col_name}）')
                stats[f'skip_{col_name}'] += 1
                time.sleep(0.1)
                continue

            texts = []
            for pdf in pdfs:
                local_path = get_local_pdf_path(pdf)
                texts.append(extract_pdf_text(local_path) if local_path else '')

            print(f'  🤖 DeepSeek 重复检测中... ({pdf_count} 个PDF)')
            has_dups = check_duplicates(texts)
            print(f'  → 有重复: {has_dups}')

            if expect_dup and not has_dups:
                # DD → CC
                ok = move_item(key, col_key, CC_KEY)
                result = '→CC' if ok else 'move_failed'
                print(f'  {"✅" if ok else "❌"} 移到 00_INBOXS_CC (非重复，正文+SI)')
            elif not expect_dup and has_dups:
                # CC → DD
                ok = move_item(key, col_key, DD_KEY)
                result = '→DD' if ok else 'move_failed'
                print(f'  {"✅" if ok else "❌"} 移到 00_INBOXS_DD (发现重复)')
            else:
                result = 'stay'
                print(f'  ✓ 保留在 {col_name}')

            stats[result] += 1
            time.sleep(0.3)

    print('\n' + '=' * 70)
    print('完成！结果汇总：')
    for k, v in sorted(stats.items()):
        print(f'  {k:20s}: {v} 条')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'reclassify':
        reclassify_dd_cc()
    else:
        main()
