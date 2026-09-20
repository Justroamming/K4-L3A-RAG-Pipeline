"""
Task 2 — Crawl bài viết/thông báo.

Thu thập tối thiểu 5 URL công khai, lưu mỗi bài dưới dạng JSON trong
data/landing/news/ với url, title, date_crawled và content_markdown.
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
REQUEST_TIMEOUT = 45
USER_AGENT = (
    "Mozilla/5.0 (compatible; RAGPipeline/0.1; "
    "+https://github.com/Kilo-Org/kilocode)"
)

ARTICLE_URLS = [
    "https://bvhttdl.gov.vn/doi-moi-le-hoi-truyen-thong-de-dam-bao-van-minh-nhung-khong-tach-roi-nguon-coi-20250220141658954.htm",
    "https://baochinhphu.vn/to-chuc-le-hoi-truyen-thong-dung-ban-chat-y-nghia-lich-su-van-hoa-phu-hop-thuan-phong-my-tuc-102221230143112759.htm",
    "https://www.vntrip.vn/cam-nang/cac-le-hoi-phong-tuc-tap-quan-dac-trung-cac-dan-toc-viet-nam-108374",
    "https://canifa.com/blog/trang-phuc-truyen-thong-viet-nam",
    "https://trangphuchonghanh.com/kham-pha-15-trang-phuc-truyen-thong-viet-nam-mang-day-ban-sac-dan-toc-bid60.html",
]

_ARTICLE_SELECTORS = (
    ".article-content",
    ".entry-content",
    ".post-content",
    ".content-article",
    ".reviewLg__cont",
    ".elementor-widget-theme-post-content",
    ".noidungchitiet",
    ".box-BaiViet",
    "article",
    "main",
    "[role='main']",
)

_NOISE_PATTERN = re.compile(
    r"menu|navigation|header|footer|sidebar|related|comment|social|share|"
    r"newsletter|advert|login|modal|popup|cookie|rating|author|breadcrumb|"
    r"toc|table-of-contents|muc-luc|noi-dung-chinh",
    re.IGNORECASE,
)


def _decode_html(response: requests.Response) -> str:
    content = response.content
    meta_match = re.search(
        br"<meta[^>]+charset\s*=\s*['\"]?([\w-]+)",
        content[:4096],
        re.IGNORECASE,
    )
    if meta_match:
        encoding = meta_match.group(1).decode("ascii", errors="ignore")
        if encoding.lower().replace("_", "-") in {"utf-8", "utf8"}:
            return content.decode("utf-8", errors="replace")

    encoding = response.apparent_encoding or response.encoding or "utf-8"
    text = content.decode(encoding, errors="replace")
    if text.count("\ufffd") <= 3:
        return text
    return content.decode("utf-8", errors="replace")


def _fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    html = _decode_html(response)
    if not html.strip():
        raise ValueError("Response body is empty")
    return html


def _visible_text(element: Tag) -> str:
    return element.get_text(" ", strip=True)


def _select_article_root(soup: BeautifulSoup) -> Tag:
    for selector in _ARTICLE_SELECTORS:
        root = soup.select_one(selector)
        if root is not None and len(_visible_text(root)) >= 200:
            return root

    candidates = [soup.find("article"), soup.find("main"), soup.body, soup]
    for candidate in candidates:
        if candidate is not None and len(_visible_text(candidate)) >= 500:
            return candidate
    raise ValueError("Could not locate article content")


def _is_noise(element: Tag) -> bool:
    classes = element.get("class", []) or []
    if isinstance(classes, str):
        classes = [classes]
    attributes = " ".join(
        [
            str(element.get("id") or ""),
            " ".join(str(value) for value in classes),
            str(element.get("aria-label") or ""),
        ]
    )
    return bool(_NOISE_PATTERN.search(attributes))


def _strip_noise(root: Tag) -> None:
    for element in list(root.find_all(True)):
        if element is root or element.name is None:
            continue
        if element.attrs is None:
            continue
        if element.name in {"script", "style", "noscript", "svg", "canvas", "iframe"}:
            element.decompose()
            continue
        if element.get("aria-hidden") == "true" or element.has_attr("hidden"):
            element.decompose()
            continue
        if _is_noise(element):
            element.decompose()


def _inline_text(element: Tag | NavigableString) -> str:
    if isinstance(element, NavigableString):
        return re.sub(r"\s+", " ", str(element)).strip()
    if element.name == "br":
        return "\n"
    if element.name == "img":
        alt = element.get("alt", "").strip()
        src = element.get("src", "").strip()
        if alt:
            return alt
        if src and not src.startswith("data:"):
            return src
        return ""
    if element.name == "a":
        text = "".join(_inline_text(child) for child in element.children).strip()
        href = element.get("href", "").strip()
        if text and href and not href.startswith(("#", "javascript:")):
            return f"[{text}]({href})"
        return text
    if element.name in {"strong", "b"}:
        text = "".join(_inline_text(child) for child in element.children).strip()
        return f"**{text}**" if text else ""
    if element.name in {"em", "i"}:
        text = "".join(_inline_text(child) for child in element.children).strip()
        return f"*{text}*" if text else ""
    if element.name in {"code", "kbd"}:
        text = "".join(_inline_text(child) for child in element.children).strip()
        return f"`{text}`" if text else ""
    return "".join(_inline_text(child) for child in element.children)


def _render_children(element: Tag, lines: list[str]) -> None:
    for child in element.children:
        if isinstance(child, NavigableString):
            text = re.sub(r"\s+", " ", str(child)).strip()
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag) or child.name in {
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "iframe",
        }:
            continue
        name = child.name
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = _inline_text(child).strip()
            if text:
                lines.extend(["", f"{'#' * int(name[1])} {text}", ""])
            continue
        if name == "p":
            text = _inline_text(child).strip()
            if text:
                lines.append(text)
            continue
        if name in {"ul", "ol"}:
            ordered = name == "ol"
            for item in child.find_all("li", recursive=False):
                text = _inline_text(item).strip()
                if text:
                    marker = "1." if ordered else "-"
                    lines.append(f"{marker} {text}")
            continue
        if name == "blockquote":
            text = _inline_text(child).strip()
            if text:
                lines.extend(["", "\n".join(f"> {line}" for line in text.splitlines()), ""])
            continue
        if name == "table":
            for row in child.find_all("tr"):
                cells = [_inline_text(cell).strip() for cell in row.find_all(["th", "td"])]
                if any(cells):
                    lines.append(" | ".join(cells))
            continue
        if name in {"div", "section", "article", "main", "figure", "figcaption", "span"}:
            if name == "span" and not any(
                isinstance(descendant, Tag)
                and descendant.name in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"}
                for descendant in child.descendants
            ):
                text = _inline_text(child).strip()
                if text:
                    lines.append(text)
                continue
            _render_children(child, lines)
            continue
        text = _inline_text(child).strip()
        if text:
            lines.append(text)


def _to_markdown(root: Tag) -> str:
    lines: list[str] = []
    _render_children(root, lines)
    markdown = "\n".join(line.strip() for line in lines if line.strip())
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    if len(markdown) < 200:
        raise ValueError("Article content is too short")
    return markdown


def _extract_title(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    if heading is not None:
        title = heading.get_text(" ", strip=True)
        if title:
            return title
    for selector in ("meta[property='og:title']", "meta[name='title']"):
        element = soup.select_one(selector)
        if element is not None and element.get("content", "").strip():
            return element["content"].strip()
    if soup.title is not None:
        title = soup.title.get_text(" ", strip=True)
        return re.sub(r"\s*[-|]\s*[^-|]+$", "", title).strip()
    raise ValueError("Could not locate article title")


async def _crawl_tourism_article(url: str) -> dict | None:
    return None


async def crawl_article(url: str) -> dict:
    if "vietnamtourism.gov.vn" in url:
        special = await _crawl_tourism_article(url)
        if special is not None:
            return special

    html = await asyncio.to_thread(_fetch_html, url)
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    root = _select_article_root(soup)
    _strip_noise(root)
    content = _to_markdown(root)
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content,
    }


async def crawl_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for index, url in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(url)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            print(f"Failed: {url} — {error}")


if __name__ == "__main__":
    asyncio.run(crawl_all())
