#!/usr/bin/env python3
"""
Gmail Integration Test Script

Tests Gmail API connection and basic operations.

Usage:
    python src/scripts/test_gmail.py

This script will:
1. Verify OAuth credentials are loaded
2. Test Gmail API connection
3. List recent emails (if no filters specified)
4. Test email search with filters
5. Display results
"""

import asyncio
import sys

try:
    from zotero_mcp.clients.gmail import GmailClient
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please run: uv sync")
    sys.exit(1)


async def test_connection(client: GmailClient) -> bool:
    """Test Gmail API connection."""
    print("=" * 60)
    print("🔌 Testing Gmail API Connection")
    print("=" * 60)
    print()

    try:
        # Try a simple search to test connection
        await client.search_messages(query="", max_results=1)
        print("✅ Connected to Gmail API")
        print("   Successfully queried Gmail")
        print()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        return False


async def test_search(client: GmailClient, max_results: int = 5):
    """Test email search."""
    print("=" * 60)
    print("🔍 Testing Email Search")
    print("=" * 60)
    print()

    try:
        # Search for recent emails (no filter)
        messages = await client.search_messages(query="", max_results=max_results)

        if not messages:
            print("⚠️  No emails found")
            return

        print(f"✅ Found {len(messages)} recent emails:")
        print()

        for i, msg in enumerate(messages[:max_results], 1):
            try:
                msg_id = msg["id"]
                headers = await client.get_message_headers(msg_id)
                subject = headers.get("Subject", "(no subject)")
                sender = headers.get("From", "(unknown sender)")
                date = headers.get("Date", "(no date)")

                print(f"{i}. {subject[:60]}...")
                print(f"   From: {sender}")
                print(f"   Date: {date}")
                print()

            except Exception as e:
                print(f"❌ Failed to read message {msg.get('id', 'unknown')}: {e}")
                print()

    except Exception as e:
        print(f"❌ Search failed: {e}")
        print()


async def test_search_with_filters(client: GmailClient):
    """Test email search with filters."""
    print("=" * 60)
    print("🎯 Testing Search with Filters")
    print("=" * 60)
    print()

    # Test various filters
    test_queries = [
        ("from:notifications@github.com", "GitHub notifications"),
        ("subject:(test OR trial)", "Subject with keywords"),
        ("has:attachment", "Emails with attachments"),
    ]

    for query, description in test_queries:
        try:
            messages = await client.search_messages(query=query, max_results=3)

            print(f"✅ Query: {description}")
            print(f"   Query string: '{query}'")
            print(f"   Results: {len(messages)}")

            if messages:
                # Show first result
                msg_id = messages[0]["id"]
                headers = await client.get_message_headers(msg_id)
                subject = headers.get("Subject", "(no subject)")
                print(f"   Example: {subject[:50]}...")

            print()

        except Exception as e:
            print(f"❌ Query failed ({description}): {e}")
            print()


async def test_email_body(client: GmailClient, message_id: str):
    """Test reading email body."""
    print("=" * 60)
    print("📧 Testing Email Body Extraction")
    print("=" * 60)
    print()

    try:
        html_body, text_body = await client.get_message_body(message_id)

        if text_body:
            text_preview = text_body[:200].replace("\n", " ")
            print(f"✅ Text body (preview): {text_preview}...")
            print()

        if html_body:
            html_preview = html_body[:200].replace("\n", " ")
            print(f"✅ HTML body (preview): {html_preview}...")
            print()

    except Exception as e:
        print(f"❌ Failed to read email body: {e}")
        print()


async def main():
    """Main test function."""
    print()
    print("🚀 Gmail Integration Test")
    print("=" * 60)
    print()

    # Initialize client
    try:
        client = GmailClient()
    except Exception as e:
        print(f"❌ Failed to initialize Gmail client: {e}")
        print()
        print("Please ensure you have:")
        print("  1. Run authorization: python src/scripts/gmail_auth.py")
        print("  2. Check token file exists: ~/.config/zotero-mcp/token.json")
        print()
        sys.exit(1)

    # Test connection
    if not await test_connection(client):
        print("❌ Cannot proceed with tests due to connection failure")
        sys.exit(1)

    # Test basic search
    await test_search(client, max_results=5)

    # Get one message ID for body test
    messages = await client.search_messages(query="", max_results=1)
    if messages:
        msg_id = messages[0]["id"]
        await test_email_body(client, msg_id)
    else:
        print("⚠️  No messages found for body extraction test")
        print()

    # Test filters
    print("ℹ️  Note: Filter tests may return no results if you don't have")
    print("   matching emails. This is normal.")
    print()
    await test_search_with_filters(client)

    # Summary
    print("=" * 60)
    print("✅ All Tests Completed")
    print("=" * 60)
    print()
    print("📝 Next Steps:")
    print("  1. If tests passed, Gmail integration is ready to use")
    print("  2. See docs/GMAIL-SETUP.md for usage examples")
    print("  3. Configure GitHub Actions if needed")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(0)
