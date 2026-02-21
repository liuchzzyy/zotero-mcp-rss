"""
Download Supporting Information (SI) files for Zotero 02_PROJECTS items.

Multi-publisher pipeline:
1. Query Crossref for metadata (cached)
2. Construct publisher-specific SI URLs
3. Download and validate files
4. Convert DOCX → PDF via win32com
5. Upload to Zotero as attachments
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

import httpx
from dotenv import load_dotenv
from pyzotero import zotero

# ── Config ──────────────────────────────────────────────────────────────
load_dotenv()

ITEMS_FILE = Path(__file__).parent / "items_need_si.json"
CACHE_DIR = Path(__file__).parent / ".crossref-cache"
SI_DIR = Path(__file__).parent / ".si-downloads"
BLOCKED_FILE = SI_DIR / "blocked_si_urls.txt"

ZOTERO_LIBRARY_ID = os.environ["ZOTERO_LIBRARY_ID"]
ZOTERO_API_KEY = os.environ["ZOTERO_API_KEY"]
POLITE_EMAIL = os.environ.get("POLITE_POOL_EMAIL", "liuchzzyy@gmail.com")

CROSSREF_HEADERS = {
    "User-Agent": f"ZoteroSIDownloader/1.0 (mailto:{POLITE_EMAIL})",
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/pdf, application/octet-stream, */*",
}

# Publishers blocked by Cloudflare/Radware bot protection
BLOCKED_PUBLISHERS = {"ACS", "Wiley", "Science", "IOP", "ECS", "APS"}

CACHE_DIR.mkdir(exist_ok=True)
SI_DIR.mkdir(exist_ok=True)


# ── Crossref ────────────────────────────────────────────────────────────
def get_crossref_metadata(doi: str, client: httpx.Client) -> dict | None:
    """Fetch Crossref metadata for a DOI, with file-based caching."""
    safe_doi = doi.replace("/", "__")
    cache_file = CACHE_DIR / f"{safe_doi}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    try:
        resp = client.get(url, params={"mailto": POLITE_EMAIL}, timeout=30)
        if resp.status_code == 200:
            data = resp.json().get("message", {})
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            return data
        else:
            print(f"    Crossref {resp.status_code} for {doi}")
            return None
    except Exception as e:
        print(f"    Crossref error for {doi}: {e}")
        return None


# ── SI URL Construction ─────────────────────────────────────────────────
def find_si_urls(item: dict, cr: dict | None) -> list[dict]:
    """
    Return list of {url, ext} dicts for SI candidates.
    Each publisher has its own URL construction logic.
    """
    doi = item["doi"]
    publisher = item.get("publisher", "Other")
    candidates = []

    # 1. Check Crossref supplementary links first
    if cr:
        for link in cr.get("link", []):
            ct = link.get("content-type", "")
            ia = link.get("intended-application", "")
            url = link.get("URL", "")
            if "supplementary" in ia or "supp" in url.lower():
                ext = "pdf" if "pdf" in ct else "unknown"
                candidates.append({"url": url, "ext": ext, "source": "crossref"})

    # 2. Publisher-specific logic
    if publisher == "Elsevier":
        candidates.extend(_elsevier_urls(doi, cr))
    elif publisher == "RSC":
        candidates.extend(_rsc_urls(doi, cr))
    elif publisher == "ACS":
        candidates.extend(_acs_urls(doi))
    elif publisher == "Wiley":
        candidates.extend(_wiley_urls(doi, cr))
    elif publisher in ("Springer", "Nature"):
        candidates.extend(_springer_urls(doi, cr))
    elif publisher == "MDPI":
        candidates.extend(_mdpi_urls(doi, cr))
    elif publisher == "ECS":
        candidates.extend(_ecs_urls(doi, cr))
    elif publisher == "IOP":
        candidates.extend(_iop_urls(doi))
    elif publisher == "APS":
        candidates.extend(_aps_urls(doi))
    elif publisher == "Science":
        candidates.extend(_science_urls(doi))
    else:
        candidates.extend(_other_urls(doi, cr))

    return candidates


def _elsevier_urls(doi: str, cr: dict | None) -> list[dict]:
    """Elsevier: extract PII from Crossref → ars.els-cdn.com mmc URLs."""
    pii = None
    if cr:
        alt_ids = cr.get("alternative-id", [])
        for aid in alt_ids:
            # PII looks like S0013468624017468 or S2405-8297(24)00123-4
            cleaned = aid.replace("-", "").replace("(", "").replace(")", "")
            if cleaned.startswith("S") and len(cleaned) >= 15:
                pii = cleaned
                break

    if not pii:
        # Try to extract from DOI suffix
        m = re.search(r"10\.1016/[a-z.]+\.(\d{4}\.\d+)", doi)
        if m:
            # Can't reliably construct PII from DOI alone
            pass

    urls = []
    if pii:
        base = f"https://ars.els-cdn.com/content/image/1-s2.0-{pii}"
        for suffix in ["mmc1.pdf", "mmc1.docx", "mmc1.doc"]:
            urls.append({"url": f"{base}-{suffix}", "ext": suffix.split(".")[-1], "source": "elsevier-pii"})
    return urls


def _rsc_urls(doi: str, cr: dict | None) -> list[dict]:
    """RSC: /suppdata/{prefix}{year}/{journal_lower}/{id_lower}/{id_lower}1.pdf
    Example: 10.1039/D4SC07285E → suppdata/d4/sc/d4sc07285e/d4sc07285e1.pdf
    """
    urls = []
    m = re.search(r"10\.1039/([A-Za-z0-9]+)", doi)
    if m:
        article_id = m.group(1)
        lower_id = article_id.lower()
        # Modern pattern: D4SC07285E → d4/sc/d4sc07285e
        m2 = re.match(r"([a-z])(\d)([a-z]{2})(.+)", lower_id)
        if m2:
            prefix, year, journal_code, _ = m2.groups()
            urls.append({
                "url": f"https://www.rsc.org/suppdata/{prefix}{year}/{journal_code}/{lower_id}/{lower_id}1.pdf",
                "ext": "pdf",
                "source": "rsc-pattern",
            })
        else:
            # Older DOIs like b926434e, tf9696502870
            urls.append({
                "url": f"https://www.rsc.org/suppdata/{lower_id[:2]}/{lower_id}/{lower_id}1.pdf",
                "ext": "pdf",
                "source": "rsc-pattern-old",
            })
    # Also add page-scrape fallback
    urls.append({"url": f"__SCRAPE__rsc__{doi}", "ext": "pdf", "source": "rsc-scrape"})
    return urls


def _acs_urls(doi: str) -> list[dict]:
    """ACS: suppl_file patterns (likely Cloudflare-blocked)."""
    # DOI: 10.1021/jacs.4c14751
    m = re.search(r"10\.1021/([a-z]+)\.(.+)", doi)
    urls = []
    if m:
        journal_code = m.group(1)
        suffix = m.group(2)
        # Common ACS SI patterns
        urls.append({
            "url": f"https://pubs.acs.org/doi/suppl/10.1021/{journal_code}.{suffix}/suppl_file/{journal_code}{suffix}_si_001.pdf",
            "ext": "pdf",
            "source": "acs-pattern",
        })
    return urls


def _wiley_urls(doi: str, cr: dict | None) -> list[dict]:
    """Wiley: various patterns (likely Cloudflare-blocked)."""
    urls = []
    # Try Crossref links
    if cr:
        for link in cr.get("link", []):
            url = link.get("URL", "")
            if "supp" in url.lower() or "support" in url.lower():
                urls.append({"url": url, "ext": "pdf", "source": "wiley-crossref"})

    # Wiley SI is typically at /action/downloadSupplement
    urls.append({
        "url": f"https://onlinelibrary.wiley.com/action/downloadSupplement?doi={quote(doi, safe='')}&file=",
        "ext": "pdf",
        "source": "wiley-pattern",
    })
    return urls


def _springer_urls(doi: str, cr: dict | None) -> list[dict]:
    """Springer/Nature: scrape article page → find static-content.springer.com ESM URLs.
    Correct filename pattern: {journalId}_{fullYear}_{articleNum}_MOESM1_ESM.pdf
    Example: 10.1038/s41893-025-01646-1 → 41893_2025_1646_MOESM1_ESM.pdf
    """
    urls = []
    encoded_doi = quote(doi, safe="")

    # Parse DOI to construct predicted filename
    # Handles: 10.1038/s41893-025-01646-1, 10.1007/s40843-024-3260-1
    m = re.search(r"10\.\d+/s?(\d+)-(\d+)-(\d+)-([a-z0-9]+)", doi)
    if m:
        journal_id, year_suffix, article_num, sub = m.groups()
        # Convert 2-3 digit year suffix to full year
        if len(year_suffix) == 3:
            full_year = "2" + year_suffix  # 025 → 2025
        elif len(year_suffix) == 2:
            full_year = "20" + year_suffix  # 25 → 2025
        else:
            full_year = year_suffix
        # Strip leading zeros from article number
        article_stripped = article_num.lstrip("0") or "0"
        for ext in ["pdf", "docx"]:
            urls.append({
                "url": f"https://static-content.springer.com/esm/art%3A{encoded_doi}/MediaObjects/{journal_id}_{full_year}_{article_stripped}_MOESM1_ESM.{ext}",
                "ext": ext,
                "source": "springer-predicted",
            })

    # Page-scrape fallback: find actual SI URLs from the article HTML page
    urls.append({"url": f"__SCRAPE__springer__{doi}", "ext": "pdf", "source": "springer-scrape"})
    return urls


def _mdpi_urls(doi: str, cr: dict | None) -> list[dict]:
    """MDPI: open access, often has SI in Crossref links."""
    urls = []
    if cr:
        for link in cr.get("link", []):
            url = link.get("URL", "")
            if "supp" in url.lower() or "s1" in url.lower():
                urls.append({"url": url, "ext": "pdf", "source": "mdpi-crossref"})

    # MDPI pattern: https://www.mdpi.com/article/{doi}/s1
    # Or https://www.mdpi.com/{journal}/{volume}/{issue}/{article_num}/s1
    urls.append({
        "url": f"https://www.mdpi.com/article/10.3390/{doi.split('/')[-1]}/s1",
        "ext": "pdf",
        "source": "mdpi-pattern",
    })
    return urls


def _ecs_urls(doi: str, cr: dict | None) -> list[dict]:
    """ECS/IOP-published: scrape article page for SI links."""
    # ECS journals are now published by IOP
    return [{"url": f"__SCRAPE__iop__{doi}", "ext": "pdf", "source": "ecs-iop-scrape"}]


def _iop_urls(doi: str) -> list[dict]:
    """IOP: scrape article page for SI links."""
    return [{"url": f"__SCRAPE__iop__{doi}", "ext": "pdf", "source": "iop-scrape"}]


def _aps_urls(doi: str) -> list[dict]:
    """APS: supplemental material patterns."""
    urls = []
    # APS DOI: 10.1103/PhysRevB.90.014426
    m = re.search(r"10\.1103/([A-Za-z.]+)\.(\d+)\.(\d+)", doi)
    if m:
        journal, volume, page = m.groups()
        journal_lower = journal.lower().replace(".", "")
        urls.append({
            "url": f"https://journals.aps.org/{journal_lower}/supplemental/{doi}",
            "ext": "pdf",
            "source": "aps-supplemental",
        })
    return urls


def _science_urls(doi: str) -> list[dict]:
    """Science: likely Cloudflare-blocked."""
    urls = []
    if "sciadv" in doi:
        # Science Advances: https://www.science.org/doi/suppl/{doi}/suppl_file/...
        urls.append({
            "url": f"https://www.science.org/doi/suppl/{doi}",
            "ext": "pdf",
            "source": "science-suppl",
        })
    return urls


def _other_urls(doi: str, cr: dict | None) -> list[dict]:
    """Other publishers: rely on Crossref links."""
    urls = []
    if cr:
        for link in cr.get("link", []):
            url = link.get("URL", "")
            ia = link.get("intended-application", "")
            if "supp" in url.lower() or "supp" in ia.lower():
                urls.append({"url": url, "ext": "pdf", "source": "crossref-other"})
    return urls


# ── Page Scraping for SI URLs ───────────────────────────────────────────
def scrape_si_urls(scrape_key: str, client: httpx.Client) -> list[dict]:
    """Scrape an article page to find SI download URLs.
    scrape_key format: __SCRAPE__{publisher}__{doi}
    """
    parts = scrape_key.split("__")
    publisher = parts[2]
    doi = parts[3]

    if publisher == "rsc":
        return _scrape_rsc(doi, client)
    elif publisher == "springer":
        return _scrape_springer(doi, client)
    elif publisher == "iop":
        return _scrape_iop(doi, client)
    return []


def _scrape_rsc(doi: str, client: httpx.Client) -> list[dict]:
    """Scrape RSC article page for ESI PDF link."""
    article_id = doi.split("/")[-1]
    url = f"https://pubs.rsc.org/en/content/articlelanding/2025/xx/{article_id}"
    try:
        resp = client.get(url, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            return []
        # Find suppdata links
        matches = re.findall(r'(https?://www\.rsc\.org/suppdata/[^"\'>\s]+\.pdf)', resp.text, re.I)
        return [{"url": m, "ext": "pdf", "source": "rsc-scraped"} for m in matches[:3]]
    except Exception:
        return []


def _scrape_springer(doi: str, client: httpx.Client) -> list[dict]:
    """Scrape Nature/Springer article page for static-content ESM links."""
    if "10.1038" in doi:
        article_id = doi.split("/")[-1]
        url = f"https://www.nature.com/articles/{article_id}"
    else:
        url = f"https://link.springer.com/article/{doi}"
    try:
        resp = client.get(url, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            return []
        # Find static-content ESM links
        matches = re.findall(
            r'(https://static-content\.springer\.com/esm/[^"\'>\s]+(?:MOESM\d+_ESM|supplementary)[^"\'>\s]*\.(?:pdf|docx|doc))',
            resp.text,
            re.I,
        )
        results = []
        for m in matches:
            ext = m.rsplit(".", 1)[-1].lower()
            results.append({"url": m, "ext": ext, "source": "springer-scraped"})
        return results[:5]
    except Exception:
        return []


def _scrape_iop(doi: str, client: httpx.Client) -> list[dict]:
    """Scrape IOP article page for supplementary data links."""
    url = f"https://iopscience.iop.org/article/{doi}"
    try:
        resp = client.get(url, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            return []
        # Find supplementary file links
        matches = re.findall(
            r'(https?://[^"\'>\s]+(?:supplementary|supp|mmedia)[^"\'>\s]*\.(?:pdf|docx|doc|zip))',
            resp.text,
            re.I,
        )
        if not matches:
            # IOP sometimes uses /media endpoint
            media_matches = re.findall(
                r'href="(/article/[^"]+/media/[^"]+)"',
                resp.text,
            )
            for mm in media_matches[:3]:
                full_url = f"https://iopscience.iop.org{mm}"
                ext = mm.rsplit(".", 1)[-1].lower() if "." in mm.split("/")[-1] else "pdf"
                matches.append(full_url)
        return [{"url": m, "ext": m.rsplit(".", 1)[-1].lower() if "." in m.split("/")[-1] else "pdf", "source": "iop-scraped"} for m in matches[:3]]
    except Exception:
        return []


# ── Download ────────────────────────────────────────────────────────────
def download_file(url: str, dest: Path, client: httpx.Client) -> tuple[bool, str]:
    """
    Download a file, validate content.
    Returns (success, message).
    """
    try:
        resp = client.get(url, follow_redirects=True, timeout=60)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"

        content = resp.content
        if len(content) < 1000:
            return False, f"Too small ({len(content)} bytes)"

        # Check for HTML error pages
        try:
            text_start = content[:500].decode("utf-8", errors="ignore").lower()
            if "<html" in text_start and "not found" in text_start:
                return False, "HTML error page"
            if "<html" in text_start and "access denied" in text_start:
                return False, "Access denied"
            if "<html" in text_start and "cloudflare" in text_start:
                return False, "Cloudflare blocked"
        except Exception:
            pass

        # Validate file type
        if dest.suffix == ".pdf":
            if not content[:10].startswith(b"%PDF"):
                # Check if it's actually HTML
                try:
                    start = content[:200].decode("utf-8", errors="ignore").lower()
                    if "<html" in start or "<!doctype" in start:
                        return False, "Got HTML instead of PDF"
                except Exception:
                    pass
                return False, "Not a valid PDF (no %PDF header)"
        elif dest.suffix in (".docx", ".doc"):
            if not content[:4].startswith(b"PK"):
                return False, "Not a valid DOCX (no PK header)"

        dest.write_bytes(content)
        return True, f"OK ({len(content)} bytes)"

    except httpx.TimeoutException:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {e}"


# ── DOCX → PDF ──────────────────────────────────────────────────────────
def convert_docx_to_pdf(docx_path: Path) -> Path | None:
    """Convert DOCX to PDF using win32com. Returns PDF path or None."""
    try:
        import win32com.client

        pdf_path = docx_path.with_suffix(".pdf")
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(docx_path.resolve()))
            doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)
            doc.Close()
            print(f"    Converted {docx_path.name} → {pdf_path.name}")
            return pdf_path
        finally:
            word.Quit()
    except Exception as e:
        print(f"    DOCX→PDF conversion failed: {e}")
        return None


# ── Zotero Upload ───────────────────────────────────────────────────────
def create_zotero_client() -> zotero.Zotero:
    """Create pyzotero client with timeout patch."""
    zot = zotero.Zotero(ZOTERO_LIBRARY_ID, "user", ZOTERO_API_KEY)

    # Monkey-patch httpx timeout for large uploads
    original_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("timeout", 120.0)
        original_init(self, *args, **kwargs)

    httpx.Client.__init__ = patched_init
    return zot


def upload_to_zotero(
    zot: zotero.Zotero, parent_key: str, file_path: Path
) -> tuple[bool, str]:
    """Upload SI file to Zotero as attachment."""
    try:
        result = zot.attachment_both(
            [("Supporting Information", str(file_path))],
            parentid=parent_key,
        )
        if result and "success" in result:
            return True, "Uploaded"
        # pyzotero returns different structures
        return True, f"Upload result: {result}"
    except Exception as e:
        return False, f"Upload error: {e}"


# ── Main Pipeline ───────────────────────────────────────────────────────
def main():
    # Parse args
    dry_run = "--dry-run" in sys.argv
    skip_upload = "--skip-upload" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    start_from = 0
    for arg in sys.argv:
        if arg.startswith("--start="):
            start_from = int(arg.split("=")[1])

    # Load items
    items = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(items)} items from {ITEMS_FILE.name}")

    if start_from:
        items = items[start_from:]
        print(f"Starting from index {start_from}")
    if limit:
        items = items[:limit]
        print(f"Processing {len(items)} items (limit={limit})")

    # Stats
    stats = {
        "crossref_found": 0,
        "crossref_miss": 0,
        "downloaded": 0,
        "blocked": 0,
        "not_found": 0,
        "uploaded": 0,
        "upload_skip": 0,
        "already_has": 0,
        "converted": 0,
        "errors": 0,
    }
    publisher_stats = {}
    blocked_urls = []

    # Create clients — browser UA for downloads, polite UA for Crossref
    crossref_client = httpx.Client(headers=CROSSREF_HEADERS, follow_redirects=True)
    client = httpx.Client(headers=BROWSER_HEADERS, follow_redirects=True)
    zot = None
    if not skip_upload and not dry_run:
        zot = create_zotero_client()

    try:
        for idx, item in enumerate(items):
            key = item["key"]
            doi = item["doi"]
            publisher = item.get("publisher", "Other")
            title_short = item.get("title", "")[:60]

            # Init publisher stats
            if publisher not in publisher_stats:
                publisher_stats[publisher] = {"downloaded": 0, "blocked": 0, "not_found": 0, "uploaded": 0}

            # Check if already downloaded
            existing = list(SI_DIR.glob(f"{key}-SI.*"))
            if existing:
                pdf_exists = any(f.suffix == ".pdf" for f in existing)
                if pdf_exists:
                    print(f"[{idx+1}/{len(items)}] {key} ({publisher}) — Already downloaded")
                    stats["already_has"] += 1
                    continue

            print(f"[{idx+1}/{len(items)}] {key} ({publisher}) {title_short}")

            # Step 1: Crossref
            cr = get_crossref_metadata(doi, crossref_client)
            if cr:
                stats["crossref_found"] += 1
            else:
                stats["crossref_miss"] += 1

            # Step 2: Find SI URLs
            candidates = find_si_urls(item, cr)
            if not candidates:
                print(f"    No SI URL candidates found")
                stats["not_found"] += 1
                publisher_stats[publisher]["not_found"] += 1
                continue

            # Check if this publisher is blocked
            is_blocked = publisher in BLOCKED_PUBLISHERS
            if is_blocked:
                # Save URLs for manual download
                for c in candidates:
                    blocked_urls.append(f"{key}\t{publisher}\t{doi}\t{c['url']}")
                print(f"    Blocked publisher ({publisher}), saved {len(candidates)} URLs")
                stats["blocked"] += 1
                publisher_stats[publisher]["blocked"] += 1
                continue

            if dry_run:
                print(f"    [DRY RUN] Would try {len(candidates)} URLs")
                for c in candidates:
                    print(f"      {c['source']}: {c['url'][:100]}")
                continue

            # Step 3: Try downloading
            downloaded_path = None
            for c in candidates:
                url = c["url"]

                # Handle scrape-based URL resolution
                if url.startswith("__SCRAPE__"):
                    print(f"    Scraping {c['source']}...")
                    scraped = scrape_si_urls(url, client)
                    if scraped:
                        print(f"    Found {len(scraped)} SI URLs from scraping")
                        for sc in scraped:
                            ext = sc["ext"]
                            dest = SI_DIR / f"{key}-SI.{ext}"
                            print(f"    Trying {sc['source']}: {sc['url'][:100]}...")
                            ok, msg = download_file(sc["url"], dest, client)
                            if ok:
                                print(f"    ✓ Downloaded: {msg}")
                                downloaded_path = dest
                                break
                            else:
                                print(f"    ✗ {msg}")
                                if dest.exists():
                                    dest.unlink()
                        if downloaded_path:
                            break
                    else:
                        print(f"    ✗ No SI URLs found from scraping")
                    continue

                ext = c["ext"]
                if ext == "unknown":
                    ext = "pdf"
                dest = SI_DIR / f"{key}-SI.{ext}"
                print(f"    Trying {c['source']}: {url[:100]}...")

                ok, msg = download_file(url, dest, client)
                if ok:
                    print(f"    ✓ Downloaded: {msg}")
                    downloaded_path = dest
                    break
                else:
                    print(f"    ✗ {msg}")
                    if dest.exists():
                        dest.unlink()

            if not downloaded_path:
                stats["not_found"] += 1
                publisher_stats[publisher]["not_found"] += 1
                continue

            stats["downloaded"] += 1
            publisher_stats[publisher]["downloaded"] += 1

            # Step 4: Convert DOCX → PDF if needed
            if downloaded_path.suffix in (".docx", ".doc"):
                pdf_path = convert_docx_to_pdf(downloaded_path)
                if pdf_path:
                    stats["converted"] += 1
                    downloaded_path = pdf_path
                else:
                    print(f"    Warning: DOCX conversion failed, uploading DOCX")

            # Step 5: Upload to Zotero
            if zot and not skip_upload:
                ok, msg = upload_to_zotero(zot, key, downloaded_path)
                if ok:
                    print(f"    ↑ Uploaded to Zotero")
                    stats["uploaded"] += 1
                    publisher_stats[publisher]["uploaded"] += 1
                else:
                    print(f"    ↑ Upload failed: {msg}")
                    stats["errors"] += 1
            else:
                stats["upload_skip"] += 1

            # Rate limiting
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user!")
    finally:
        client.close()
        crossref_client.close()

        # Save blocked URLs
        if blocked_urls:
            BLOCKED_FILE.write_text("\n".join(blocked_urls) + "\n", encoding="utf-8")
            print(f"\nSaved {len(blocked_urls)} blocked URLs to {BLOCKED_FILE}")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Crossref found:  {stats['crossref_found']}")
    print(f"  Crossref miss:   {stats['crossref_miss']}")
    print(f"  Already had SI:  {stats['already_has']}")
    print(f"  Downloaded:      {stats['downloaded']}")
    print(f"  Converted DOCX:  {stats['converted']}")
    print(f"  Uploaded:        {stats['uploaded']}")
    print(f"  Blocked:         {stats['blocked']}")
    print(f"  Not found:       {stats['not_found']}")
    print(f"  Errors:          {stats['errors']}")

    print(f"\n{'Publisher':<12} {'Downloaded':>10} {'Blocked':>8} {'NotFound':>9} {'Uploaded':>9}")
    print("-" * 52)
    for pub in sorted(publisher_stats.keys()):
        s = publisher_stats[pub]
        print(f"  {pub:<10} {s['downloaded']:>10} {s['blocked']:>8} {s['not_found']:>9} {s['uploaded']:>9}")


if __name__ == "__main__":
    main()
