"""
上传下载的 PDF 到 Zotero
"""
from pyzotero import zotero
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Monkey-patch timeout for large files
_original_post = httpx.Client.post
def _patched_post(self, *args, **kwargs):
    kwargs['timeout'] = httpx.Timeout(240.0, connect=60.0)
    return _original_post(self, *args, **kwargs)
httpx.Client.post = _patched_post

zot = zotero.Zotero(
    os.getenv('ZOTERO_LIBRARY_ID'),
    os.getenv('ZOTERO_LIBRARY_TYPE'),
    os.getenv('ZOTERO_API_KEY')
)

# 下载的 PDF 文件映射到 Zotero item key
pdf_mapping = {
    'Gold-Nanofilms-at-Liquid–Liquid-Interfaces-An-Emerging-Platform-for-Redox-Electrocatalysis-Nanoplasmonic-Sensors-and-Electrov-科研通-ablesci-com-.pdf': '77IXL8DV',
}

download_dir = 'F:/ICMAB-Data/UAB-Thesis/zotero-mcp/.playwright-mcp/'

print(f"Starting PDF upload to Zotero...\n")

for filename, item_key in pdf_mapping.items():
    filepath = os.path.join(download_dir, filename)

    if not os.path.exists(filepath):
        print(f"❌ File not found: {filename}")
        continue

    try:
        print(f"⏳ Uploading {filename} -> item key: {item_key}")
        zot.attachment_simple([filepath], item_key)
        print(f"✅ Successfully uploaded: {filename}\n")

        # 上传成功后删除文件
        os.remove(filepath)
        print(f"   🗑️  Deleted local file: {filename}\n")

    except Exception as e:
        print(f"❌ Error uploading {filename}: {e}\n")

print("Done!")
