# Upload hardening — policy, proposed limits, and what is and is not claimed

Status: **proposed**. The numeric limits below are proposals awaiting business acceptance; nothing here is deployed,
scheduled or merged. Code: `backend/app/core/upload_policy.py`, `upload_validators.py`, `body_limit.py`,
`attachment_upload.py`; tests: `backend/tests/test_upload_hardening.py`.

## 1. Proposed limits — value, business impact, configuration, boundary tests

| Limit | Proposed value | Business impact | Configured by | Boundary tests (`test_upload_hardening.py`) |
|---|---|---|---|---|
| Single file | 100 MB (unchanged, M.3) | none — existing rule | code constant | `test_declared_size_limits_are_enforced`, `test_ordinary_upload_refuses_a_body_over_100_mb_with_413` |
| Chunk size (multi-chunk uploads) | 64 KiB – 16 MiB | a 100 MB file needs ≥ 7 chunks; a phone on a poor link can still use small chunks; one chunk is held in memory, so 16 MiB caps per-request memory | code constant | `test_a_chunk_size_below/above_the_minimum/maximum…`, `test_chunk_size_boundaries_and_tiny_single_chunk_files_are_accepted` |
| Chunks per session | 2,048 | never binds a legitimate upload (100 MB ÷ 64 KiB = 1,600) | code constant | same boundary test (1,600 accepted; 1-byte chunks refused) |
| Open sessions per user | 10 | a user can have 10 uploads in flight; the 11th is refused (429) until one finishes or is cleaned up | code constant | `test_open_sessions_per_user_are_capped_at_10…`, race: `test_racing_session_starts_cannot_exceed_the_open_session_cap` |
| Open declared bytes per user | 500 MiB | five maximum-size files at once per user | code constant | `test_declared_bytes_per_user_are_capped…`, race: `…declared_byte_cap` |
| Global storage ceiling | 50 GiB (stored attachments + open reservations) | refuses new uploads (413) when the disk budget is spent; `0` disables it | `ATTACHMENT_STORAGE_CAP_BYTES` (env) | `test_a_global_storage_cap_…`, `test_the_storage_cap_counts_reserved_and_stored_bytes_once…`, race: `…quota_lock_cannot_jointly_exceed…` |
| Request body ceiling | chunk limit + 1 MiB / file limit + 1 MiB framing allowance | normal multipart framing is accepted; anything larger is cut off before parsing | code constants | `test_a_maximum_size_chunk_with_normal_multipart_overhead_is_accepted`, streamed/lying-length tests |
| Parser ceilings | image 50 Mpx, 1,000 frames; ZIP 5,000 entries and 1 GiB expanded; XML part 8 MiB, no DTD/entities; 100,000 top-level video boxes; 5,000 PDF pages | refuses decompression/expansion abuse; ordinary business files are far below every figure | code constants | section 10 of the test file |

"Configured by: code constant" means changing it is a one-line edit plus a deploy, not a runtime setting. Only the
storage ceiling (and the scanner settings) are environment-configurable.

**Reserved vs stored vs temporary bytes.** *Reserved* = declared bytes of open sessions (counted against the user's and the
global limit). *Stored* = committed attachments. *Temporary* = chunk files on disk for a reservation — never counted
again (they are the same bytes as the reservation) and removed by cleanup. A session that fails or is purged releases its
reservation.

## 2. What validation does and does not establish

* **Establishes:** the file parses completely as the type its extension names, to the extent each parser can tell, and
  contains none of the specifically refused active content (PDF script/launch/embedded-file entries, Office macros/ActiveX).
* **Does not establish malware clearance.** Parsing a file is not scanning it.
* **Stated limits of the validators:** DWG is a signature-level check (version tag + minimum size) — no DWG parser is a
  dependency. Legacy Office (.doc/.xls/.ppt) is structural only (OLE header and sector arithmetic). EML, TXT, CSV cannot
  be proven *un*-truncated. PDF content streams are deliberately not decompressed during validation, and PDF active-content
  detection is on the raw bytes (it cannot see entries inside compressed object streams). No wall-clock/CPU limit is
  enforced on a parser. Passing validation does not make a PDF/Office file safe to open in a desktop application.

## 3. Scanner states — exactly what happens

| State | Behaviour | Recorded as |
|---|---|---|
| No scanner configured (default) | upload accepted after structural validation. **The file was not scanned; it is not "clean".** | warning log `upload accepted but not malware-scanned`; `--report` shows `scanner: disabled-uploads-are-not-scanned` |
| `UPLOAD_SCAN_REQUIRED=true`, no command | **every upload refused (503)** until a scanner is configured | `required-but-not-configured-uploads-refused` |
| Scanner configured, exit 0 | accepted | `active` |
| Scanner exit 1 (infected) | refused (422); file moved to `_quarantine/`; no Attachment row is created | quarantine count in `--report` |
| Scanner missing/crashes/times out/other exit code | **refused (503), fail closed**; ordinary upload stores nothing; a resumable session stays retriable (not failed) | warning/error log |

