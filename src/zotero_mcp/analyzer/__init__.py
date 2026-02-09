"""Zotero MCP analyzer: PDF paper analysis engine with LLM-powered analysis."""

from zotero_mcp.analyzer.analyzers.pdf_analyzer import PDFAnalyzer
from zotero_mcp.analyzer.extractors.pdf_extractor import PDFExtractor
from zotero_mcp.analyzer.models.checkpoint import CheckpointData
from zotero_mcp.analyzer.models.content import ImageBlock, PDFContent, TableBlock
from zotero_mcp.analyzer.models.result import AnalysisResult
from zotero_mcp.analyzer.models.template import AnalysisTemplate

__all__ = [
    "PDFContent",
    "ImageBlock",
    "TableBlock",
    "AnalysisResult",
    "AnalysisTemplate",
    "CheckpointData",
    "PDFExtractor",
    "PDFAnalyzer",
]

try:
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("zotero-mcp")
except PackageNotFoundError:
    __version__ = "unknown"
