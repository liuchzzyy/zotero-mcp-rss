# paper-analyzer 完整设计文档

**日期**: 2025-02-06
**状态**: 最终设计
**版本**: 1.0

## 概述

`paper-analyzer` 是一个独立的 PDF 论文分析引擎。提供 PDF 内容提取、多模态分析(文本+图像)、LLM 驱动的智能分析、批量处理和检查点恢复功能。

## 设计目标

1. **独立可用**: 可以独立安装和使用,不依赖 zotero-mcp
2. **多模态支持**: 支持文本、图像、表格的提取和分析
3. **LLM 灵活**: 支持多种 LLM 提供商(DeepSeek, OpenAI-compatible)
4. **可配置**: 分析模板可自定义,支持灵活的提示词工程
5. **可恢复**: 检查点机制支持大批量处理的中断恢复

## 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    paper-analyzer                         │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Extractors  │  │   Analyzers  │  │   Clients    │
│              │  │              │  │              │
│ • PDF文本    │  │ • LLM分析    │  │ • DeepSeek   │
│ • 图像提取   │  │ • 模板管理   │  │ • OpenAI     │
│ • 表格提取   │  │ • 批处理     │  │ (compatible) │
└──────────────┘  └──────────────┘  └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
                    ┌──────────────┐
                    │   Services   │
                    │              │
                    │ • Workflow   │
                    │ • Checkpoint │
                    └──────────────┘
```

## 核心数据模型

### PDFContent (PDF 内容)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ImageBlock(BaseModel):
    """图像块"""
    index: int = Field(..., description="图像索引")
    page_number: int = Field(..., description="页码")
    bbox: tuple[float, float, float, float] = Field(..., description="边界框 (x0, y0, x1, y1)")
    width: float = Field(..., description="宽度")
    height: float = Field(..., description="高度")
    data_base64: Optional[str] = Field(None, description="Base64 编码的图像数据")
    format: str = Field(default="png", description="图像格式")

class TableBlock(BaseModel):
    """表格块"""
    page_number: int = Field(..., description="页码")
    bbox: tuple[float, float, float, float] = Field(..., description="边界框")
    rows: int = Field(..., description="行数")
    cols: int = Field(..., description="列数")
    data: List[List[str]] = Field(default_factory=list, description="表格数据")
    markdown: Optional[str] = Field(None, description="Markdown 格式")

class PDFContent(BaseModel):
    """PDF 提取内容"""

    # 基础信息
    file_path: str = Field(..., description="PDF 文件路径")
    total_pages: int = Field(..., description="总页数")
    extracted_at: datetime = Field(default_factory=datetime.now, description="提取时间")

    # 文本内容
    text: str = Field(default="", description="全文文本")
    text_by_page: List[str] = Field(default_factory=list, description="按页分页的文本")

    # 多模态内容
    images: List[ImageBlock] = Field(default_factory=list, description="图像列表")
    tables: List[TableBlock] = Field(default_factory=list, description="表格列表")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="PDF 元数据")

    @property
    def has_images(self) -> bool:
        """是否有图像"""
        return len(self.images) > 0

    @property
    def has_tables(self) -> bool:
        """是否有表格"""
        return len(self.tables) > 0

    @property
    def is_multimodal(self) -> bool:
        """是否为多模态内容"""
        return self.has_images or self.has_tables
```

### AnalysisTemplate (分析模板)

```python
from typing import Dict, Any, List

class AnalysisTemplate(BaseModel):
    """分析模板配置"""

    # 基础信息
    name: str = Field(..., description="模板名称")
    description: str = Field(default="", description="模板描述")
    version: str = Field(default="1.0", description="模板版本")

    # 提示词配置
    system_prompt: str = Field(..., description="系统提示词")
    user_prompt_template: str = Field(..., description="用户提示词模板 (支持 {variables})")

    # 输出配置
    output_format: str = Field(default="markdown", description="输出格式: markdown, json, html")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="输出 JSON Schema")

    # 功能配置
    supports_multimodal: bool = Field(default=False, description="是否支持多模态输入")
    max_tokens: int = Field(default=4000, description="最大输出 token 数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")

    # 变量定义
    required_variables: List[str] = Field(default_factory=list, description="必需变量列表")
    optional_variables: List[str] = Field(default_factory=list, description="可选变量列表")

    def render(self, **kwargs) -> str:
        """渲染提示词模板"""
        # 检查必需变量
        missing_vars = [v for v in self.required_variables if v not in kwargs]
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")

        # 渲染模板
        return self.user_prompt_template.format(**kwargs)

    def validate_output(self, output: str) -> bool:
        """验证输出格式"""
        if self.output_format == "json" and self.output_schema:
            import json
            try:
                data = json.loads(output)
                # 简化的 schema 验证
                return all(key in data for key in self.output_schema.get("required", []))
            except json.JSONDecodeError:
                return False
        return True
```

