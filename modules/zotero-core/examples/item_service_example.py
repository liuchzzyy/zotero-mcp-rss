"""
Example usage of ItemService from zotero-core module.

This example demonstrates how to use the ItemService for basic
Zotero item operations.
"""

import asyncio
from zotero_core.services import ItemService
from zotero_core.models import ItemCreate, ItemUpdate


async def main():
    """Demonstrate ItemService usage."""

    # Initialize service with your Zotero credentials
    service = ItemService(
        library_id="your_library_id",
        api_key="your_api_key",
        library_type="user",  # or "group" for group libraries
    )

    # Example 1: Get an item
    print("Example 1: Getting an item...")
    try:
        item = await service.get_item("ABCD1234")
        if item:
            print(f"  Found: {item.title} by {', '.join(item.get_creator_names())}")
        else:
            print("  Item not found")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 2: Get all items with pagination
    print("\nExample 2: Getting items (batch)...")
    try:
        items = await service.get_all_items(limit=10)
        print(f"  Found {len(items)} items")
        for item in items[:3]:  # Show first 3
            print(f"    - {item.title}")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 3: Create a new item
    print("\nExample 3: Creating a new item...")
    try:
        new_item = ItemCreate(
            type="journalArticle",
            title="Example Paper",
            creators=[
                {"firstName": "Jane", "lastName": "Smith", "creatorType": "author"}
            ],
            abstract="This is an example paper created with zotero-core.",
            date="2024",
            tags=["example", "zotero-core"],
        )
        created = await service.create_item(new_item)
        print(f"  Created item with key: {created.key}")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 4: Update an item
    print("\nExample 4: Updating an item...")
    try:
        item_update = ItemUpdate(
            abstract="Updated abstract with new information.",
            tags=["example", "updated"],
        )
        updated = await service.update_item("ABCD1234", item_update)
        print(f"  Updated item: {updated.title}")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 5: Add tags to an item
    print("\nExample 5: Adding tags...")
    try:
        tagged = await service.add_tags("ABCD1234", ["new-tag", "another-tag"])
        print(f"  Tags after adding: {', '.join(tagged.tags)}")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 6: Remove tags from an item
    print("\nExample 6: Removing tags...")
    try:
        untagged = await service.remove_tags("ABCD1234", ["old-tag"])
        print(f"  Tags after removal: {', '.join(untagged.tags)}")
    except Exception as e:
        print(f"  Error: {e}")

    # Example 7: Delete an item
    print("\nExample 7: Deleting an item...")
    try:
        success = await service.delete_item("ABCD1234")
        print(f"  Deleted: {success}")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    print("Zotero-Core ItemService Example\n")
    print("=" * 50)
    asyncio.run(main())
