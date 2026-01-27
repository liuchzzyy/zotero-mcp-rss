"""
选项 3: 使用现有的 WorkflowService 批量工具

直接使用 zotero-mcp 内置的 WorkflowService，
这是最完整、最强大的批量分析解决方案。

Usage:
    # Method 1: Use .env file (recommended)
    cp .env.example .env  # Copy template and fill in your credentials
    uv run python examples/workflow_example.py
    
    # Method 2: Set environment variables directly
    ZOTERO_LIBRARY_ID=your_library_id \
    ZOTERO_API_KEY=your_api_key \
    DEEPSEEK_API_KEY=your_deepseek_api_key \
    uv run python examples/workflow_example.py

功能:
    ✅ 使用完整的 WorkflowService（生产级代码）
    ✅ 支持断点续传（Checkpoint 系统）
    ✅ 自动重试和错误处理
    ✅ 包含 PDF 批注提取
    ✅ 进度回调实时显示
    ✅ 结果自动保存为 Zotero 笔记
    ✅ 可恢复中断的工作流
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup path to import zotero_mcp modules
sys.path.insert(0, str(Path.cwd() / "src"))

from zotero_mcp.services.workflow import WorkflowService
from zotero_mcp.services.data_access import get_data_service


async def use_workflow_service():
    """使用完整的 WorkflowService 进行批量分析"""

    print("\n" + "=" * 70)
    print("选项 3: 使用 WorkflowService (生产级批量工具)")
    print("=" * 70 + "\n")

    # 检查环境变量
    required_vars = {
        "ZOTERO_LIBRARY_ID": os.getenv("ZOTERO_LIBRARY_ID"),
        "ZOTERO_API_KEY": os.getenv("ZOTERO_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    }

    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print("❌ 缺少必要的环境变量:")
        for var in missing:
            print(f"   - {var}")
        return

    # 配置
    COLLECTION_NAME = "1 - 中转过滤"
    MAX_ITEMS = 3

    print(f"📊 最大处理数量: {MAX_ITEMS}")
    print()

    try:
        # 初始化服务
        print("🔌 正在初始化 WorkflowService...")
        workflow_service = WorkflowService()
        data_service = get_data_service()
        print("✅ 服务初始化完成\n")

        # 查找收藏集
        print(f"🔍 正在查找收藏集: {COLLECTION_NAME}...")
        matches = await data_service.find_collection_by_name(COLLECTION_NAME)

        if not matches:
            print("❌ 未找到收藏集\n")
            return

        collection = matches[0]
        collection_name = collection.get("data", {}).get("name", "Unknown")
        collection_key = collection.get("data", {}).get("key", "")
        print(f"✅ 找到收藏集: {collection_name}")
        print(f"   Collection Key: {collection_key}\n")

        # 定义进度回调函数
        async def progress_callback(current: int, total: int, item_title: str):
            """实时显示进度"""
            percentage = (current / total * 100) if total > 0 else 0
            print(f"📊 进度: [{current}/{total}] ({percentage:.1f}%)")
            print(f"   当前条目: {item_title[:60]}...")
            print()

        # 使用 WorkflowService 进行批量分析
        print("🚀 开始批量分析...")
        print("   (使用 DeepSeek AI 模型)")
        print("   (包含 PDF 全文 + 批注)")
        print("   (支持断点续传)")
        print()

        result = await workflow_service.batch_analyze(
            source="collection",
            collection_key=collection_key,
            collection_name=None,  # 已有 key，不需要 name
            limit=MAX_ITEMS,
            skip_existing=True,  # 跳过已有笔记的条目
            include_annotations=True,  # 包含 PDF 批注
            llm_provider="deepseek",
            llm_model=None,  # 使用默认模型
            template=None,  # 使用默认中文学术模板
            dry_run=False,  # 实际执行，不是预览
            progress_callback=progress_callback,
        )

        # 显示结果
        print("=" * 70)
        print("📊 批量分析完成")
        print("=" * 70)
        print(f"   Workflow ID: {result.workflow_id}")
        print(f"   状态: {result.status}")
        print(f"   总条目数: {result.total_items}")
        print(f"   成功处理: {result.processed}")
        print(f"   跳过: {result.skipped}")
        print(f"   失败: {result.failed}")

        if result.can_resume:
            print(f"\n💡 工作流可恢复")
            print(f"   使用以下命令继续:")
            print(f'   resume_workflow_id="{result.workflow_id}"')

        if result.error:
            print(f"\n⚠️  错误信息: {result.error}")

        print()
        print("✨ 使用 WorkflowService 的优势:")
        print("   ✅ 生产级稳定性")
        print("   ✅ 自动断点续传")
        print("   ✅ 包含 PDF 批注")
        print("   ✅ 自动错误重试")
        print("   ✅ 完整的进度跟踪")
        print("   ✅ Checkpoint 状态管理")
        print()

        # 如果有失败的条目，可以继续执行
        if result.failed > 0 and result.can_resume:
            print("⚠️  有失败的条目，可以使用以下代码继续执行:")
            print()
            print("```python")
            print("result = await workflow_service.batch_analyze(")
            print(f'    resume_workflow_id="{result.workflow_id}",')
            print("    # 其他参数保持不变")
            print(")")
            print("```")
            print()

    except Exception as e:
        print(f"\n❌ 发生错误: {e}\n")
        import traceback

        traceback.print_exc()


async def list_workflows():
    """列出所有工作流状态（可选功能）"""
    print("\n" + "=" * 70)
    print("📋 查看所有工作流状态")
    print("=" * 70 + "\n")

    workflow_service = WorkflowService()

    # 获取所有工作流
    workflows = workflow_service.checkpoint_manager.list_workflows()

    if not workflows:
        print("   (暂无工作流记录)")
        return

    for wf in workflows:
        print(f"📌 Workflow ID: {wf.workflow_id}")
        print(f"   状态: {wf.status}")
        print(f"   总数: {wf.total_items}")
        print(f"   已处理: {len(wf.processed_keys)}")
        print(f"   失败: {len(wf.failed_keys)}")
        print(f"   创建时间: {wf.created_at}")
        print()


if __name__ == "__main__":
    # 主功能：批量分析
    asyncio.run(use_workflow_service())

    # 可选：列出所有工作流
    # asyncio.run(list_workflows())