No per-file "scanned" flag is stored (that would need a schema migration, deliberately not part of this change).

## 4. Quarantine

A quarantined file has no `Attachment` row, so it cannot be downloaded, reviewed, approved for marketing, shared or used
as signing evidence; nothing in the app serves from `_quarantine/`. Clearing it is a manual operator step. Existing
originals are never modified (stored bytes are served byte-for-byte; verified by SHA-256 in tests).

## 5. Supported formats and what changed

Accepted (each with a structural validator): PDF, PNG, JPG/JPEG, GIF, WebP, BMP, TIF/TIFF, HEIC, DOCX, XLSX, PPTX, DOC,
XLS, PPT, EML, DWG, DXF, MP4, MOV, M4V, TXT, CSV. This is a superset of everything the attachments panel offers
(`.jpg .jpeg .png .gif .webp .pdf .doc .docx .xls .xlsx .eml .dwg`), asserted by
`test_every_type_the_attachments_panel_offers_is_supported_by_the_backend`.

**Behaviour change for approval:** before, *any* extension outside a deny-list was accepted; now only the list above is.
Formerly accepted but now refused (415) include .zip/.rar/.7z, .odt/.ods, .rtf, .kml/.kmz, audio files, .rvt/.skp/.ifc
and other CAD/BIM formats. If any of these is needed for sports drawings or site documents, it must be added together with
a validator (or explicitly accepted unvalidated).

## 6. Downstream processing — what validation does NOT protect

Cheap validation (e.g. a PDF whose page stream would inflate to ~300 MB is accepted without being decompressed) proves only
that the *validator* avoids that expansion. It does not protect anything that later opens the file. The processing this CRM
actually performs on stored uploads, and its status:

| Processing | Where | Status |
|---|---|---|
| Generated quotation/estimate PDFs decode every embedded image in full | `app/api/pdf_documents.py` | **Measured**: one 12 Mpx JPEG ≈ 2.5 s / 180 MB peak; 50 Mpx ≈ 11 s / 0.7 GB; 100 Mpx ≈ 22 s / 1.3 GB (this dev machine). Mitigation here: the upload ceiling is 50 Mpx and the PDF builder **skips any image over that budget** (legacy images stored before the ceiling). **Not solved:** several 50 Mpx photos on one quotation multiply the cost; no per-request memory/time limit exists. |
| Sending an attachment by email/WhatsApp reads the whole file into memory | `app/api/messages.py` | bounded by the 100 MB file limit only |
| Downloading | `GET /attachments/{id}/download` | streamed by `FileResponse`; headers make it inert in a browser |
| PDF text/page extraction, OOXML/office parsing, video transcoding, thumbnails | — | **not performed** by the CRM, so not exercised; if ever added they need their own limits |
| Users opening a PDF/Office file in desktop software | outside the CRM | outside this change's protection entirely |

Tests: `test_quotation_pdf_leaves_out_a_stored_image_over_the_embed_budget_instead_of_decoding_it` (PDF builder skip) and the
parser-bound tests in `test_upload_hardening.py` section 10.

## 7. Coverage carried over from the P5 branch's reproduction tests

`backend/tests/test_upload_security_reproductions.py` (P5 branch) holds 23 tests. Dropping it in a combined tree loses
nothing: 22 keep their names and assertions in `test_upload_hardening.py` (marks removed, now ordinary passing tests); the
23rd, `test_content_is_not_inspected_documented_gap` (a characterization that a `.pdf`-named HTML file was accepted), is
**replaced** by its inverse: `test_ordinary_upload_refuses_content_that_does_not_match_its_type_with_415`,
`test_resumable_completion_refuses_content_that_does_not_match_its_type` and the malformed/truncated/mismatched matrix. The
ordinary-upload and supersede controls (`test_ordinary_upload_refuses_prohibited_types…`,
`test_supersede_refuses_prohibited_types…`, `test_control_a_completion_with_unchanged_permissions_commits`) are retained.
Two tests changed only their sizes to fit the 64 KiB chunk minimum (`chunk_bodies_must_match…`,
`abandoned_sessions_are_cleaned_up…`); their assertions are unchanged.

## 8. Cleanup scheduling (documented, not activated)

See `deploy/README.md` → "Upload hardening". The script and wrapper exist; no cron entry is installed by this change.
