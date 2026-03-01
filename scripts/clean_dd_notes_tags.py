"""
Delete note attachments and all tags from every item in 00_INBOXS_DD.
"""
import os
import sys
from dotenv import load_dotenv
from pyzotero import zotero

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LIBRARY_ID = os.environ["ZOTERO_LIBRARY_ID"]
API_KEY = os.environ["ZOTERO_API_KEY"]
COLLECTION_KEY = "G7AJ2X8Y"  # 00_INBOXS_DD

zot = zotero.Zotero(LIBRARY_ID, "user", API_KEY)

print(f"Fetching all items in 00_INBOXS_DD ({COLLECTION_KEY})...")
items = zot.everything(zot.collection_items(COLLECTION_KEY))
parent_items = [i for i in items if i["data"]["itemType"] != "note"
                and i["data"]["itemType"] != "attachment"]
print(f"Found {len(parent_items)} parent items.")

notes_deleted = 0
tags_cleared = 0
errors = 0

for idx, item in enumerate(parent_items, 1):
    key = item["data"]["key"]
    title = item["data"].get("title", "")[:60]
    changes = []

    # 1. Delete note children
    try:
        children = zot.children(key)
        notes = [c for c in children if c["data"]["itemType"] == "note"]
        for note in notes:
            zot.delete_item(note)
            notes_deleted += 1
            changes.append(f"deleted note {note['data']['key']}")
    except Exception as e:
        print(f"  [{idx}] ERROR getting/deleting notes for {key}: {e}")
        errors += 1

    # 2. Clear tags
    current_tags = item["data"].get("tags", [])
    if current_tags:
        try:
            item["data"]["tags"] = []
            zot.update_item(item)
            tags_cleared += 1
            changes.append(f"cleared {len(current_tags)} tags")
        except Exception as e:
            print(f"  [{idx}] ERROR clearing tags for {key}: {e}")
            errors += 1

    if changes:
        print(f"  [{idx}/{len(parent_items)}] {key} | {title} → {', '.join(changes)}")

print()
print("=== Done ===")
print(f"Notes deleted : {notes_deleted}")
print(f"Items tags cleared: {tags_cleared}")
print(f"Errors        : {errors}")