### AnalysisResult (分析结果)

```python
class AnalysisResult(BaseModel):
    """分析结果"""

    # 基础信息
    file_path: str = Field(..., description="PDF 文件路径")
    template_name: str = Field(..., description="使用的模板名称")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="分析时间")

    # LLM 信息
    llm_provider: str = Field(..., description="LLM 提供商")
    model: str = Field(..., description="模型名称")

    # 输出内容
    summary: str = Field(default="", description="论文摘要")
    key_points: List[str] = Field(default_factory=list, description="关键点列表")
    methodology: str = Field(default="", description="方法论")
    conclusions: str = Field(default="", description="结论")

    # 原始输出
    raw_output: str = Field(..., description="LLM 原始输出")
    formatted_output: str = Field(default="", description="格式化后的输出")

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    # 性能指标
    tokens_used: int = Field(default=0, description="使用的 token 数")
    processing_time: float = Field(default=0.0, description="处理时间(秒)")
```

### CheckpointData (检查点数据)

```python
class CheckpointData(BaseModel):
    """检查点数据"""

    # 任务信息
    task_id: str = Field(..., description="任务 ID")
    started_at: datetime = Field(..., description="开始时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    # 进度信息
    total_items: int = Field(..., description="总条目数")
    completed_items: int = Field(default=0, description="已完成条目数")
    failed_items: int = Field(default=0, description="失败条目数")
    skipped_items: int = Field(default=0, description="跳过条目数")

    # 状态
    status: str = Field(default="running", description="状态: running, paused, completed, failed")

    # 详细记录
    completed: List[str] = Field(default_factory=list, description="已完成条目 ID 列表")
    failed: Dict[str, str] = Field(default_factory=dict, description="失败条目 ID -> 错误信息")
    skipped: List[str] = Field(default_factory=list, description="跳过条目 ID 列表")

    # 配置快照
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置快照")

    @property
    def progress_percentage(self) -> float:
        """进度百分比"""
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100

    @property
    def is_completed(self) -> bool:
        """是否完成"""
        return self.completed_items + self.failed_items + self.skipped_items >= self.total_items
```

## 提取器层

### PDFExtractor (PDF 提取器)

