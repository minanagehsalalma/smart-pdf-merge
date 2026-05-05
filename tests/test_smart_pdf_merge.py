from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from smart_pdf_merge import classify_pages, load_pages, merge_pages, write_report_json


class SmartPdfMergeTests(unittest.TestCase):
    def test_outlier_page_gets_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            giant_pdf = tmp / "giant.pdf"
            normal_pdf = tmp / "normal.pdf"
            output_pdf = tmp / "merged.pdf"
            report_json = tmp / "report.json"

            giant_writer = PdfWriter()
            giant_writer.add_blank_page(width=11520, height=8085.6)
            giant_writer.write(giant_pdf)

            normal_writer = PdfWriter()
            normal_writer.add_blank_page(width=595, height=842)
            normal_writer.write(normal_pdf)

            _, pages = load_pages([giant_pdf, normal_pdf])
            classify_pages(
                pages,
                normalize_all=False,
                absolute_max_dimension=2000,
                relative_area_factor=3.0,
                paper="a4",
                margin=14,
            )
            merge_pages(pages, output_path=output_pdf)
            write_report_json(pages, output_pdf, report_json)

            merged = PdfReader(str(output_pdf))
            self.assertEqual(len(merged.pages), 2)
            self.assertEqual(float(merged.pages[0].mediabox.width), 842.0)
            self.assertEqual(float(merged.pages[0].mediabox.height), 595.0)
            self.assertEqual(float(merged.pages[1].mediabox.width), 595.0)
            self.assertEqual(float(merged.pages[1].mediabox.height), 842.0)

            report = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(report["normalized_pages"], 1)
            self.assertEqual(report["kept_pages"], 1)
            self.assertEqual(report["pages"][0]["action"], "normalize")
            self.assertEqual(report["pages"][1]["action"], "keep")

    def test_normalize_all_rebuilds_every_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_pdf = tmp / "source.pdf"
            output_pdf = tmp / "normalized.pdf"

            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            writer.add_blank_page(width=612, height=792)
            writer.write(source_pdf)

            _, pages = load_pages([source_pdf])
            classify_pages(
                pages,
                normalize_all=True,
                absolute_max_dimension=2000,
                relative_area_factor=3.0,
                paper="letter",
                margin=14,
            )
            merge_pages(pages, output_path=output_pdf)

            merged = PdfReader(str(output_pdf))
            self.assertEqual(len(merged.pages), 2)
            for page in merged.pages:
                self.assertEqual(float(page.mediabox.width), 612.0)
                self.assertEqual(float(page.mediabox.height), 792.0)


if __name__ == "__main__":
    unittest.main()
