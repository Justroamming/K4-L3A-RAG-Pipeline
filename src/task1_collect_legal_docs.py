"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Hướng dẫn:
    1. Chọn chủ đề của nhóm.
    2. Tìm tối thiểu 3 tài liệu PDF/DOCX từ nguồn công khai.
    3. Lưu file gốc vào data/landing/legal/.
    4. Đặt tên không dấu và thể hiện đúng nội dung.

Ví dụ tài liệu: học phí, học bổng, ký túc xá, quy trình đăng ký.
Nếu website chặn crawler, hãy chọn nguồn công khai khác; không vượt WAF.
"""

from pathlib import Path

import requests


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

LEGAL_SOURCES = {
    "vai_suy_nghi_khac_ve_le_hoi_truyen_thong.pdf": (
        "https://dsvh.gov.vn/Upload/files/Tap%20chi%20DSVH/So%2031/"
        "3108_Vai%20suy%20nghi%20khac%20ve%20Le%20hoi%20truyen%20thong.pdf"
    ),
    "bao_ton_di_san_van_hoa_phi_vat_the_tu_goc_nhin_toan_cau_hoa.pdf": (
        "https://dsvh.gov.vn/Upload/files/Tap%20chi%20DSVH/So%2021/"
        "2101_Bao%20ton%20di%20san%20van%20hoa%20phi%20vat%20the%20tu%20goc%20nhin%20toan%20cau%20hoa.pdf"
    ),
    "dan_ca_quan_ho_bac_ninh_di_san_van_hoa_phi_vat_the_dai_dien_cua_nhan_loai.pdf": (
        "https://dsvh.gov.vn/Upload/files/Tap%20chi%20DSVH/So%2030/"
        "3008_Dan%20ca%20Quan%20ho%20Bac%20Ninh%20di%20san%20van%20hoa%20phi%20vat%20the%20dai%20dien%20cua%20nhan%20loai.pdf"
    ),
}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def _is_valid_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(5) == b"%PDF-"
    except OSError:
        return False


def _download(source_url: str, output_path: Path) -> None:
    temporary_path = output_path.with_suffix(output_path.suffix + ".part")
    try:
        response = requests.get(
            source_url,
            headers={"User-Agent": "K4-RAG-Pipeline/1.0"},
            timeout=(10, 120),
            stream=True,
        )
        response.raise_for_status()
        with temporary_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
        if not _is_valid_pdf(temporary_path):
            raise ValueError(f"Downloaded content is not a PDF: {source_url}")
        temporary_path.replace(output_path)
        print(f"Saved: {output_path}")
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def download_documents() -> None:
    """Tải ít nhất 3 PDF/DOCX từ nguồn công khai."""
    for filename, source_url in LEGAL_SOURCES.items():
        output_path = DATA_DIR / filename
        if _is_valid_pdf(output_path):
            print(f"Already available: {output_path}")
            continue
        _download(source_url, output_path)


if __name__ == "__main__":
    setup_directory()
    download_documents()
