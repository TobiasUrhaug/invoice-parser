def make_pdf_bytes(text: str = "test") -> bytes:
    """Create a minimal valid single-page PDF with the given ASCII text."""
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET\n".encode()

    obj1 = b"1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n"
    obj2 = b"2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>>\nendobj\n"
    )
    obj4 = (
        f"4 0 obj\n<</Length {len(content)}>>\nstream\n".encode()
        + content
        + b"endstream\nendobj\n"
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
