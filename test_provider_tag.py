"""
Test LLM provider tag generation.
"""

import asyncio
from zotero_mcp.clients.llm import get_llm_client


async def test_provider_tag():
    """Test that provider name is correctly extracted."""
    print("🔍 测试LLM provider名称提取...\n")

    # Test auto-selection
    try:
        client = get_llm_client()
        provider_name = client.provider.capitalize()

        print(f"✅ LLM Client初始化成功")
        print(f"   Provider: {client.provider}")
        print(f"   Model: {client.model}")
        print(f"   Tag格式: '{provider_name}'")
        print(f"\n📌 生成的tags将是: ['AI分析', '{provider_name}']")

        # Show what tags would be created for each provider
        print(f"\n📋 所有可能的provider tags:")
        providers = ["deepseek", "openai", "gemini"]
        for p in providers:
            tag = p.capitalize()
            print(f"   - {p} → '{tag}'")

        return True

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_provider_tag())
    exit(0 if success else 1)
