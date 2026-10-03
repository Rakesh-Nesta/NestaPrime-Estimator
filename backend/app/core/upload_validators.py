"""Structural validators for the supported attachment formats.

A matching header alone is NOT validation (a truncated, hand-edited or polyglot file keeps its header), so each
validator parses the file with the library or structure that format defines and requires it to parse completely:

  PDF            pypdf opens the cross-reference table and the document has at least one page; no active-content
                 entry points (/JavaScript, /JS, /Launch, /EmbeddedFile, /OpenAction with a script) in the catalog tree.
  PNG/JPEG/GIF/WebP/BMP/TIFF
                 JPEG: decoded at 1/8 scale (reads the whole stream, so truncation is caught, at ~1/64 the memory);
                 PNG: structure and CRC verification only (pixel data is NOT inflated); other formats: full decode under a
                 16 Mpx ceiling. All: 50 Mpx dimension ceiling and a frame-count ceiling.
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

MAX_IMAGE_PIXELS = 50_000_000  # dimensions ceiling for JPEG/PNG (cheaply validated, below)
MAX_FULL_DECODE_PIXELS = 16_000_000  # other image formats are decoded in full to validate, so they get the tighter ceiling
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
            if image.format == "JPEG":
                # decode at 1/8 scale (about 1/64 of the memory): the decoder still has to read the whole entropy-coded
                # stream, so a truncated or corrupt JPEG raises here without a full-resolution decode
                image.draft("RGB", (max(width // 8, 1), max(height // 8, 1)))
                image.load()
            elif image.format == "PNG":
                image.verify()  # chunk structure and CRCs through IEND
                validate_png_pixel_stream(path)  # then the compressed pixel data itself, streamed (no pixel buffer)
            else:
                if width * height > MAX_FULL_DECODE_PIXELS:
                    raise ValueError("image dimensions are too large")
                image.load()  # full decode: a truncated or corrupt image raises here
    except ValueError:
        raise
    except Image.DecompressionBombError:
        raise ValueError("image dimensions are too large")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"image is damaged or truncated ({type(exc).__name__})")


# colour type -> (channels, permitted bit depths), per the PNG specification (table 11.1)
_PNG_LAYOUTS = {0: (1, (1, 2, 4, 8, 16)), 2: (3, (8, 16)), 3: (1, (1, 2, 4, 8)), 4: (2, (8, 16)), 6: (4, (8, 16))}
_ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
_PNG_MAX_DIMENSION = 2**31 - 1


def _png_expected_raw_size(width: int, height: int, bit_depth: int, color_type: int, interlace: int) -> int:
    """Bytes the IDAT stream must inflate to: for every (sub)image row, one filter byte plus ceil(width x bits-per-pixel / 8).
    Raises ValueError for any layout the PNG specification does not define (unsupported layouts fail explicitly)."""
    if color_type not in _PNG_LAYOUTS:
        raise ValueError(f"unsupported PNG colour type {color_type}")
    channels, depths = _PNG_LAYOUTS[color_type]
    if bit_depth not in depths:
        raise ValueError(f"unsupported PNG bit depth {bit_depth} for colour type {color_type}")
    if interlace not in (0, 1):
        raise ValueError(f"unsupported PNG interlace method {interlace}")
    if not (0 < width <= _PNG_MAX_DIMENSION and 0 < height <= _PNG_MAX_DIMENSION):
        raise ValueError("invalid PNG dimensions")
    bits_per_pixel = channels * bit_depth

    def pass_size(w: int, h: int) -> int:
        return 0 if w == 0 or h == 0 else h * (1 + (w * bits_per_pixel + 7) // 8)

    if interlace == 0:
        return pass_size(width, height)
    total = 0
    for x0, y0, dx, dy in _ADAM7:
        total += pass_size(-(-(width - x0) // dx) if width > x0 else 0, -(-(height - y0) // dy) if height > y0 else 0)
    return total


def validate_png_pixel_stream(path: Path) -> None:
    """The PNG's IDAT data must inflate to EXACTLY the number of bytes its header implies, with a complete zlib stream.

    Bounded: every decompress() call is capped at the number of bytes still PERMITTED (never more than 64 KiB), so the
    inflater can never be made to produce more than one byte beyond the expected total before the check stops it, and
    the output is counted, never stored. No pixel buffer is allocated. A PNG with valid chunk CRCs but a corrupt, short,
    long or bomb-like compressed stream is refused at upload (Pillow's verify() alone checks only chunk structure/CRCs).
    Layouts the PNG specification does not define (colour type / bit depth / interlace combinations) fail explicitly."""
    import zlib

    with open(path, "rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG")
        decompressor = zlib.decompressobj()
        produced = 0
        expected = None
        saw_idat = False
        while True:
            header = handle.read(8)
            if len(header) < 8:
                raise ValueError("PNG ends before IEND")
            length, kind = struct.unpack(">I4s", header)
            if kind == b"IHDR":
                if expected is not None or length != 13:
                    raise ValueError("malformed PNG header")
                width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                    ">IIBBBBB", handle.read(13))
                if compression != 0 or filter_method != 0:
                    raise ValueError("unsupported PNG compression or filter method")
                expected = _png_expected_raw_size(width, height, bit_depth, color_type, interlace)
                handle.read(4)
            elif kind == b"IDAT":
                if expected is None:
                    raise ValueError("IDAT before IHDR")
                saw_idat = True
                remaining = length
                while remaining:
                    piece = handle.read(min(remaining, 65536))
                    if not piece:
                        raise ValueError("PNG data is truncated")
                    remaining -= len(piece)
                    pending = piece
                    while pending:
                        allowed = min(65536, expected - produced + 1)  # at most ONE byte past the permitted total
                        out = decompressor.decompress(pending, allowed)
                        produced += len(out)
                        if produced > expected:
                            raise ValueError("PNG pixel data is longer than its header allows")
                        if decompressor.eof:
                            if decompressor.unused_data or decompressor.unconsumed_tail:
                                raise ValueError("PNG has data after the end of its pixel stream")
                            break
                        pending = decompressor.unconsumed_tail
                handle.read(4)
            elif kind == b"IEND":
                break
            else:
                handle.seek(length + 4, 1)
        if expected is None or not saw_idat:
            raise ValueError("PNG has no pixel data")
        if not decompressor.eof or produced != expected:
            raise ValueError("PNG pixel data is incomplete or corrupt")


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
