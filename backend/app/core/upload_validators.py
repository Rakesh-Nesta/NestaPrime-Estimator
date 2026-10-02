"""Structural validators for the supported attachment formats.

A matching header alone is NOT validation (a truncated, hand-edited or polyglot file keeps its header), so each
validator parses the file with the library or structure that format defines and requires it to parse completely:

  PDF            pypdf opens the cross-reference table and the document has at least one page; no active-content
                 entry points (/JavaScript, /JS, /Launch, /EmbeddedFile, /OpenAction with a script) in the catalog tree.
  PNG/JPEG/GIF/WebP/BMP/TIFF
                 Pillow fully DECODES the image (not just verify(), which misses truncated JPEGs), with a pixel ceiling
                 against decompression bombs.
  DOCX/XLSX/PPTX the ZIP's CRCs all verify, the OOXML content-types part parses as XML, the format's main part exists,
                 macro/ActiveX parts (vbaProject.bin, ActiveX) are refused, and the declared uncompressed size is bounded
                 (zip-bomb guard).
  DOC/XLS/PPT    OLE2 compound file: header magic, sector/size arithmetic and FAT bounds are consistent. (No OLE
                 parser is a dependency, so this is structural, not a full parse -- stated in the PR.)
  EML            parsed with the standard email parser; From/To/Date/Subject: at least two must be present.
  MP4/MOV/M4V/HEIC
                 the ISO base-media box tree is walked to the end of the file: every size field must be consistent and
                 land exactly on the end (a truncated file fails), and 'ftyp' or 'moov' must be present.
  DWG            version tag in the known AutoCAD set and a plausible minimum size (2 KiB). (No DWG parser is a dependency,
                 so this is a signature-level check -- stated in the PR.)
  DXF            ASCII DXF section structure ending in an EOF record, or the AutoCAD binary-DXF sentinel.
  TXT/CSV        decodes as UTF-8 or Windows-1252, contains no NUL bytes, and no active-content markup in the first
                 64 KiB; CSV additionally parses.

Every validator raises ValueError with a short reason on failure."""

import csv
import io
import re
import struct
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

MAX_IMAGE_PIXELS = 100_000_000
MAX_ZIP_UNCOMPRESSED = 1024 * 1024 * 1024
MAX_ZIP_ENTRIES = 5000
MAX_XML_PART_BYTES = 8 * 1024 * 1024
MAX_TOP_LEVEL_BOXES = 100_000
MAX_PDF_PAGES = 5000
MAX_IMAGE_FRAMES = 1000

_ACTIVE_TEXT = re.compile(rb"<\s*(script|html|svg|iframe|object|embed|!doctype\s+html)", re.IGNORECASE)
_PDF_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia)\b")
_DWG_VERSIONS = {b"AC1009", b"AC1012", b"AC1014", b"AC1015", b"AC1018", b"AC1021", b"AC1024", b"AC1027", b"AC1032"}


def _head(path: Path, n: int = 8192) -> bytes:
    with open(path, "rb") as handle:
        return handle.read(n)


def validate_pdf(path: Path) -> None:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    data = path.read_bytes()
    if b"%PDF-" not in data[:1024] or _ACTIVE_TEXT.search(data[:1024]):
        raise ValueError("not a PDF")
    if _PDF_ACTIVE.search(data):
        raise ValueError("contains active content (script, launch action or embedded file)")
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted PDFs cannot be inspected")
        if len(reader.pages) < 1:
            raise ValueError("no pages")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("too many pages")
        reader.pages[0].mediabox  # resolves the first page object; page CONTENT streams are never decompressed here
    except ValueError:
        raise
    except (PyPdfError, Exception) as exc:  # noqa: BLE001 - any parser failure means "not a complete PDF"
        raise ValueError(f"PDF structure is damaged or truncated ({type(exc).__name__})")


_IMAGE_FORMATS = {
    ".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".webp": "WEBP", ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
}


def validate_image(path: Path, extension: str) -> None:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(path) as image:
            if image.format != _IMAGE_FORMATS[extension]:
                raise ValueError(f"the image is {image.format}, not {_IMAGE_FORMATS[extension]}")
            if getattr(image, "n_frames", 1) > MAX_IMAGE_FRAMES:
                raise ValueError("too many frames")
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image dimensions are too large")
            image.load()  # full decode: a truncated or corrupt image raises here
    except ValueError:
        raise
    except Image.DecompressionBombError:
        raise ValueError("image dimensions are too large")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"image is damaged or truncated ({type(exc).__name__})")


_OOXML_MAIN = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml", ".pptx": "ppt/presentation.xml"}


