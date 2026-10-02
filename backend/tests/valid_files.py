"""Genuinely valid small files for upload tests -- each is produced by the real library for its format (or built to the
format's own structure), so it passes the structural validators in app/core/upload_validators.py for a real reason,
not because it merely starts with the right bytes."""

import io
import struct
import zipfile


def valid_png(color=(200, 30, 30), size=(8, 8)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def valid_jpeg(color=(30, 120, 200), size=(16, 16)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


def valid_gif() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("P", (4, 4)).save(buffer, "GIF")
    return buffer.getvalue()


def valid_pdf(text="NestaPrime test document") -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def valid_xlsx() -> bytes:
    import openpyxl

    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "rate"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def valid_docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr("word/document.xml", '<?xml version="1.0"?><document><body><p>hi</p></body></document>')
    return buffer.getvalue()


def valid_eml() -> bytes:
    return b"From: a@example.com\r\nTo: b@example.com\r\nSubject: Site visit\r\nDate: Fri, 02 Oct 2026 10:00:00 +0530\r\n\r\nBody\r\n"


def valid_mp4() -> bytes:
    ftyp = struct.pack(">I4s4sI4s", 20, b"ftyp", b"mp42", 0, b"mp42")
    moov = struct.pack(">I4s", 8, b"moov")
    return ftyp + moov


def valid_dwg() -> bytes:
    return b"AC1027" + b"\x00" * 4090


def valid_dxf() -> bytes:
    return b"0\r\nSECTION\r\n2\r\nHEADER\r\n0\r\nENDSEC\r\n0\r\nEOF\r\n"


def valid_ole() -> bytes:
    """A minimal OLE2 header + one directory sector (structure only -- see the validator's documented limits)."""
    header = bytearray(512)
    header[0:8] = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    struct.pack_into("<H", header, 30, 9)  # 512-byte sectors
    struct.pack_into("<I", header, 44, 1)  # one FAT sector
    struct.pack_into("<I", header, 48, 1)  # directory starts at sector 1
    return bytes(header) + b"\x00" * 512 * 2


def content_for(filename: str, default: bytes = b"hello world") -> bytes:
    """Genuinely valid content for the filename's extension (plain text for anything else)."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    builders = {
        "pdf": valid_pdf, "png": valid_png, "jpg": valid_jpeg, "jpeg": valid_jpeg, "gif": valid_gif, "xlsx": valid_xlsx,
        "docx": valid_docx, "eml": valid_eml, "mp4": valid_mp4, "mov": valid_mp4, "m4v": valid_mp4, "dwg": valid_dwg,
        "dxf": valid_dxf, "doc": valid_ole, "xls": valid_ole, "ppt": valid_ole,
    }
    return builders[extension]() if extension in builders else default
