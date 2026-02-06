# paper-analyzer

PDF paper analysis engine with multi-modal content extraction and LLM-powered analysis.

## Installation

```bash
pip install paper-analyzer
```

### With DeepSeek support
```bash
pip install paper-analyzer[deepseek]
```

### Full features
```bash
pip install paper-analyzer[all]
```

## Quick Start

```python
from paper_analyzer import PDFAnalyzer, PDFExtractor
from paper_analyzer.clients import DeepSeekClient

# Initialize
llm = DeepSeekClient(api_key="your-key")
analyzer = PDFAnalyzer(llm_client=llm)

# Analyze a paper
result = await analyzer.analyze("paper.pdf")
print(result.summary)
print(result.key_points)
```

## Features

- Fast PDF extraction (PyMuPDF) - 10x faster than pdfplumber
- Multi-modal support (text + images + tables)
- Multiple LLM providers (DeepSeek, OpenAI-compatible)
- Customizable analysis templates (default, multimodal, structured)
- Checkpoint-based batch processing with resume capability

## Architecture

```
paper-analyzer
├── extractors/     # PDF content extraction (PyMuPDF)
├── clients/        # LLM provider clients
├── analyzers/      # Analysis orchestration
├── templates/      # Analysis prompt templates
└── models/         # Pydantic data models
```
