"""
download_dd_si.py
=================
Fetch and upload SI files for every item in 00_INBOXS_DD.
Processes items one at a time. Already-uploaded SI is skipped.

Supports: Elsevier, ACS, RSC, Springer.
Wiley/unknown: URL logged to .si-downloads/dd_blocked.txt for manual download.

Usage:
    cd zotero-mcp
    uv run python scripts/download_dd_si.py
"""
import os
import re
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import fitz
import httpx
import requests
from dotenv import load_dotenv
from openai import OpenAI
import pyzotero.zotero as zotero

# ── Project / env ─────────────────────────────────────────────────────────────
PROJECT = Path(__file__).parent.parent
load_dotenv(PROJECT / '.env')

LIBRARY_ID  = os.environ['ZOTERO_LIBRARY_ID']
API_KEY     = os.environ['ZOTERO_API_KEY']
ELS_KEY     = os.environ['ELSEVIER_API_KEY']

ZOT_STORAGE = Path(os.environ.get('ZOTERO_STORAGE_PATH',
                   'C:/Users/chengliu/Zotero/storage'))
SI_DIR  = Path(os.environ.get('SHORTTERMS_SI_DIR',
               str(PROJECT / '.si-downloads/shortterms')))
BLOCKED = PROJECT / '.si-downloads/dd_blocked.txt'
SI_DIR.mkdir(parents=True, exist_ok=True)
BLOCKED.parent.mkdir(parents=True, exist_ok=True)

# ── Collection name ────────────────────────────────────────────────────────────
COL_DD_NAME = '00_INBOXS_DD'

# ── Constants ──────────────────────────────────────────────────────────────────
ALLOWED_EXT  = {'.pdf', '.docx', '.doc'}
MAX_MMC      = 8
OLE_MAGIC    = b'\xd0\xcf\x11\xe0'
RE_PII       = re.compile(r'pii[/=](S\w+)', re.I)
SI_KEYWORDS  = ['supporting', 'suppl', '_si_', '_si.', 'si_00', 'supp_', 'mmc', 'suppdata']
REQ_HEADERS  = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

# ── Clients ────────────────────────────────────────────────────────────────────
_orig_post = httpx.post
def _post_timeout(*a, **kw):
    kw['timeout'] = httpx.Timeout(600.0, connect=60.0)
    return _orig_post(*a, **kw)
httpx.post = _post_timeout

zot = zotero.Zotero(LIBRARY_ID, 'user', API_KEY)
zot.client = httpx.Client(
    timeout=httpx.Timeout(600.0, connect=60.0),
    headers=dict(zot.client.headers),
)

# ── Collection resolution ──────────────────────────────────────────────────────
def resolve_col(name: str) -> str:
    for c in zot.collections():
        if c['data']['name'] == name:
            return c['key']
    raise ValueError(f'Collection not found: {name!r}')

# ── Publisher detection ────────────────────────────────────────────────────────
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

# ── File helpers ───────────────────────────────────────────────────────────────
def download(url: str, dest: Path) -> tuple[bool, float]:
    try:
        r = requests.get(url, timeout=120, stream=True, headers=REQ_HEADERS)
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


def upload_files(files: list[Path], item_key: str) -> int:
    n = 0
    for path in files:
        try:
            result = zot.attachment_simple([str(path)], parentid=item_key)
            if result.get('success') or result.get('unchanged'):
                label = 'unchanged' if result.get('unchanged') else 'uploaded'
                print(f'    ✓ {label}: {path.name}')
                n += 1
            else:
                print(f'    ✗ upload failed: {path.name} | {result}')
        except Exception as e:
            print(f'    ✗ upload error ({path.name}): {str(e)[:80]}')
    return n

# ── SI presence check ──────────────────────────────────────────────────────────
def has_si(item_key: str) -> bool:
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

# ── Publisher-specific finders ─────────────────────────────────────────────────
def elsevier_pii(item: dict) -> str | None:
    doi = item['data'].get('DOI', '')
    m = RE_PII.search(item['data'].get('url', ''))
    if m:
        return m.group(1)
    if not doi:
        return None
    try:
        r = requests.get(
            f'https://api.elsevier.com/content/article/doi/{doi}',
            headers={'X-ELS-APIKey': ELS_KEY, 'Accept': 'application/json'},
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
                          allow_redirects=True, headers=REQ_HEADERS)
        m2 = RE_PII.search(r2.url)
        if m2:
            return m2.group(1)
    except Exception:
        pass
    return None


def elsevier_si_urls(pii: str, item_key: str) -> list[tuple[str, str, str]]:
    hits = []
    for n in range(1, MAX_MMC + 1):
        found = False
        for ext in ('pdf', 'docx'):
            url = f'https://ars.els-cdn.com/content/image/1-s2.0-{pii}-mmc{n}.{ext}'
            try:
                rh = requests.head(url, timeout=10, headers=REQ_HEADERS)
                ct = rh.headers.get('Content-Type', '')
                if rh.status_code == 200 and 'xml' not in ct and 'html' not in ct:
                    hits.append((url, f'{item_key}_mmc{n}.{ext}', ext))
                    found = True
            except Exception:
                pass
        if not found and n > 1:
            break
    return hits


