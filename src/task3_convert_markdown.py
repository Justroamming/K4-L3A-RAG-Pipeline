"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Legal documents are converted from PDF/DOC/DOCX and news JSON articles are
wrapped with their source metadata. Output names are stable and reruns replace
the corresponding Markdown file instead of creating copies.
"""

import json
import re
import shutil
import subprocess
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

import numpy as np

try:
    from .task1_collect_legal_docs import LEGAL_SOURCES
except ImportError:
    from task1_collect_legal_docs import LEGAL_SOURCES


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"
MIN_CONTENT_LENGTH = 200


def _display_path(path: Path) -> str:
    root = LANDING_DIR.parent.resolve()
    resolved_path = path.resolve()
    return f"data/{resolved_path.relative_to(root).as_posix()}"


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _metadata_value(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)
    return True


def _markitdown_converter():
    try:
        from markitdown import MarkItDown
    except ImportError as error:
        raise RuntimeError(
            "MarkItDown is required for document conversion; install the "
            "project dependencies with: python -m pip install -e .[dev]"
        ) from error
    return MarkItDown()


@lru_cache(maxsize=1)
def _easyocr_reader():
    try:
        import easyocr
    except ImportError as error:
        raise RuntimeError(
            "The legal PDFs are image-only and require EasyOCR; install the "
            "project dependencies with: python -m pip install -e .[dev]"
        ) from error
    return easyocr.Reader(["vi", "en"], gpu=False, verbose=False)


def _ocr_line_groups(detections: list[tuple], page_width: int, page_height: int) -> list[dict]:
    lines = []
    for box, text, confidence in detections:
        if confidence < 0.25 or not text.strip():
            continue
        x_values = [point[0] for point in box]
        y_values = [point[1] for point in box]
        x1, x2 = min(x_values), max(x_values)
        y1, y2 = min(y_values), max(y_values)
        lines.append(
            {
                "x1": x1,
                "x2": x2,
                "y1": y1,
                "y2": y2,
                "cx": (x1 + x2) / 2,
                "cy": (y1 + y2) / 2,
                "text": text.strip(),
            }
        )
    if not lines:
        return []

    median_height = sorted(line["y2"] - line["y1"] for line in lines)[
        len(lines) // 2
    ]
    tolerance = max(8.0, median_height * 0.75)
    y_groups: list[list[dict]] = []
    for line in sorted(lines, key=lambda item: (item["cy"], item["x1"])):
        group = next(
            (
                current
                for current in reversed(y_groups[-3:])
                if abs(current[0]["cy"] - line["cy"]) <= tolerance
            ),
            None,
        )
        if group is None:
            y_groups.append([line])
        else:
            group.append(line)

    rows = []
    gap_threshold = max(page_width * 0.08, median_height * 2.5)
    for y_group in y_groups:
        y_group.sort(key=lambda item: item["x1"])
        clusters: list[list[dict]] = []
        for line in y_group:
            if not clusters or line["x1"] - clusters[-1][-1]["x2"] > gap_threshold:
                clusters.append([line])
            else:
                clusters[-1].append(line)
        for cluster in clusters:
            cluster.sort(key=lambda item: item["x1"])
            rows.append(
                {
                    "x1": min(line["x1"] for line in cluster),
                    "x2": max(line["x2"] for line in cluster),
                    "cx": sum(line["cx"] for line in cluster) / len(cluster),
                    "cy": sum(line["cy"] for line in cluster) / len(cluster),
                    "text": " ".join(line["text"] for line in cluster),
                }
            )
    rows.sort(key=lambda line: (line["cy"], line["x1"]))

    left_count = sum(line["cx"] < page_width * 0.45 for line in rows)
    right_count = sum(line["cx"] > page_width * 0.55 for line in rows)
    if left_count < 4 or right_count < 4:
        return rows

    header = [
        line
        for line in rows
        if line["cy"] < page_height * 0.35 or line["x2"] - line["x1"] > page_width * 0.72
    ]
    body = [line for line in rows if line not in header]
    left = sorted(
        (line for line in body if line["cx"] < page_width * 0.5),
        key=lambda line: line["cy"],
    )
    right = sorted(
        (line for line in body if line["cx"] >= page_width * 0.5),
        key=lambda line: line["cy"],
    )
    return sorted(header, key=lambda line: line["cy"]) + left + right


def _extract_scanned_pdf_text(path: Path) -> str:
    import pdfplumber

    reader = _easyocr_reader()
    pages = []
    with pdfplumber.open(path) as document:
        for page in document.pages:
            image = page.to_image(resolution=220).original
            detections = reader.readtext(
                np.asarray(image),
                detail=1,
                paragraph=False,
                workers=0,
            )
            text = "\n".join(
                line["text"]
                for line in _ocr_line_groups(
                    detections,
                    page_width=image.width,
                    page_height=image.height,
                )
            )
            if text.strip():
                pages.append(text.strip())
    if not pages:
        raise RuntimeError(f"OCR returned no text for {path}")
    return "\n\n".join(pages)


def _extract_pdf_text(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if executable:
        process = subprocess.run(
            [executable, str(path), "-"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode == 0 and process.stdout.strip():
            return process.stdout

    for module_name, reader_name in (("pypdf", "PdfReader"), ("PyPDF2", "PdfReader")):
        try:
            module = __import__(module_name)
            reader = getattr(module, reader_name)(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except ImportError:
            continue
        except Exception:
            break

    try:
        import fitz
    except ImportError:
        pass
    else:
        document = fitz.open(path)
        text = "\n".join(page.get_text() for page in document)
        document.close()
        if text.strip():
            return text

    return _extract_scanned_pdf_text(path)


def _extract_docx_text(path: Path) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in document.iter(f"{namespace}p"):
        text = "".join(
            node.text or ""
            for node in paragraph.iter()
            if node.tag == f"{namespace}t"
        )
        if text.strip():
            paragraphs.append(text.strip())
    return "\n\n".join(paragraphs)


def _convert_legal_file(path: Path, converter) -> str:
    conversion_errors = []
    try:
        result = converter.convert(str(path))
        text = getattr(result, "text_content", None)
        if text is None:
            text = getattr(result, "text", None)
        if callable(text):
            text = text()
        if isinstance(text, str) and text.strip():
            return _clean_text(text)
        conversion_errors.append("MarkItDown returned empty content")
    except Exception as error:
        conversion_errors.append(f"MarkItDown failed: {error}")

    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            text = _extract_pdf_text(path)
        elif suffix == ".docx":
            text = _extract_docx_text(path)
        else:
            raise ValueError(f"Unsupported legal document type: {suffix}")
        return _clean_text(text)
    except Exception as fallback_error:
        details = "; ".join(conversion_errors)
        raise RuntimeError(f"Could not convert {path}: {details}") from fallback_error


def _legal_header(path: Path) -> str:
    source_url = LEGAL_SOURCES.get(path.name)
    lines = [
        f"# {path.stem}",
        "",
        f"**Landing file:** `{_display_path(path)}`",
    ]
    if source_url:
        lines.append(f"**Source:** {source_url}")
    lines.extend(["**Type:** legal", "", "---", ""])
    return "\n".join(lines)


def convert_legal_docs() -> None:
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = _markitdown_converter()
    supported = {".pdf", ".doc", ".docx"}

    for path in sorted(legal_dir.iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in supported:
            continue
        content = _convert_legal_file(path, converter)
        if len(content) < MIN_CONTENT_LENGTH:
            raise ValueError(f"Converted legal document is too short: {path}")
        output_path = output_dir / f"{path.stem}.md"
        changed = _write_if_changed(output_path, _legal_header(path) + content + "\n")
        print(f"{'Saved' if changed else 'Unchanged'}: {output_path}")


def _news_header(data: dict, path: Path) -> str:
    required = {"url", "title", "date_crawled", "content_markdown"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"{path.name} is missing metadata: {', '.join(missing)}")

    title = _metadata_value(data["title"])
    url = _metadata_value(data["url"])
    crawled = _metadata_value(data["date_crawled"])
    if not title or not url or not crawled:
        raise ValueError(f"{path.name} contains empty metadata")

    return (
        f"# {title}\n\n"
        f"**Source:** {url}\n\n"
        f"**Crawled:** {crawled}\n\n"
        f"**Landing file:** `{_display_path(path)}`\n\n"
        "---\n\n"
    )


def convert_news_articles() -> None:
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(news_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} must contain a JSON object")
        content = _clean_text(str(data.get("content_markdown", "")))
        if len(content) < MIN_CONTENT_LENGTH:
            raise ValueError(f"News article content is too short: {path}")
        output_path = output_dir / f"{path.stem}.md"
        markdown = _news_header(data, path) + content + "\n"
        changed = _write_if_changed(output_path, markdown)
        print(f"{'Saved' if changed else 'Unchanged'}: {output_path}")


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
