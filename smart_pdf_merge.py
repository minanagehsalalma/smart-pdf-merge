#!/usr/bin/env python3
"""
Smart PDF merge for scanned or badly-sized source PDFs.

Primary goal:
- merge PDFs normally when page geometry is sane
- detect page-size outliers like giant scanner/export canvases
- rebuild only suspicious pages onto a standard paper size
- explain every decision so the tool is not a black box
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

__version__ = "0.1.0"

STANDARD_PAGES = {
    "a4": (595.0, 842.0),
    "letter": (612.0, 792.0),
}


@dataclass
class SourcePage:
    source_path: Path
    source_label: str
    page_number: int
    page: object
    width: float
    height: float
    rotation: int
    reasons: list[str] = field(default_factory=list)
    action: str = "keep"
    target_width: float | None = None
    target_height: float | None = None
    scale: float | None = None

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def orientation(self) -> str:
        return "landscape" if self.width >= self.height else "portrait"

    @property
    def max_dimension(self) -> float:
        return max(self.width, self.height)

    @property
    def min_dimension(self) -> float:
        return min(self.width, self.height)

    @property
    def inches(self) -> tuple[float, float]:
        return (self.width / 72.0, self.height / 72.0)

    def report_row(self) -> dict[str, object]:
        return {
            "source": self.source_label,
            "page_number": self.page_number,
            "width_points": round(self.width, 2),
            "height_points": round(self.height, 2),
            "rotation": self.rotation,
            "orientation": self.orientation,
            "action": self.action,
            "reasons": self.reasons,
            "target_width_points": None if self.target_width is None else round(self.target_width, 2),
            "target_height_points": None if self.target_height is None else round(self.target_height, 2),
            "scale": None if self.scale is None else round(self.scale, 6),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge PDFs while detecting suspicious page geometries and "
            "normalizing outlier pages onto standard paper sizes."
        )
    )
    parser.add_argument("inputs", nargs="+", help="Input PDF files in merge order.")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output PDF path.",
    )
    parser.add_argument(
        "--paper",
        choices=sorted(STANDARD_PAGES),
        default="a4",
        help="Standard paper size used when normalizing pages. Default: a4",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=14.0,
        help="Margin in PDF points for normalized pages. Default: 14",
    )
    parser.add_argument(
        "--absolute-max-dimension",
        type=float,
        default=2000.0,
        help=(
            "Pages larger than this in either dimension are treated as suspicious. "
            "Default: 2000 points"
        ),
    )
    parser.add_argument(
        "--relative-area-factor",
        type=float,
        default=3.0,
        help=(
            "Pages larger than this times the cohort median area are treated as "
            "suspicious. Default: 3.0"
        ),
    )
    parser.add_argument(
        "--normalize-all",
        action="store_true",
        help="Normalize every page onto a standard paper canvas.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the final summary.",
    )
    parser.add_argument(
        "--report-json",
        help="Optional path for a machine-readable JSON decision report.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args()


def load_pages(input_paths: list[Path]) -> tuple[list[PdfReader], list[SourcePage]]:
    readers: list[PdfReader] = []
    pages: list[SourcePage] = []

    for path in input_paths:
        reader = PdfReader(str(path))
        readers.append(reader)
        for idx, page in enumerate(reader.pages, start=1):
            mediabox = page.mediabox
            rotation = page.get("/Rotate") or 0
            pages.append(
                SourcePage(
                    source_path=path,
                    source_label=path.name,
                    page_number=idx,
                    page=page,
                    width=float(mediabox.width),
                    height=float(mediabox.height),
                    rotation=int(rotation),
                )
            )
    return readers, pages


def effective_dimensions(width: float, height: float, rotation: int) -> tuple[float, float]:
    if rotation % 180 == 90:
        return (height, width)
    return (width, height)


def median_reference_area(pages: list[SourcePage], absolute_max_dimension: float) -> float:
    sane_pages = [p.area for p in pages if p.max_dimension <= absolute_max_dimension]
    reference_pool = sane_pages or [p.area for p in pages]
    return statistics.median(reference_pool)


def classify_pages(
    pages: list[SourcePage],
    *,
    normalize_all: bool,
    absolute_max_dimension: float,
    relative_area_factor: float,
    paper: str,
    margin: float,
) -> None:
    reference_area = median_reference_area(pages, absolute_max_dimension)

    for page in pages:
        suspicious = False
        effective_width, effective_height = effective_dimensions(page.width, page.height, page.rotation)
        effective_max_dimension = max(effective_width, effective_height)
        effective_area = effective_width * effective_height

        if effective_max_dimension > absolute_max_dimension:
            suspicious = True
            page.reasons.append(
                f"max dimension {effective_max_dimension:.1f}pt exceeds "
                f"{absolute_max_dimension:.1f}pt"
            )

        if reference_area > 0 and effective_area > reference_area * relative_area_factor:
            suspicious = True
            page.reasons.append(
                f"page area {effective_area:.0f}pt^2 exceeds cohort median "
                f"{reference_area:.0f}pt^2 by factor {effective_area / reference_area:.2f}"
            )

        if normalize_all or suspicious:
            target_w, target_h = target_dimensions(
                paper,
                "landscape" if effective_width >= effective_height else "portrait",
            )
            usable_w = max(target_w - (margin * 2.0), 1.0)
            usable_h = max(target_h - (margin * 2.0), 1.0)
            scale = min(usable_w / effective_width, usable_h / effective_height)

            page.action = "normalize"
            page.target_width = target_w
            page.target_height = target_h
            page.scale = scale

            if normalize_all and not suspicious:
                page.reasons.append("normalize-all requested")
        else:
            page.action = "keep"


def target_dimensions(paper: str, orientation: str) -> tuple[float, float]:
    portrait_w, portrait_h = STANDARD_PAGES[paper]
    if orientation == "landscape":
        return portrait_h, portrait_w
    return portrait_w, portrait_h


def merge_pages(
    pages: list[SourcePage],
    *,
    output_path: Path,
) -> None:
    writer = PdfWriter()

    for info in pages:
        if info.action == "keep":
            writer.add_page(info.page)
            continue

        target_w = info.target_width or info.width
        target_h = info.target_height or info.height
        scale = info.scale or 1.0
        scaled_w = info.width * scale
        scaled_h = info.height * scale
        tx = (target_w - scaled_w) / 2.0
        ty = (target_h - scaled_h) / 2.0

        canvas = writer.add_blank_page(width=target_w, height=target_h)
        canvas.merge_transformed_page(
            info.page,
            Transformation().scale(scale).translate(tx, ty),
        )

    with output_path.open("wb") as handle:
        writer.write(handle)


def print_report(
    pages: list[SourcePage],
    *,
    output_path: Path,
    quiet: bool,
) -> None:
    normalized = sum(1 for page in pages if page.action == "normalize")

    if not quiet:
        for page in pages:
            width_in, height_in = page.inches
            prefix = f"{page.source_label} page {page.page_number}"
            size_text = f"{page.width:.1f} x {page.height:.1f}pt ({width_in:.1f} x {height_in:.1f}in)"

            if page.action == "keep":
                print(f"[KEEP] {prefix}: {size_text}")
                continue

            reasons = "; ".join(page.reasons) if page.reasons else "normalization requested"
            print(
                f"[NORMALIZE] {prefix}: {size_text} -> "
                f"{page.target_width:.0f} x {page.target_height:.0f}pt "
                f"at scale {page.scale:.5f}"
            )
            print(f"  reason: {reasons}")

    print(
        f"Wrote {output_path} with {len(pages)} pages. "
        f"Normalized {normalized} page(s), kept {len(pages) - normalized} page(s)."
    )


def write_report_json(pages: list[SourcePage], output_path: Path, report_path: Path) -> None:
    report = {
        "output": str(output_path),
        "page_count": len(pages),
        "normalized_pages": sum(1 for page in pages if page.action == "normalize"),
        "kept_pages": sum(1 for page in pages if page.action == "keep"),
        "pages": [page.report_row() for page in pages],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def validate_inputs(input_paths: list[Path], output_path: Path) -> None:
    missing = [str(path) for path in input_paths if not path.exists()]
    if missing:
        raise SystemExit(f"Input PDF not found: {', '.join(missing)}")

    if not input_paths:
        raise SystemExit("At least one input PDF is required.")

    output_path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    input_paths = [Path(item).expanduser().resolve() for item in args.inputs]
    output_path = Path(args.output).expanduser().resolve()
    report_path = Path(args.report_json).expanduser().resolve() if args.report_json else None

    validate_inputs(input_paths, output_path)
    _, pages = load_pages(input_paths)

    classify_pages(
        pages,
        normalize_all=args.normalize_all,
        absolute_max_dimension=args.absolute_max_dimension,
        relative_area_factor=args.relative_area_factor,
        paper=args.paper,
        margin=args.margin,
    )

    merge_pages(
        pages,
        output_path=output_path,
    )
    if report_path:
        write_report_json(pages, output_path, report_path)
    print_report(pages, output_path=output_path, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
