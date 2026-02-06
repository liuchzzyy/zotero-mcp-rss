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

## Analysis Templates

Three built-in templates:

| Template | Output | Multi-modal | Use Case |
|----------|--------|-------------|----------|
| `default` | Markdown | No | General paper analysis |
| `multimodal` | Markdown | Yes | Papers with figures/charts |
| `structured` | JSON | No | Programmatic processing |

```python
# Use structured template for JSON output
result = await analyzer.analyze("paper.pdf", template_name="structured")
# result.summary, result.key_points, result.methodology, result.conclusions

# Register custom template
from paper_analyzer.models import AnalysisTemplate
from paper_analyzer.templates import TemplateManager

custom = AnalysisTemplate(
    name="brief",
    system_prompt="Summarize in 3 sentences.",
    user_prompt_template="Summarize: {title}\n{text}",
    required_variables=["title", "text"],
)
mgr = TemplateManager()
mgr.register_template(custom)
```

## Development

```bash
cd modules/paper-analyzer
pip install -e ".[dev]"
pytest -v                    # Run tests
ruff check src/              # Lint
ruff format src/             # Format
```

## License

MIT License - see LICENSE file for details.