```python
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional, List
from ..models import PDFContent, ImageBlock, TableBlock

class PDFExtractor:
    """
    PDF 内容提取器 (基于 PyMuPDF)

    特点:
    - 快速: 比 pdfplumber 快 10 倍
    - 多模态: 支持文本、图像、表格提取
    - 灵活: 可选择提取内容类型
    """

    def __init__(
        self,
        extract_images: bool = True,
        extract_tables: bool = True,
        image_format: str = "png",
        image_dpi: int = 150
    ):
        """
        Args:
            extract_images: 是否提取图像
            extract_tables: 是否提取表格
            image_format: 图像格式 (png, jpeg)
            image_dpi: 图像 DPI (影响清晰度和文件大小)
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.image_format = image_format
        self.image_dpi = image_dpi

    async def extract(
        self,
        file_path: str,
        pages: Optional[List[int]] = None
    ) -> PDFContent:
        """
        提取 PDF 内容

        Args:
            file_path: PDF 文件路径
            pages: 要提取的页码列表 (None 提取全部)

        Returns:
            PDFContent 对象
        """
        doc = fitz.open(file_path)

        # 基础信息
        content = PDFContent(
            file_path=file_path,
            total_pages=doc.page_count,
            metadata=self._extract_metadata(doc)
        )

        # 逐页提取
        for page_num in range(doc.page_count):
            if pages and page_num + 1 not in pages:
                continue

            page = doc[page_num]

            # 提取文本
            page_text = page.get_text()
            content.text_by_page.append(page_text)
            content.text += page_text + "\n\n"

            # 提取图像
            if self.extract_images:
                images = self._extract_images(page, page_num)
                content.images.extend(images)

            # 提取表格
            if self.extract_tables:
                tables = self._extract_tables(page, page_num)
                content.tables.extend(tables)

        doc.close()
        return content

    def _extract_metadata(self, doc: fitz.Document) -> Dict[str, Any]:
        """提取 PDF 元数据"""
        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "keywords": doc.metadata.get("keywords", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
        }

        # 移除空值
        return {k: v for k, v in metadata.items() if v}

    def _extract_images(
        self,
        page: fitz.Page,
        page_num: int
    ) -> List[ImageBlock]:
        """提取页面图像"""
        images = []
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            xref = img[0]

            # 获取图像
            base_image = page.parent.extract_image(xref)

            # 图像元数据
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            # 获取位置信息
            try:
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    rect = img_rects[0]
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                else:
                    bbox = (0, 0, 0, 0)
            except:
                bbox = (0, 0, 0, 0)

            # 转换为 base64 (用于多模态 LLM)
            import base64
            data_base64 = base64.b64encode(image_bytes).decode("utf-8")

            image_block = ImageBlock(
                index=len(images),
                page_number=page_num + 1,
                bbox=bbox,
                width=base_image.get("width", 0),
                height=base_image.get("height", 0),
                data_base64=data_base64,
                format=image_ext
            )

            images.append(image_block)

        return images

    def _extract_tables(
        self,
        page: fitz.Page,
        page_num: int
    ) -> List[TableBlock]:
        """提取页面表格"""
        tables = []

        # PyMuPDF 不直接支持表格提取,这里使用启发式方法
        # 检测表格边框和结构

        # 查找所有线条
        horizontal_lines = []
        vertical_lines = []

        for drawing in page.get_drawings():
            path = drawing["path"]
            if path.rect.width > path.rect.height * 5:
                # 水平线
                horizontal_lines.append(path.rect.y0)
            elif path.rect.height > path.rect.width * 5:
                # 垂直线
                vertical_lines.append(path.rect.x0)

        # 如果有足够的线条,可能是表格
        if len(horizontal_lines) > 2 and len(vertical_lines) > 2:
            # 简化的表格检测
            # 实际应用中可能需要更复杂的算法或使用 pdfplumber

            # 按 y 和 x 坐标排序
            horizontal_lines = sorted(set(horizontal_lines))
            vertical_lines = sorted(set(vertical_lines))

            rows = len(horizontal_lines) - 1
            cols = len(vertical_lines) - 1

            if rows > 0 and cols > 0:
                # 提取表格区域文本
                table_bbox = (
                    min(vertical_lines),
                    min(horizontal_lines),
                    max(vertical_lines),
                    max(horizontal_lines)
                )

                table = TableBlock(
                    page_number=page_num + 1,
                    bbox=table_bbox,
                    rows=rows,
                    cols=cols,
                    data=[],  # 简化,不提取单元格内容
                    markdown=""  # 简化
                )
                tables.append(table)

        return tables

    async def extract_text_only(self, file_path: str) -> str:
        """
        仅提取文本 (快速模式)

        Args:
            file_path: PDF 文件路径

        Returns:
            全文文本
        """
        doc = fitz.open(file_path)
        text = ""

        for page in doc:
            text += page.get_text() + "\n\n"

        doc.close()
        return text
```

## LLM 客户端层

### BaseLLMClient (LLM 客户端基类)

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "default",
        max_tokens: int = 4000,
        temperature: float = 0.7
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @abstractmethod
    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        发送分析请求

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            images: 图像 base64 列表 (用于多模态)
            **kwargs: 额外参数

        Returns:
            LLM 响应文本
        """
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        """是否支持视觉能力(多模态)"""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        pass
```

### OpenAIClient (OpenAI-compatible 客户端)

```python
import httpx
from typing import List, Optional
from .base import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    """
    OpenAI API 客户端 (兼容 DeepSeek 等)

    支持任何 OpenAI-compatible API
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = 120
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        self.timeout = timeout

    async def analyze(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """发送分析请求"""

        # 构建消息
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 用户消息
        if images and self.supports_vision():
            # 多模态消息
            content = [
                {"type": "text", "text": prompt}
            ]

            for img_base64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })

            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # 纯文本消息
            messages.append({
                "role": "user",
                "content": prompt
            })

        # API 请求
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature)
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # 提取响应
        return data["choices"][0]["message"]["content"]

    def supports_vision(self) -> bool:
        """检测是否支持视觉能力"""
        vision_models = {
            "gpt-4o", "gpt-4-vision-preview", "gpt-4o-mini",
            "claude-3", "claude-3.5", "gemini-pro-vision"
        }
        return any(model in self.model.lower() for model in vision_models)

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "supports_vision": self.supports_vision(),
            "max_tokens": self.max_tokens
        }
```

### DeepSeekClient (DeepSeek 客户端)

```python
from .openai import OpenAIClient

