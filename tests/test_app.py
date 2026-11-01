import json
import unittest
from io import BytesIO
from pathlib import Path

from docx import Document
from streamlit.testing.v1 import AppTest


def _docx_bytes(name: str) -> bytes:
    doc = Document()
    doc.add_paragraph(f"原告：{name}，住北京市朝阳区建国路88号。")
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _docx_with_text(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


class AppBatchUploadTests(unittest.TestCase):
    def test_manual_terms_are_applied_from_ui(self):
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "app.py"),
            default_timeout=30,
        ).run()

        app.get("file_uploader")[0].set_value(
            (
                "manual.docx",
                _docx_with_text("案件备注：星河计划。核验码：ZX-7788。"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        ).run()
        app.text_area(key="custom_terms").set_value("星河计划\nZX-7788").run()
        app.button(key="start_btn").click().run()

        self.assertEqual(app.exception, [])
        result = app.session_state["results"][0]
        self.assertTrue(result.success, result.error)
        cleaned = Document(result.output_file).paragraphs[0].text
        self.assertNotIn("星河计划", cleaned)
        self.assertNotIn("ZX-7788", cleaned)

    def test_same_named_uploads_are_both_processed(self):
        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "app.py"),
            default_timeout=30,
        ).run()

        uploads = [
            (
                "起诉状.docx",
                _docx_bytes("张三"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                "起诉状.docx",
                _docx_bytes("李四"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ]
        app.get("file_uploader")[0].set_value(uploads).run()
        app.button(key="start_btn").click().run()

        self.assertEqual(app.exception, [])
        results = app.session_state["results"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.success for result in results))

        mapped_names = set()
        for result in results:
            mapping = json.loads(
                Path(result.mapping_file).read_text(encoding="utf-8")
            )
            mapped_names.update(mapping.values())

        self.assertIn("张三", mapped_names)
        self.assertIn("李四", mapped_names)


if __name__ == "__main__":
    unittest.main()
