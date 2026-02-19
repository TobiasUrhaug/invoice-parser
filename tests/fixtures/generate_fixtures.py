#!/usr/bin/env python3
"""Generate synthetic PDF invoice fixtures for testing.

Run with: uv run python tests/fixtures/generate_fixtures.py
"""

import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).parent


def _make_text_pdf(lines: list[str]) -> bytes:
    """Create a minimal valid single-page PDF with the given text lines."""
    content_parts: list[str] = []
    y = 720
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_parts.append(f"BT /F1 11 Tf 50 {y} Td ({safe}) Tj ET")
        y -= 16
    content = "\n".join(content_parts).encode()

    obj1 = b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
    obj2 = b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>>\nendobj\n"
    )
    obj4 = (
        f"4 0 obj\n<</Length {len(content)}>>\nstream\n".encode()
        + content
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>\nendobj\n"

    header = b"%PDF-1.4\n"
    objects = [obj1, obj2, obj3, obj4, obj5]
    body = b""
    offsets: list[int] = []
    for obj in objects:
        offsets.append(len(header) + len(body))
        body += obj

    xref_offset = len(header) + len(body)
    xref = "xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"
    trailer = f"trailer\n<</Size 6 /Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n"
    return header + body + xref.encode() + trailer.encode()


def _make_image_pdf(lines: list[str]) -> bytes:
    """Create a PDF where all content is a JPEG image (simulates a scanned page).

    pdfplumber will find no selectable text, triggering the OCR path.
    """
    img = Image.new("RGB", (612, 792), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=14)

    y = 60
    for line in lines:
        draw.text((50, y), line, fill="black", font=font)
        y += 22

    jpeg_buf = io.BytesIO()
    img.save(jpeg_buf, format="JPEG", quality=90)
    jpeg_data = jpeg_buf.getvalue()

    w, h = img.size

    image_stream_header = (
        f"5 0 obj\n"
        f"<</Type /XObject /Subtype /Image"
        f" /Width {w} /Height {h}"
        f" /ColorSpace /DeviceRGB /BitsPerComponent 8"
        f" /Filter /DCTDecode /Length {len(jpeg_data)}>>\n"
        f"stream\n"
    ).encode()
    obj5 = image_stream_header + jpeg_data + b"\nendstream\nendobj\n"

    content_str = f"q {w} 0 0 {h} 0 0 cm /Im1 Do Q\n"
    content = content_str.encode()

    obj1 = b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
    obj2 = b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R"
        b" /Resources <</XObject <</Im1 5 0 R>>>>>>\nendobj\n"
    )
    obj4 = (
        f"4 0 obj\n<</Length {len(content)}>>\nstream\n".encode()
        + content
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    objects = [obj1, obj2, obj3, obj4, obj5]
    body = b""
    offsets: list[int] = []
    for obj in objects:
        offsets.append(len(header) + len(body))
        body += obj

    xref_offset = len(header) + len(body)
    xref = "xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"
    trailer = f"trailer\n<</Size 6 /Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n"
    return header + body + xref.encode() + trailer.encode()


# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

FIXTURES: list[dict[str, object]] = [
    {
        "name": "invoice_english",
        "generator": "text",
        "lines": [
            "INVOICE",
            "",
            "From: Acme Corp, 123 Main St, New York, NY 10001",
            "To:   Globex Ltd, 456 Oak Ave, Chicago, IL 60601",
            "",
            "Invoice Number: INV-2024-001",
            "Invoice Date:   2024-01-15",
            "",
            "Description                  Qty   Unit Price   Amount",
            "Professional Services          1    1000.00      1000.00",
            "",
            "Net Amount:    USD 1000.00",
            "VAT (25%):     USD  250.00",
            "Total Amount:  USD 1250.00",
            "",
            "Payment due within 30 days.",
            "Bank: First National Bank  IBAN: US12 3456 7890 0001",
        ],
        "expected": {
            "invoiceDate": "2024-01-15",
            "invoiceReference": "INV-2024-001",
            "netAmount": {"amount": "1000.00", "currency": "USD"},
            "vatAmount": {"amount": "250.00", "currency": "USD"},
            "totalAmount": {"amount": "1250.00", "currency": "USD"},
        },
    },
    {
        "name": "invoice_german",
        "generator": "text",
        # NOTE: Deliberately ASCII-only. The Helvetica Type1 font used by _make_text_pdf
        # cannot render non-ASCII characters (ä, ö, ü, ß) without explicit encoding.
        # This fixture verifies non-English language handling but does not exercise
        # non-ASCII character handling. See T-19 for verification note.
        "lines": [
            "RECHNUNG",
            "",
            "Von: Mustermann GmbH, Hauptstrasse 10, 10115 Berlin",
            "An:  Schmidt AG, Industrieweg 5, 80333 Muenchen",
            "",
            "Rechnungsnummer: RE-2024-042",
            "Rechnungsdatum:  20.02.2024",
            "",
            "Beschreibung                 Menge   Einzelpreis   Betrag",
            "Beratungsleistungen            1       850,00       850,00",
            "",
            "Nettobetrag:    EUR  850,00",
            "MwSt. (19%):    EUR  161,50",
            "Gesamtbetrag:   EUR 1011,50",
            "",
            "Zahlungsziel: 14 Tage netto.",
            "Bank: Deutsche Bank  IBAN: DE89 3704 0044 0532 0130 00",
        ],
        "expected": {
            "invoiceDate": "2024-02-20",
            "invoiceReference": "RE-2024-042",
            "netAmount": {"amount": "850.00", "currency": "EUR"},
            "vatAmount": {"amount": "161.50", "currency": "EUR"},
            "totalAmount": {"amount": "1011.50", "currency": "EUR"},
        },
    },
    {
        "name": "invoice_scanned",
        "generator": "image",
        "lines": [
            "INVOICE",
            "",
            "Seller: Nordic Supplies AS, Storgata 1, Oslo",
            "Buyer:  Bergen Trading AS, Bryggen 5, Bergen",
            "",
            "Invoice No: SCAN-001",
            "Date: 2024-03-10",
            "",
            "Item                     Amount",
            "Consulting Services      GBP 500.00",
            "",
            "Net:   GBP  500.00",
            "VAT:   GBP  100.00",
            "Total: GBP  600.00",
            "",
            "Please pay within 30 days.",
        ],
        "expected": {
            "invoiceDate": "2024-03-10",
            "invoiceReference": "SCAN-001",
            "netAmount": {"amount": "500.00", "currency": "GBP"},
            "vatAmount": {"amount": "100.00", "currency": "GBP"},
            "totalAmount": {"amount": "600.00", "currency": "GBP"},
        },
    },
    {
        "name": "invoice_partial",
        "generator": "text",
        "lines": [
            "INVOICE",
            "",
            "From: Freelancer Studio, Via Roma 7, Milan, Italy",
            "To:   Omega BV, Keizersgracht 1, Amsterdam",
            "",
            "Reference: PART-001",
            "Date: 2024-04-05",
            "",
            "Description             Amount",
            "Design Work             EUR 300.00",
            "",
            "Net Amount: EUR 300.00",
            "",
            "Note: VAT exempt under Art. 7 DPR 633/72.",
        ],
        "expected": {
            "invoiceDate": "2024-04-05",
            "invoiceReference": "PART-001",
            "netAmount": {"amount": "300.00", "currency": "EUR"},
            "vatAmount": None,
            "totalAmount": None,
        },
    },
]


def main() -> None:
    for fixture in FIXTURES:
        name = fixture["name"]
        generator = fixture["generator"]
        lines: list[str] = fixture["lines"]  # type: ignore[assignment]
        expected = fixture["expected"]

        pdf_path = FIXTURES_DIR / f"{name}.pdf"
        json_path = FIXTURES_DIR / f"{name}.json"

        if generator == "text":
            pdf_bytes = _make_text_pdf(lines)
        else:
            pdf_bytes = _make_image_pdf(lines)

        pdf_path.write_bytes(pdf_bytes)
        json_path.write_text(json.dumps(expected, indent=2) + "\n")
        print(f"  wrote {pdf_path.name}  ({len(pdf_bytes):,} bytes)")
        print(f"  wrote {json_path.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
