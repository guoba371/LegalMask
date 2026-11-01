import json
import os
import re
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

import pymupdf
import numpy as np
from docx import Document
from docx.shared import Pt
from PIL import Image, ImageDraw, ImageFont

from core.processor import (
    _clean_sensitive_info,
    _extract_text_docx,
    _get_ocr_engine,
    batch_process,
    process_document,
    restore_text,
)


def _cjk_font() -> str | None:
    candidates = [
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    return next((path for path in candidates if os.path.exists(path)), None)


class TextRedactionTests(unittest.TestCase):
    def test_text_redacts_all_supported_entities_and_restores_them(self):
        text = (
            "原告：张三，男，1985年3月12日出生，住北京市朝阳区建国路88号。\n"
            "被告：李四，男，住上海市浦东新区世纪大道100号。\n"
            "原告张三与被告李四于2023年5月1日签订《借款合同》，约定借款100000元。\n"
            "（2023）京0105民初12345号\n"
            "身份证号：110105198503121234，手机号：13800138000。\n"
            "开户行：中国工商银行北京朝阳支行，账号：6222021234567890123。\n"
            "指派翁雪娟 律师为代理人，联系电话：0755-33246689。\n"
            "联系地址：广东省海丰县海城镇北社区居民委员会新北苑一巷58号\n"
            "根据《中华人民共和国民法典》第667条，被告李四应当偿还。"
        )

        cleaned, mapping = _clean_sensitive_info(text)

        for value in (
            "张三",
            "李四",
            "1985年3月12日",
            "2023年5月1日",
            "北京市朝阳区建国路88号",
            "上海市浦东新区世纪大道100号",
            "100000元",
            "（2023）京0105民初12345号",
            "110105198503121234",
            "13800138000",
            "中国工商银行北京朝阳支行",
            "6222021234567890123",
            "翁雪娟",
            "0755-33246689",
            "广东省海丰县海城镇北社区居民委员会新北苑一巷58号",
        ):
            self.assertNotIn(value, cleaned)

        self.assertIn("第667条", cleaned)
        self.assertIn("中华人民共和国民法典", cleaned)
        self.assertTrue(all(key.startswith("[") and key.endswith("]") for key in mapping))
        self.assertFalse(
            any(re.search(r"\[[A-Z]+\d+\]", value) for value in mapping.values())
        )
        self.assertEqual(restore_text(cleaned, mapping), text)


class DocxRedactionTests(unittest.TestCase):
    def test_manual_terms_are_redacted_and_restorable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "manual_terms.docx"
            output = root / "out"
            original = "案件备注：星河计划。核验码：ZX-7788。"

            doc = Document()
            paragraph = doc.add_paragraph()
            paragraph.add_run("案件备注：星河")
            paragraph.add_run("计划。核验码：ZX-7788。")
            doc.save(source)

            result = process_document(
                source,
                output,
                custom_terms=["星河计划", "ZX-7788"],
            )

            self.assertTrue(result.success, result.error)
            cleaned = _extract_text_docx(Path(result.output_file))
            self.assertNotIn("星河计划", cleaned)
            self.assertNotIn("ZX-7788", cleaned)
            self.assertIn("[X", cleaned)

            mapping = json.loads(
                Path(result.mapping_file).read_text(encoding="utf-8")
            )
            self.assertIn("星河计划", mapping.values())
            self.assertIn("ZX-7788", mapping.values())
            self.assertEqual(restore_text(cleaned, mapping), original)

    def test_docx_redacts_split_runs_without_losing_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample_张三.docx"
            output = root / "out"

            doc = Document()
            title = doc.add_paragraph().add_run("民事起诉状")
            title.bold = True
            title.font.size = Pt(18)
            doc.add_paragraph(
                "原告：张三，男，1985年3月12日出生，住北京市朝阳区建国路88号。"
            )
            paragraph = doc.add_paragraph()
            paragraph.add_run("原告张")
            paragraph.add_run("三").bold = True
            paragraph.add_run("认为，被告李四拒绝还款。")
            doc.add_paragraph("根据《中华人民共和国民法典》第667条，应当偿还。")
            doc.save(source)

            result = process_document(source, output)

            self.assertTrue(result.success, result.error)
            self.assertNotIn("张三", Path(result.output_file).name)
            self.assertNotIn("张三", Path(result.mapping_file).name)
            cleaned = _extract_text_docx(Path(result.output_file))
            self.assertNotIn("张三", cleaned)
            self.assertNotIn("1985年3月12日", cleaned)
            self.assertNotIn("北京市朝阳区建国路88号", cleaned)
            self.assertIn("[P", cleaned)
            self.assertIn("第", cleaned)

            cleaned_doc = Document(result.output_file)
            self.assertTrue(cleaned_doc.paragraphs[0].runs[0].bold)
            self.assertGreater(len(cleaned_doc.paragraphs[0].runs[0].text), 0)
            self.assertEqual(
                restore_text(cleaned, json.loads(Path(result.mapping_file).read_text("utf-8"))),
                _extract_text_docx(source),
            )


class BatchProcessingTests(unittest.TestCase):
    def test_same_named_documents_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()

            sources = []
            for directory, name in ((first_dir, "张三"), (second_dir, "李四")):
                source = directory / "起诉状.docx"
                doc = Document()
                doc.add_paragraph(f"原告：{name}，住北京市朝阳区建国路88号。")
                doc.save(source)
                sources.append(source)

            results = batch_process(sources, root / "out")

            self.assertTrue(all(result.success for result in results))
            self.assertEqual(len({result.output_file for result in results}), 2)
            self.assertEqual(len({result.mapping_file for result in results}), 2)

            mapped_names = set()
            for result in results:
                mapping = json.loads(
                    Path(result.mapping_file).read_text(encoding="utf-8")
                )
                mapped_names.update(mapping.values())

            self.assertIn("张三", mapped_names)
            self.assertIn("李四", mapped_names)


class PdfRedactionTests(unittest.TestCase):
    def test_pdf_keeps_page_assets_and_renders_readable_chinese(self):
        font = _cjk_font()
        if not font:
            self.skipTest("No CJK font available for the PDF test")

        text = (
            "民事起诉状\n"
            "原告：张三，男，住北京市朝阳区建国路88号。\n"
            "身份证号：110105198503121234，手机号：13800138000。\n"
            "根据《中华人民共和国民法典》第667条，张三应当偿还。"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample_张三.pdf"
            output = root / "out"

            doc = pymupdf.open()
            page = doc.new_page(width=595, height=842)
            logo = Image.new("RGB", (240, 64), (210, 20, 20))
            logo_buffer = BytesIO()
            logo.save(logo_buffer, format="PNG")
            page.insert_image(
                pymupdf.Rect(50, 20, 290, 84),
                stream=logo_buffer.getvalue(),
            )
            page.insert_text(
                (72, 72),
                text,
                fontfile=font,
                fontname="china",
                fontsize=12,
            )
            page.draw_rect(pymupdf.Rect(50, 50, 545, 700), color=(0.2, 0.3, 0.8))
            doc.save(source)
            doc.close()

            result = process_document(source, output)

            self.assertTrue(result.success, result.error)
            self.assertNotIn("张三", Path(result.output_file).name)
            self.assertNotIn("张三", Path(result.mapping_file).name)
            cleaned_doc = pymupdf.open(result.output_file)
            try:
                self.assertEqual(cleaned_doc.page_count, 1)
                cleaned_page = cleaned_doc[0]
                cleaned_text = cleaned_page.get_text()
                self.assertIn("民事起诉状", cleaned_text)
                self.assertIn("第667条", cleaned_text)
                self.assertNotIn("张三", cleaned_text)
                self.assertNotIn("北京市朝阳区建国路88号", cleaned_text)
                self.assertNotIn("110105198503121234", cleaned_text)
                self.assertGreaterEqual(len(cleaned_page.get_images(full=True)), 1)
                fonts = {item[3] for item in cleaned_page.get_fonts(full=True)}
                self.assertTrue(any("SimSun" in name or "PingFang" in name for name in fonts))
                rendered = cleaned_page.get_pixmap(
                    matrix=pymupdf.Matrix(1, 1), alpha=False
                )
                red, green, blue = rendered.pixel(170, 52)
                self.assertGreater(min(red, green, blue), 245)
            finally:
                cleaned_doc.close()

            mapping = json.loads(Path(result.mapping_file).read_text("utf-8"))
            self.assertEqual(
                " ".join(restore_text(cleaned_text, mapping).split()),
                " ".join(text.split()),
            )


class ScannedPdfRedactionTests(unittest.TestCase):
    def test_blank_pdf_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "blank.pdf"
            output = root / "out"

            doc = pymupdf.open()
            doc.new_page(width=595, height=842)
            doc.save(source)
            doc.close()

            result = process_document(source, output)

            self.assertFalse(result.success)
            self.assertEqual(result.error, "PDF 中没有识别到可脱敏文字。")
            self.assertFalse((output / "blank_cleaned.pdf").exists())

    def test_scanned_pdf_uses_local_ocr_and_removes_visible_text(self):
        font = _cjk_font()
        if not font:
            self.skipTest("No CJK font available for the scanned PDF test")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "scan.png"
            image = Image.new("RGB", (1654, 2339), "white")
            draw = ImageDraw.Draw(image)
            text_font = ImageFont.truetype(font, 48)
            lines = (
                "广东测试律师事务所",
                "TEST LAW FIRM",
                "民事起诉状",
                "甲方（委托人）：_张三",
                "联系人：_张三",
                "联系电话：_13800138000",
                "联系地址：_广东省海丰县海城镇城北社区居民委员会新北苑一巷58号",
                "指派李四_律师为代理人。",
                "根据《中华人民共和国民法典》第667条，张三应当偿还100000元。",
            )
            for index, line in enumerate(lines):
                draw.text((160, 80 + index * 110), line, font=text_font, fill="black")
            image.save(image_path)

            source = root / "scanned_张三.pdf"
            output = root / "out"
            doc = pymupdf.open()
            page = doc.new_page(width=595, height=842)
            page.insert_image(page.rect, filename=str(image_path))
            doc.save(source)
            doc.close()

            result = process_document(source, output)

            self.assertTrue(result.success, result.error)
            self.assertEqual(result.ocr_page_count, 1)
            cleaned_doc = pymupdf.open(result.output_file)
            try:
                self.assertEqual(cleaned_doc.page_count, 1)
                cleaned_page = cleaned_doc[0]
                cleaned_text = cleaned_page.get_text()
                for value in (
                    "张三",
                    "李四",
                    "广东省海丰县海城镇城北社区居民委员会新北苑一巷58号",
                    "13800138000",
                    "100000元",
                    "TEST LAW FIRM",
                ):
                    self.assertNotIn(value, cleaned_text)
                self.assertIn("第667条", cleaned_text)
                self.assertIn("[P", cleaned_text)
                self.assertGreaterEqual(len(cleaned_page.get_images(full=True)), 1)

                pixmap = cleaned_page.get_pixmap(
                    matrix=pymupdf.Matrix(150 / 72, 150 / 72),
                    alpha=False,
                )
                image_array = np.frombuffer(
                    pixmap.samples, dtype=np.uint8
                ).reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3]
                ocr_lines, _ = _get_ocr_engine()(
                    image_array[:, :, ::-1].copy()
                )
                visible_text = "\n".join(row[1] for row in ocr_lines or [])
                for value in (
                    "张三",
                    "李四",
                    "广东省海丰县海城镇城北社区居民委员会新北苑一巷58号",
                    "新北苑一巷58号",
                    "13800138000",
                    "TEST LAW FIRM",
                ):
                    self.assertNotIn(value, visible_text)
            finally:
                cleaned_doc.close()


if __name__ == "__main__":
    unittest.main()
