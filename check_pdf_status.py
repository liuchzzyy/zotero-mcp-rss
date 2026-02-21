"""
检查 inbox 中哪些文献已经有 PDF 附件
"""
from pyzotero import zotero
import os
import json
from dotenv import load_dotenv

load_dotenv()

zot = zotero.Zotero(
    os.getenv('ZOTERO_LIBRARY_ID'),
    os.getenv('ZOTERO_LIBRARY_TYPE'),
    os.getenv('ZOTERO_API_KEY')
)

INBOX_COLLECTION = '2PSBFJEI'

# 获取 inbox 中的所有条目（排除附件和笔记）
items = zot.everything(zot.collection_items(INBOX_COLLECTION, itemType='-attachment || note'))

print(f"Total items in inbox: {len(items)}\n")

# 检查每个条目是否有 PDF 附件
needs_pdf = []
has_pdf = []

for item in items:
    key = item['data']['key']
    doi = item['data'].get('DOI', '')
    title = item['data'].get('title', '')[:80]

    # 获取子条目（附件）
    children = zot.children(key)
    pdf_attachments = [c for c in children if c['data'].get('contentType') == 'application/pdf']

    if pdf_attachments:
        has_pdf.append({'key': key, 'doi': doi, 'title': title, 'pdf_count': len(pdf_attachments)})
    else:
        needs_pdf.append({'key': key, 'doi': doi, 'title': title})

print(f"Items WITH PDF: {len(has_pdf)}")
print(f"Items NEEDING PDF: {len(needs_pdf)}\n")

# 保存需要 PDF 的条目
with open('needs_pdf.json', 'w', encoding='utf-8') as f:
    json.dump(needs_pdf, f, ensure_ascii=False, indent=2)

print(f"Saved {len(needs_pdf)} items needing PDF to 'needs_pdf.json'")

# 打印前 10 个需要 PDF 的条目
print("\nFirst 10 items needing PDF:")
for i, item in enumerate(needs_pdf[:10], 1):
    print(f"{i}. {item['key']} | {item['doi'][:50] if item['doi'] else 'NO DOI'} | {item['title'][:60]}")
