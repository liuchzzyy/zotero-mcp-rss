"""paper-analyzer: PDF paper analysis engine with LLM-powered analysis."""

from paper_analyzer.models.content import PDFContent, ImageBlock, TableBlock
from paper_analyzer.models.result import AnalysisResult
from paper_analyzer.models.template import AnalysisTemplate
from paper_analyzer.models.checkpoint import CheckpointData
from paper_analyzer.extractors.pdf_extractor import PDFExtractor
from paper_analyzer.analyzers.pdf_analyzer import PDFAnalyzer

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

__version__ = "1.0.0"
