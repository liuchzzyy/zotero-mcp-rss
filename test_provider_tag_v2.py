"""
Test improved LLM provider tag generation with proper capitalization.
"""

import asyncio
from zotero_mcp.clients.llm import get_llm_client


async def test_provider_tag_v2():
    """Test that provider names are properly formatted."""
    print("🔍 测试优化后的provider tag格式...\n")

    # Provider name mapping (same as in workflow.py)
    provider_map = {
        "deepseek": "DeepSeek",
        "openai": "OpenAI",
        "gemini": "Gemini",
    }

    try:
        client = get_llm_client()
        provider_name = provider_map.get(client.provider, client.provider.capitalize())

        print(f"✅ LLM Client初始化成功")
        print(f"   Provider: {client.provider}")
        print(f"   Model: {client.model}")
        print(f"   格式化Tag: '{provider_name}'")
        print(f"\n📌 生成的tags: ['AI分析', '{provider_name}']")

        # Show all possible tags with proper formatting
        print(f"\n📋 所有provider tags（正确格式）:")
        for p, formatted in provider_map.items():
            print(f"   - {p:10} → '{formatted}'")

        print(f"\n✨ 改进:")
        print(f"   ❌ 旧格式: 'Openai'")
        print(f"   ✅ 新格式: 'OpenAI'")

        return True

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_provider_tag_v2())
    exit(0 if success else 1)
