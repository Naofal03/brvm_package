"""
PDF and OCR extraction utilities for BRVM financial reports.
"""

from __future__ import annotations

from importlib import import_module


class FinancialExtractionDependencyError(RuntimeError):
    """Raised when optional financial-report extraction dependencies are missing."""


def _import_or_raise(module_name: str, package_hint: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        raise FinancialExtractionDependencyError(
            "Financial report extraction requires optional dependency "
            f"`{package_hint}`. Install with `pip install brvm-package[financial-reports]`."
        ) from exc


class FinancialPDFExtractor:
    def extract_tables(self, pdf_path: str):
        """
        Extract tables from a PDF (text-based or image-based).
        Strategy:
        1. `camelot` for structured PDF tables
        2. `pdfplumber` for text extraction from born-digital PDFs
        3. OCR fallback for scanned PDFs
        """
        try:
            camelot = import_module("camelot")
        except ModuleNotFoundError:
            camelot = None

        if camelot is not None:
            try:
                tables = []
                tables_camelot = camelot.read_pdf(pdf_path, pages="all")
                for table in tables_camelot:
                    tables.append(table.df)
                if tables:
                    return tables
            except Exception:
                pass

        try:
            return self.extract_with_pdfplumber(pdf_path)
        except FinancialExtractionDependencyError:
            return self.extract_with_ocr(pdf_path)

    def extract_with_pdfplumber(self, pdf_path: str) -> list[str]:
        pdfplumber = _import_or_raise("pdfplumber", "pdfplumber")

        texts: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    texts.append(text)
        if texts:
            return texts
        return self.extract_with_ocr(pdf_path)

    def extract_with_ocr(self, pdf_path: str) -> list[str]:
        """
        Extract text from a PDF using OCR (for scanned PDFs).
        Returns a list of text blocks, one per page.
        """
        fitz = _import_or_raise("fitz", "pymupdf")
        Image = _import_or_raise("PIL.Image", "pillow")
        pytesseract = _import_or_raise("pytesseract", "pytesseract")
        import io

        doc = fitz.open(pdf_path)
        texts: list[str] = []
        for page in doc:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            text = pytesseract.image_to_string(img, lang="fra")
            texts.append(text)
        return texts