class DeepSeekClient(OpenAIClient):
    """
    DeepSeek API 客户端

    DeepSeek 使用 OpenAI-compatible API
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com/v1",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = 120
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout
        )

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": "deepseek",
            "model": self.model,
            "base_url": self.base_url,
            "supports_vision": False,  # DeepSeek 当前不支持视觉
            "max_tokens": self.max_tokens
        }
```

## 分析器层

### PDFAnalyzer (PDF 分析器)

```python
import time
from typing import Optional, List
from pathlib import Path
from .extractors.pdf_extractor import PDFExtractor
from .clients.base import BaseLLMClient
from .templates.template_manager import TemplateManager
from ..models import PDFContent, AnalysisResult, AnalysisTemplate

class PDFAnalyzer:
    """
    PDF 分析器

    职责:
    1. 提取 PDF 内容
    2. 选择合适的模板
    3. 调用 LLM 分析
    4. 格式化输出
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        template_manager: Optional[TemplateManager] = None,
        extractor: Optional[PDFExtractor] = None
    ):
        """
        Args:
            llm_client: LLM 客户端
            template_manager: 模板管理器 (默认使用内置模板)
            extractor: PDF 提取器 (默认使用默认配置)
        """
        self.llm_client = llm_client
        self.template_manager = template_manager or TemplateManager()
        self.extractor = extractor or PDFExtractor()

    async def analyze(
        self,
        file_path: str,
        template_name: str = "default",
        template: Optional[AnalysisTemplate] = None,
        extract_images: bool = True,
        extract_tables: bool = False
    ) -> AnalysisResult:
        """
        分析 PDF 文件

        Args:
            file_path: PDF 文件路径
            template_name: 模板名称 (如果 template 为 None)
            template: 自定义模板 (优先级高于 template_name)
            extract_images: 是否提取图像
            extract_tables: 是否提取表格

        Returns:
            AnalysisResult 对象
        """
        start_time = time.time()

        # 1. 选择模板
        if template is None:
            template = self.template_manager.get_template(template_name)

        # 2. 提取内容
        content = await self.extractor.extract(
            file_path=file_path,
            extract_images=extract_images,
            extract_tables=extract_tables
        )

        # 3. 构建提示词
        system_prompt = template.system_prompt
        user_prompt = self._build_prompt(template, content)

        # 4. 准备多模态输入
        images = None
        if template.supports_multimodal and content.has_images:
            images = [img.data_base64 for img in content.images[:10]]  # 限制图像数量

        # 5. 调用 LLM
        try:
            raw_output = await self.llm_client.analyze(
                prompt=user_prompt,
                system_prompt=system_prompt,
                images=images,
                max_tokens=template.max_tokens,
                temperature=template.temperature
            )
        except Exception as e:
            raise RuntimeError(f"LLM analysis failed: {e}")

        # 6. 解析输出
        result = self._parse_result(
            file_path=file_path,
            template_name=template.name,
            raw_output=raw_output,
            content=content,
            template=template
        )

        # 7. 记录性能
        result.processing_time = time.time() - start_time
        result.llm_provider = self.llm_client.get_model_info()["provider"]
        result.model = self.llm_client.model

        return result

    def _build_prompt(
        self,
        template: AnalysisTemplate,
        content: PDFContent
    ) -> str:
        """构建提示词"""
        # 准备变量
        variables = {
            "title": content.metadata.get("title", Path(content.file_path).stem),
            "text": content.text[:10000],  # 截断过长文本
            "page_count": content.total_pages,
            "has_images": content.has_images,
            "has_tables": content.has_tables,
            "image_count": len(content.images),
            "table_count": len(content.tables),
        }

        # 渲染模板
        return template.render(**variables)

    def _parse_result(
        self,
        file_path: str,
        template_name: str,
        raw_output: str,
        content: PDFContent,
        template: AnalysisTemplate
    ) -> AnalysisResult:
        """解析 LLM 输出"""
        result = AnalysisResult(
            file_path=file_path,
            template_name=template_name,
            raw_output=raw_output
        )

        # 根据输出格式解析
        if template.output_format == "json":
            try:
                import json
                data = json.loads(raw_output)

                result.summary = data.get("summary", "")
                result.key_points = data.get("key_points", [])
                result.methodology = data.get("methodology", "")
                result.conclusions = data.get("conclusions", "")

                result.formatted_output = json.dumps(data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                # JSON 解析失败,保留原始输出
                result.formatted_output = raw_output

        elif template.output_format == "markdown":
            # 解析 Markdown
            lines = raw_output.split("\n")

            current_section = None
            current_content = []

            for line in lines:
                if line.startswith("## "):
                    # 保存上一个 section
                    if current_section == "摘要":
                        result.summary = "\n".join(current_content).strip()
                    elif current_section == "关键点":
                        result.key_points = [
                            l.strip().lstrip("-*").strip()
                            for l in current_content if l.strip()
                        ]
                    elif current_section == "方法论":
                        result.methodology = "\n".join(current_content).strip()
                    elif current_section == "结论":
                        result.conclusions = "\n".join(current_content).strip()

                    # 开始新 section
                    current_section = line[3:].strip()
                    current_content = []
                else:
                    current_content.append(line)

            # 保存最后一个 section
            if current_section == "摘要":
                result.summary = "\n".join(current_content).strip()
            elif current_section == "关键点":
                result.key_points = [
                    l.strip().lstrip("-*").strip()
                    for l in current_content if l.strip()
                ]
            elif current_section == "方法论":
                result.methodology = "\n".join(current_content).strip()
            elif current_section == "结论":
                result.conclusions = "\n".join(current_content).strip()

            result.formatted_output = raw_output

        else:  # text or html
            result.formatted_output = raw_output
            result.summary = raw_output[:500]  # 前 500 字符作为摘要

        return result
```

### TemplateManager (模板管理器)

```python
from typing import Dict, Optional, List
from pathlib import Path
import json
import yaml
from ..models import AnalysisTemplate

class TemplateManager:
    """
    分析模板管理器

    支持内置模板和自定义模板
    """

    # 内置模板
    BUILTIN_TEMPLATES = {
        "default": AnalysisTemplate(
            name="default",
            description="默认论文分析模板",
            version="1.0",
            system_prompt="你是一个专业的学术论文分析助手。请分析提供的论文内容,提取关键信息。",
            user_prompt_template="""请分析以下论文:

标题: {title}
页数: {page_count}

论文内容:
{text}

请提供以下信息:
1. 研究摘要
2. 关键创新点 (3-5个)
3. 研究方法
4. 主要结论

以 Markdown 格式输出。""",
            output_format="markdown",
            supports_multimodal=False,
            max_tokens=2000,
            temperature=0.7,
            required_variables=["title", "text"],
            optional_variables=["page_count", "has_images", "has_tables"]
        ),

        "multimodal": AnalysisTemplate(
            name="multimodal",
            description="多模态论文分析模板(支持图像)",
            version="1.0",
            system_prompt="你是一个专业的学术论文分析助手,具备理解图像和图表的能力。",
            user_prompt_template="""请分析以下论文(包含图像):

标题: {title}
页数: {page_count}
图像数量: {image_count}

论文内容:
{text}

请结合论文中的图像、图表,提供详细分析。""",
            output_format="markdown",
            supports_multimodal=True,
            max_tokens=3000,
            temperature=0.7,
            required_variables=["title", "text"],
            optional_variables=["page_count", "image_count"]
        ),

        "structured": AnalysisTemplate(
            name="structured",
            description="结构化输出模板(JSON格式)",
            version="1.0",
            system_prompt="你是一个专业的学术论文分析助手。请以结构化 JSON 格式输出分析结果。",
            user_prompt_template="""请分析以下论文并提供 JSON 格式的输出:

标题: {title}
内容: {text}

输出格式:
{
  "summary": "研究摘要",
  "key_points": ["关键点1", "关键点2", ...],
  "methodology": "研究方法",
  "conclusions": "主要结论",
  "relevance_score": 0.8
}""",
            output_format="json",
            output_schema={
                "type": "object",
                "required": ["summary", "key_points", "methodology", "conclusions"]
            },
            supports_multimodal=False,
            max_tokens=2000,
            temperature=0.5,
            required_variables=["title", "text"]
        )
    }

    def __init__(self, custom_templates_dir: Optional[Path] = None):
        """
        Args:
            custom_templates_dir: 自定义模板目录路径
        """
        self.custom_templates_dir = custom_templates_dir
        self.custom_templates: Dict[str, AnalysisTemplate] = {}

        # 加载自定义模板
        if custom_templates_dir and custom_templates_dir.exists():
            self._load_custom_templates()

    def get_template(self, name: str) -> AnalysisTemplate:
        """获取模板"""
        # 优先返回自定义模板
        if name in self.custom_templates:
            return self.custom_templates[name]

        # 返回内置模板
        if name in self.BUILTIN_TEMPLATES:
            return self.BUILTIN_TEMPLATES[name]

        raise ValueError(f"Template not found: {name}")

    def list_templates(self) -> List[str]:
        """列出所有可用模板"""
        builtin = list(self.BUILTIN_TEMPLATES.keys())
        custom = list(self.custom_templates.keys())
        return builtin + custom

    def register_template(self, template: AnalysisTemplate) -> None:
        """注册自定义模板"""
        self.custom_templates[template.name] = template

    def save_template(self, template: AnalysisTemplate, file_path: Path) -> None:
        """保存模板到文件"""
        data = template.model_dump()

        # 根据文件扩展名选择格式
        if file_path.suffix == ".json":
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif file_path.suffix in [".yaml", ".yml"]:
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

    def load_template(self, file_path: Path) -> AnalysisTemplate:
        """从文件加载模板"""
        # 根据文件扩展名选择格式
        if file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif file_path.suffix in [".yaml", ".yml"]:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        return AnalysisTemplate(**data)

    def _load_custom_templates(self) -> None:
        """加载自定义模板目录中的所有模板"""
        for file_path in self.custom_templates_dir.glob("*.json"):
            try:
                template = self.load_template(file_path)
                self.custom_templates[template.name] = template
            except Exception as e:
                print(f"Warning: Failed to load template {file_path}: {e}")

        for file_path in self.custom_templates_dir.glob("*.yaml"):
            try:
                template = self.load_template(file_path)
                self.custom_templates[template.name] = template
            except Exception as e:
                print(f"Warning: Failed to load template {file_path}: {e}")
```

## 服务层

### CheckpointService (检查点服务)

```python
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from ..models import CheckpointData

class CheckpointService:
    """
    检查点服务

    负责保存和恢复任务进度
    """

    def __init__(self, checkpoint_dir: Path):
        """
        Args:
            checkpoint_dir: 检查点文件目录
        """
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, task_id: str) -> Path:
        """获取检查点文件路径"""
        return self.checkpoint_dir / f"{task_id}.json"

    async def save(self, checkpoint: CheckpointData) -> None:
        """保存检查点"""
        checkpoint.updated_at = datetime.now()

        file_path = self.get_checkpoint_path(checkpoint.task_id)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.model_dump(), f, indent=2, ensure_ascii=False)

    async def load(self, task_id: str) -> Optional[CheckpointData]:
        """加载检查点"""
        file_path = self.get_checkpoint_path(task_id)

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CheckpointData(**data)

    async def delete(self, task_id: str) -> bool:
        """删除检查点"""
        file_path = self.get_checkpoint_path(task_id)

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def list_checkpoints(self) -> List[str]:
        """列出所有检查点"""
        return [
            f.stem for f in self.checkpoint_dir.glob("*.json")
        ]
