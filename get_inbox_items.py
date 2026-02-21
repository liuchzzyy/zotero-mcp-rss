from pyzotero import zotero
import os, json, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

zot = zotero.Zotero(os.getenv('ZOTERO_LIBRARY_ID'), os.getenv('ZOTERO_LIBRARY_TYPE'), os.getenv('ZOTERO_API_KEY'))

INBOXS = '2PSBFJEI'
items = zot.everything(zot.collection_items(INBOXS, itemType='-attachment || note'))
print(f'Total items in 00_INBOXS: {len(items)}')

result = []
for item in items:
    d = item['data']
    if d.get('itemType') in ('attachment', 'note'):
        continue
    doi = d.get('DOI', '')
    title = d.get('title', '')
    key = d.get('key', '')
    itype = d.get('itemType', '')
    result.append({'key': key, 'title': title, 'doi': doi, 'itemType': itype})

print(f'Items to process: {len(result)}')
for i, r in enumerate(result, 1):
    print(f'{i:3d}. {r["key"]} | DOI: {r["doi"][:40]} | {r["title"][:60]}')

with open('inbox_items.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