def rsc_si_urls(doi: str) -> list[tuple[str, str]]:
    if '10.1039/' not in doi:
        return []
    paper_id = doi.split('10.1039/')[-1].lower()
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=REQ_HEADERS)
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


def acs_si_files(doi: str) -> list[dict]:
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


def springer_si_urls(doi: str) -> list[tuple[str, str]]:
    results, seen = [], set()
    try:
        r = requests.get(f'https://doi.org/{doi}', timeout=25,
                         allow_redirects=True, headers=REQ_HEADERS)
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

# ── Main fetch logic ───────────────────────────────────────────────────────────
def fetch_si(item: dict) -> str:
    """Try to fetch and upload SI. Returns: 'uploaded' / 'already_has_si' /
    'no_doi' / 'no_si' / 'blocked' / 'error'."""
    key = item['key']
    doi = item['data'].get('DOI', '')

    if not doi:
        print('    SI: 跳过 (无DOI)')
        return 'no_doi'
    if has_si(key):
        print('    SI: 已有 SI 附件，跳过')
        return 'already_has_si'

    publisher = detect_publisher(item)
    print(f'    SI: 查找中 (publisher={publisher}, doi={doi[:50]})')

    files: list[Path] = []

    if publisher == 'elsevier':
        pii = elsevier_pii(item)
        if not pii:
            print('    SI: 无法获取 PII')
            return 'no_si'
        hits = elsevier_si_urls(pii, key)
        if not hits:
            print('    SI: mmc CDN 无文件')
            return 'no_si'
        for url, fname, ext in hits:
            dest = SI_DIR / fname
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download(url, dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('docx', 'doc') else dest)

    elif publisher == 'rsc':
        for url, fname in rsc_si_urls(doi):
            ext = Path(fname).suffix.lower()
            if ext not in ALLOWED_EXT:
                continue
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download(url, dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('.docx', '.doc') else dest)

    elif publisher == 'acs':
        for fi in acs_si_files(doi):
            ext = Path(fi['name']).suffix.lower()
            if ext not in ALLOWED_EXT:
                continue
            dest = SI_DIR / f'{key}_{fi["name"]}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download(fi['downloadUrl'], dest)
                if not ok:
                    continue
                print(f'    SI: 下载 {fi["name"]} ({sz:.1f}MB)')
            files.append(docx_to_pdf(dest) or dest if ext in ('.docx', '.doc') else dest)

    elif publisher == 'springer':
        for url, fname in springer_si_urls(doi):
            dest = SI_DIR / f'{key}_{fname}'
            if not (dest.exists() and dest.stat().st_size > 500):
                ok, sz = download(url, dest)
                if not ok:
                    with open(BLOCKED, 'a') as bf:
                        bf.write(f'{doi}\tspringer\t{url}\n')
                    continue
                print(f'    SI: 下载 {fname} ({sz:.1f}MB)')
            files.append(dest)

    else:
        print(f'    SI: publisher "{publisher}" 不支持，记录到 blocked')
        with open(BLOCKED, 'a') as bf:
            bf.write(f'{doi}\t{publisher}\thttps://doi.org/{doi}\n')
        return 'blocked'

    if not files:
        return 'no_si'
    uploaded = upload_files(files, key)
    return 'uploaded' if uploaded > 0 else 'no_si'

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print('Loading collections...')
    col_dd = resolve_col(COL_DD_NAME)
    print(f'  DD={col_dd}')
    print(f'  SI dir: {SI_DIR}')

    raw   = zot.everything(zot.collection_items(col_dd, itemType='-attachment'))
    items = [i for i in raw if i['data'].get('itemType') != 'note']
    total = len(items)

    print(f'\n{COL_DD_NAME}: {total} 个条目\n')
    print('=' * 70)

    stats: Counter = Counter()

    for idx, item in enumerate(items, 1):
        key       = item['key']
        title     = re.sub(r'<[^>]+>', '', item['data'].get('title', '(无标题)'))[:60]
        year      = item['data'].get('date', '')[:4]
        item_type = item['data'].get('itemType', '')

        print(f'\n[{idx:04d}/{total}] [{key}] ({year}) [{item_type}] {title}')
        result = fetch_si(item)
        stats[result] += 1
        time.sleep(0.5)

    print('\n' + '=' * 70)
    print('完成！结果汇总：')
    for k, v in sorted(stats.items()):
        print(f'  {k:20s}: {v} 条')
    print(f'\n已记录无法下载的条目：{BLOCKED}')


if __name__ == '__main__':
    main()