```

### WorkflowService (工作流服务)

```python
import asyncio
from typing import List, Optional, Callable, Dict, Any
from pathlib import Path
from .analyzers.pdf_analyzer import PDFAnalyzer
from .checkpoint_service import CheckpointService
from ..models import CheckpointData, AnalysisResult

class WorkflowService:
    """
    批量分析工作流服务

    特性:
    - 批量处理多个 PDF
    - 检查点恢复
    - 错误处理和重试
    - 进度回调
    """

    def __init__(
        self,
        analyzer: PDFAnalyzer,
        checkpoint_service: CheckpointService
    ):
        """
        Args:
            analyzer: PDF 分析器
            checkpoint_service: 检查点服务
        """
        self.analyzer = analyzer
        self.checkpoint_service = checkpoint_service

    async def batch_analyze(
        self,
        file_paths: List[str],
        task_id: str,
        template_name: str = "default",
        resume: bool = True,
        max_retries: int = 2,
        progress_callback: Optional[Callable[[CheckpointData], None]] = None,
        delay_between_items: float = 1.0
    ) -> List[AnalysisResult]:
        """
        批量分析 PDF 文件

        Args:
            file_paths: PDF 文件路径列表
            task_id: 任务 ID (用于检查点)
            template_name: 分析模板名称
            resume: 是否从检查点恢复
            max_retries: 最大重试次数
            progress_callback: 进度回调函数
            delay_between_items: 条目间延迟(秒)

        Returns:
            AnalysisResult 列表
        """
        # 1. 尝试从检查点恢复
        checkpoint = None
        if resume:
            checkpoint = await self.checkpoint_service.load(task_id)

        # 2. 创建新检查点
        if checkpoint is None:
            checkpoint = CheckpointData(
                task_id=task_id,
                started_at=datetime.now(),
                total_items=len(file_paths),
                config={
                    "template_name": template_name,
                    "max_retries": max_retries
                }
            )

        # 3. 过滤已完成的文件
        pending_files = [
            f for f in file_paths
            if f not in checkpoint.completed
        ]

        results = []

        # 4. 批量处理
        for file_path in pending_files:
            # 检查是否已完成
            if checkpoint.is_completed:
                break

            # 带重试的分析
            result = await self._analyze_with_retry(
                file_path=file_path,
                template_name=template_name,
                max_retries=max_retries
            )

            if result:
                results.append(result)
                checkpoint.completed.append(file_path)
                checkpoint.completed_items += 1
            else:
                checkpoint.failed[file_path] = "Max retries exceeded"
                checkpoint.failed_items += 1

            # 保存检查点
            await self.checkpoint_service.save(checkpoint)

            # 进度回调
            if progress_callback:
                progress_callback(checkpoint)

            # 延迟
            await asyncio.sleep(delay_between_items)

        # 5. 更新状态
        checkpoint.status = "completed"
        await self.checkpoint_service.save(checkpoint)

        return results

    async def _analyze_with_retry(
        self,
        file_path: str,
        template_name: str,
        max_retries: int
    ) -> Optional[AnalysisResult]:
        """带重试的分析"""
        for attempt in range(max_retries + 1):
            try:
                result = await self.analyzer.analyze(
                    file_path=file_path,
                    template_name=template_name
                )
                return result

            except Exception as e:
                if attempt >= max_retries:
                    print(f"Failed after {max_retries} retries: {file_path} - {e}")
                    return None

                # 等待后重试
                await asyncio.sleep(2 ** attempt)  # 指数退避

        return None

    async def get_progress(self, task_id: str) -> Optional[CheckpointData]:
        """获取任务进度"""
        return await self.checkpoint_service.load(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        checkpoint = await self.checkpoint_service.load(task_id)
        if checkpoint:
            checkpoint.status = "cancelled"
            await self.checkpoint_service.save(checkpoint)
            return True
        return False
```

## CLI 工具

```python
import click
from pathlib import Path
from .analyzers.pdf_analyzer import PDFAnalyzer
from .clients.openai import OpenAIClient
from .clients.deepseek import DeepSeekClient
from .templates.template_manager import TemplateManager
from .services.checkpoint_service import CheckpointService
from .services.workflow_service import WorkflowService

@click.group()
@click.option('--api-key', envvar='LLM_API_KEY', required=True)
@click.option('--provider', type=click.Choice(['openai', 'deepseek']), default='deepseek')
@click.option('--model', default='deepseek-chat')
@click.option('--base-url', default=None)
@click.pass_context
def cli(ctx, api_key, provider, model, base_url):
    """paper-analyzer CLI"""
    ctx.ensure_object(dict)

    # 初始化 LLM 客户端
    if provider == 'openai':
        llm_client = OpenAIClient(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model
        )
    else:  # deepseek
        llm_client = DeepSeekClient(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.deepseek.com/v1"
        )

    ctx.obj['llm_client'] = llm_client
    ctx.obj['template_manager'] = TemplateManager()

@cli.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--template', '-t', default='default', help='Analysis template')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.option('--no-images', is_flag=True, help='Do not extract images')
@click.pass_context
def analyze(ctx, pdf_path, template, output, no_images):
    """Analyze a single PDF file"""
    llm_client = ctx.obj['llm_client']
    template_manager = ctx.obj['template_manager']

    # 初始化分析器
    analyzer = PDFAnalyzer(
        llm_client=llm_client,
        template_manager=template_manager
    )

    # 分析
    click.echo(f"Analyzing {pdf_path}...")
    result = click.Path(async=True).run(analyzer.analyze(
        file_path=pdf_path,
        template_name=template,
        extract_images=not no_images
    ))

    # 输出
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(result.formatted_output)
        click.echo(f"Output saved to {output}")
    else:
        click.echo(result.formatted_output)

@cli.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
@click.option('--pattern', default='*.pdf', help='File pattern')
@click.option('--template', '-t', default='default', help='Analysis template')
@click.option('--task-id', required=True, help='Task ID for checkpointing')
@click.option('--resume', is_flag=True, help='Resume from checkpoint')
@click.pass_context
def batch(ctx, directory, pattern, template, task_id, resume):
    """Batch analyze PDF files in a directory"""
    llm_client = ctx.obj['llm_client']
    template_manager = ctx.obj['template_manager']

    # 初始化服务
    analyzer = PDFAnalyzer(
        llm_client=llm_client,
        template_manager=template_manager
    )

    checkpoint_dir = Path(".paper-analyzer/checkpoints")
    checkpoint_service = CheckpointService(checkpoint_dir=checkpoint_dir)
    workflow_service = WorkflowService(
        analyzer=analyzer,
        checkpoint_service=checkpoint_service
    )

    # 查找 PDF 文件
    pdf_files = list(Path(directory).glob(pattern))

    click.echo(f"Found {len(pdf_files)} PDF files")

    # 进度回调
    def progress_callback(checkpoint):
        progress = checkpoint.progress_percentage
        click.echo(f"Progress: {progress:.1f}% ({checkpoint.completed_items}/{checkpoint.total_items})")

    # 批量分析
    results = click.Path(async=True).run(workflow_service.batch_analyze(
        file_paths=[str(f) for f in pdf_files],
        task_id=task_id,
        template_name=template,
        resume=resume,
        progress_callback=progress_callback
    ))

    click.echo(f"Completed: {len(results)} files analyzed")

@cli.command()
@click.pass_context
def list_templates(ctx):
    """List available templates"""
    template_manager = ctx.obj['template_manager']

    templates = template_manager.list_templates()

    click.echo("Available templates:")
    for name in templates:
        template = template_manager.get_template(name)
        click.echo(f"  - {name}: {template.description}")

def main():
    cli(obj={})

if __name__ == '__main__':
    main()
```

## 使用示例

### 单文件分析

```python
from paper_analyzer import PDFAnalyzer, DeepSeekClient

# 初始化
llm_client = DeepSeekClient(api_key="your_api_key")
analyzer = PDFAnalyzer(llm_client=llm_client)

# 分析
result = await analyzer.analyze(
    file_path="paper.pdf",
    template_name="default",
    extract_images=False
)

# 输出
print(f"Summary: {result.summary}")
print(f"Key Points: {result.key_points}")
print(f"Processing Time: {result.processing_time:.2f}s")
```

### 批量分析

```python
from paper_analyzer import PDFAnalyzer, DeepSeekClient, WorkflowService, CheckpointService
from pathlib import Path

# 初始化
llm_client = DeepSeekClient(api_key="your_api_key")
analyzer = PDFAnalyzer(llm_client=llm_client)
checkpoint_service = CheckpointService(checkpoint_dir=Path("./checkpoints"))
workflow_service = WorkflowService(
    analyzer=analyzer,
    checkpoint_service=checkpoint_service
)

# 查找文件
pdf_files = [
    "paper1.pdf",
    "paper2.pdf",
    "paper3.pdf"
]

# 批量分析
results = await workflow_service.batch_analyze(
    file_paths=pdf_files,
    task_id="batch_001",
    template_name="default",
    resume=True  # 支持中断恢复
)

print(f"Analyzed {len(results)} papers")
```

### 自定义模板

```python
from paper_analyzer import AnalysisTemplate, TemplateManager

# 创建自定义模板
custom_template = AnalysisTemplate(
    name="citation_analysis",
    description="引用分析模板",
    version="1.0",
    system_prompt="你是一个学术论文引用分析专家。",
    user_prompt_template="""请分析以下论文的引用情况:

标题: {title}
内容: {text}

请提供:
1. 主要引用的论文列表
2. 引用数量统计
3. 引用时间分布
4. 引用的研究领域分布""",
    output_format="markdown",
    supports_multimodal=False,
    max_tokens=2000,
    temperature=0.5,
    required_variables=["title", "text"]
)

# 注册模板
template_manager = TemplateManager()
template_manager.register_template(custom_template)

# 使用自定义模板
analyzer = PDFAnalyzer(llm_client=llm_client, template_manager=template_manager)
result = await analyzer.analyze("paper.pdf", template_name="citation_analysis")
```

## 依赖配置

```toml
[project]
name = "paper-analyzer"
version = "1.0.0"
description = "PDF paper analysis engine with LLM"
dependencies = [
    "PyMuPDF>=1.23.0",
    "pydantic>=2.0.0",
    "httpx>=0.25.0",
    "click>=8.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
deepseek = ["openai>=1.0.0"]  # DeepSeek uses OpenAI-compatible API
openai = ["openai>=1.0.0"]
all = ["paper-analyzer[deepseek,openai]"]

[project.scripts]
paper-analyzer = "paper_analyzer.cli:main"
```

## 实施计划(5周)

### Week 1: 核心模型 + 提取器
- [ ] 实现 PDFContent, AnalysisTemplate, AnalysisResult, CheckpointData 模型
- [ ] 实现 PDFExtractor (PyMuPDF)
- [ ] 实现文本、图像提取
- [ ] 单元测试

### Week 2: LLM 客户端 + 分析器
- [ ] 实现 BaseLLMClient, OpenAIClient, DeepSeekClient
- [ ] 实现 PDFAnalyzer
- [ ] 实现多模态分析支持
- [ ] 测试 LLM 调用

### Week 3: 模板系统
- [ ] 实现 TemplateManager
- [ ] 实现内置模板 (default, multimodal, structured)
- [ ] 实现自定义模板加载/保存
- [ ] 模板验证和渲染

### Week 4: 工作流和检查点
- [ ] 实现 CheckpointService
- [ ] 实现 WorkflowService
- [ ] 实现批量处理和恢复
- [ ] 进度跟踪和回调

### Week 5: CLI + 文档
- [ ] 实现命令行接口
- [ ] 编写使用示例
- [ ] 编写 README 和 API 文档
- [ ] 性能优化和测试覆盖率 > 80%

---

**文档版本**: 1.0 (最终版)
**最后更新**: 2025-02-06