def validate_ooxml(path: Path, extension: str) -> None:
    from xml.etree import ElementTree

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_ZIP_UNCOMPRESSED:
                raise ValueError("archive is too large when unpacked")
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f"archive member {bad!r} is corrupt")
            if "[Content_Types].xml" not in names or _OOXML_MAIN[extension] not in names:
                raise ValueError("not a valid Office document (required parts missing)")
            if any(n.lower().endswith(("vbaproject.bin", ".exe", ".dll")) or "activex" in n.lower() for n in names):
                raise ValueError("contains macros or ActiveX content")
            for part in ("[Content_Types].xml", _OOXML_MAIN[extension]):
                if archive.getinfo(part).file_size > MAX_XML_PART_BYTES:
                    raise ValueError(f"{part} is too large")
                raw = archive.read(part)
                if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:  # no DTDs / entity definitions in Office XML (entity expansion)
                    raise ValueError(f"{part} contains a DTD or entity declaration")
                ElementTree.fromstring(raw)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Office document is damaged or truncated ({type(exc).__name__})")


_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def validate_ole(path: Path) -> None:
    size = path.stat().st_size
    head = _head(path, 512)
    if len(head) < 512 or not head.startswith(_OLE_MAGIC):
        raise ValueError("not an Office 97-2003 file")
    sector_shift = struct.unpack_from("<H", head, 30)[0]
    if sector_shift not in (9, 12):
        raise ValueError("invalid sector size")
    sector = 1 << sector_shift
    if (size - 512 if sector == 512 else size - sector) % sector != 0:
        raise ValueError("file length is not a whole number of sectors (truncated)")
    fat_sectors, first_dir = struct.unpack_from("<I", head, 44)[0], struct.unpack_from("<I", head, 48)[0]
    total_sectors = (size - sector) // sector
    if fat_sectors < 1 or first_dir >= total_sectors:
        raise ValueError("directory sector is out of range (truncated)")


def validate_eml(path: Path) -> None:
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        raise ValueError("not a text email")
    message = BytesParser(policy=policy.default).parsebytes(data, headersonly=True)
    present = sum(1 for h in ("From", "To", "Date", "Subject") if message[h] is not None)
    if present < 2:
        raise ValueError("not an email (needs at least two of From/To/Date/Subject headers)")


def validate_iso_bmff(path: Path) -> None:
    size = path.stat().st_size
    seen = set()
    boxes = 0
    with open(path, "rb") as handle:
        offset = 0
        while offset < size:
            boxes += 1
            if boxes > MAX_TOP_LEVEL_BOXES:
                raise ValueError("too many boxes")
            handle.seek(offset)
            header = handle.read(16)
            if len(header) < 8:
                raise ValueError("truncated box header")
            length, kind = struct.unpack(">I4s", header[:8])
            if length == 1:
                if len(header) < 16:
                    raise ValueError("truncated box header")
                length = struct.unpack(">Q", header[8:16])[0]
            elif length == 0:
                length = size - offset  # box extends to the end of the file
            if length < 8 or offset + length > size:
                raise ValueError("box size runs past the end of the file (truncated)")
            seen.add(kind)
            offset += length
    if b"ftyp" not in seen and b"moov" not in seen:
        raise ValueError("not an ISO media file")


def validate_dwg(path: Path) -> None:
    head = _head(path, 16)
    if head[:6] not in _DWG_VERSIONS or path.stat().st_size < 2048:
        raise ValueError("not a recognised AutoCAD DWG version")


def validate_dxf(path: Path) -> None:
    head = _head(path, 4096)
    if head.startswith(b"AutoCAD Binary DXF"):
        return
    text = head.decode("utf-8", "replace")
    lines = [ln.strip() for ln in text.splitlines()[:40]]
    if "SECTION" not in lines or b"\x00" in head:
        raise ValueError("not a DXF file")
    with open(path, "rb") as handle:  # an ASCII DXF ends with an EOF record; a truncated one does not
        handle.seek(max(path.stat().st_size - 64, 0))
        if b"EOF" not in handle.read():
            raise ValueError("the DXF is truncated (no EOF record)")


def validate_text(path: Path, extension: str) -> None:
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("binary data in a text file")
    for encoding in ("utf-8", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise ValueError("not readable text")
    if _ACTIVE_TEXT.search(data[:65536]):
        raise ValueError("contains active markup")
    if extension == ".csv":
        try:
            for _ in csv.reader(io.StringIO(text), strict=True):
                pass
        except csv.Error as exc:
            raise ValueError(f"not a valid CSV ({exc})")


VALIDATORS = {
    ".pdf": lambda p: validate_pdf(p),
    **{e: (lambda p, e=e: validate_image(p, e)) for e in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")},
    ".docx": lambda p: validate_ooxml(p, ".docx"),
    ".xlsx": lambda p: validate_ooxml(p, ".xlsx"),
    ".pptx": lambda p: validate_ooxml(p, ".pptx"),
    **{e: (lambda p: validate_ole(p)) for e in (".doc", ".xls", ".ppt")},
    ".eml": lambda p: validate_eml(p),
    **{e: (lambda p: validate_iso_bmff(p)) for e in (".mp4", ".mov", ".m4v", ".heic")},
    ".dwg": lambda p: validate_dwg(p),
    ".dxf": lambda p: validate_dxf(p),
    ".txt": lambda p: validate_text(p, ".txt"),
    ".csv": lambda p: validate_text(p, ".csv"),
}
