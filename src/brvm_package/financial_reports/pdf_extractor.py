"""
PDF and OCR extraction utilities for financial tables.
"""

class FinancialPDFExtractor:
    def extract_tables(self, pdf_path):
        """
        Extract tables from a PDF (text-based or image-based).
        Tries camelot, then tabula, then falls back to OCR if needed.
        Returns: list of pandas.DataFrame or list of text blocks.
        """
        import os
        import camelot
        import pandas as pd
        tables = []
        try:
            tables_camelot = camelot.read_pdf(pdf_path, pages="all")
            for t in tables_camelot:
                tables.append(t.df)
            if tables:
                return tables
        except Exception:
            pass
        # Optionally try tabula-py here if camelot fails
        # If still nothing, fallback to OCR
        return self.extract_with_ocr(pdf_path)

    def extract_with_ocr(self, pdf_path):
        """
        Extract text from a PDF using OCR (for scanned PDFs).
        Returns: list of text blocks (one per page).
        """
        import fitz  # PyMuPDF
        from PIL import Image
        import pytesseract
        import io
        doc = fitz.open(pdf_path)
        texts = []
        for page in doc:
            pix = page.get_pixmap()
            img = Image.open(io.BytesIO(pix.tobytes()))
            text = pytesseract.image_to_string(img, lang="fra")
            texts.append(text)
        return texts
