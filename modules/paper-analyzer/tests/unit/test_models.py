"""Tests for paper-analyzer models."""

from datetime import datetime

from paper_analyzer.models.content import ImageBlock, PDFContent, TableBlock
from paper_analyzer.models.result import AnalysisResult
from paper_analyzer.models.template import AnalysisTemplate
from paper_analyzer.models.checkpoint import CheckpointData


class TestPDFContent:
    def test_create_basic(self):
        content = PDFContent(file_path="test.pdf", total_pages=5)
        assert content.file_path == "test.pdf"
        assert content.total_pages == 5
        assert content.text == ""
        assert content.images == []
        assert content.tables == []

    def test_has_images(self):
        content = PDFContent(file_path="test.pdf", total_pages=1)
        assert not content.has_images

        content.images.append(
            ImageBlock(
                index=0,
                page_number=1,
                bbox=(0, 0, 100, 100),
                width=100,
                height=100,
            )
        )
        assert content.has_images

    def test_has_tables(self):
        content = PDFContent(file_path="test.pdf", total_pages=1)
        assert not content.has_tables

        content.tables.append(
            TableBlock(
                page_number=1, bbox=(0, 0, 100, 100), rows=3, cols=4
            )
        )
        assert content.has_tables

    def test_is_multimodal(self):
        content = PDFContent(file_path="test.pdf", total_pages=1)
        assert not content.is_multimodal

        content.images.append(
            ImageBlock(
                index=0,
                page_number=1,
                bbox=(0, 0, 100, 100),
                width=100,
                height=100,
            )
        )
        assert content.is_multimodal


class TestImageBlock:
    def test_create(self):
        img = ImageBlock(
            index=0,
            page_number=1,
            bbox=(10.0, 20.0, 300.0, 400.0),
            width=290.0,
            height=380.0,
            data_base64="abc123",
            format="png",
        )
        assert img.index == 0
        assert img.page_number == 1
        assert img.width == 290.0
        assert img.data_base64 == "abc123"


class TestTableBlock:
    def test_create(self):
        table = TableBlock(
            page_number=2,
            bbox=(0, 0, 500, 200),
            rows=5,
            cols=3,
            data=[["a", "b", "c"]],
        )
        assert table.rows == 5
        assert table.cols == 3
        assert len(table.data) == 1


class TestAnalysisTemplate:
    def test_render(self):
        template = AnalysisTemplate(
            name="test",
            system_prompt="You are a helper.",
            user_prompt_template="Analyze: {title}\n{text}",
            required_variables=["title", "text"],
        )
        result = template.render(title="My Paper", text="Content here")
        assert "My Paper" in result
        assert "Content here" in result

    def test_render_missing_variable(self):
        template = AnalysisTemplate(
            name="test",
            system_prompt="Helper",
            user_prompt_template="{title} {text}",
            required_variables=["title", "text"],
        )
        try:
            template.render(title="Only title")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "text" in str(e)

    def test_validate_output_json(self):
        template = AnalysisTemplate(
            name="test",
            system_prompt="",
            user_prompt_template="",
            output_format="json",
            output_schema={
                "type": "object",
                "required": ["summary"],
            },
        )
        assert template.validate_output('{"summary": "test"}')
        assert not template.validate_output("not json")
        assert not template.validate_output('{"other": "field"}')

    def test_validate_output_markdown(self):
        template = AnalysisTemplate(
            name="test",
            system_prompt="",
            user_prompt_template="",
            output_format="markdown",
        )
        assert template.validate_output("# Any markdown")


class TestAnalysisResult:
    def test_create(self):
        result = AnalysisResult(
            file_path="test.pdf",
            template_name="default",
            raw_output="Analysis text",
        )
        assert result.file_path == "test.pdf"
        assert result.summary == ""
        assert result.key_points == []
        assert result.processing_time == 0.0

    def test_with_parsed_fields(self):
        result = AnalysisResult(
            file_path="test.pdf",
            template_name="default",
            raw_output="raw",
            summary="A great paper",
            key_points=["Point 1", "Point 2"],
            methodology="ML approach",
            conclusions="It works",
        )
        assert len(result.key_points) == 2
        assert result.methodology == "ML approach"


class TestCheckpointData:
    def test_progress_percentage(self):
        cp = CheckpointData(
            task_id="task-1",
            started_at=datetime.now(),
            total_items=10,
            completed_items=3,
        )
        assert cp.progress_percentage == 30.0

    def test_is_completed(self):
        cp = CheckpointData(
            task_id="task-1",
            started_at=datetime.now(),
            total_items=5,
            completed_items=3,
            failed_items=1,
            skipped_items=1,
        )
        assert cp.is_completed

    def test_not_completed(self):
        cp = CheckpointData(
            task_id="task-1",
            started_at=datetime.now(),
            total_items=10,
            completed_items=3,
        )
        assert not cp.is_completed

    def test_zero_total(self):
        cp = CheckpointData(
            task_id="task-1",
            started_at=datetime.now(),
            total_items=0,
        )
        assert cp.progress_percentage == 0.0
