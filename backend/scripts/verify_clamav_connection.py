"""Exercise the real scanner hook without a DB, migrations, or production files.

Run explicitly in the candidate backend image with the scanner socket mounted.
This proves the hook/inspection boundary, NOT the complete HTTP upload protocol.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.upload_policy import PolicyViolation, inspect_file


def main() -> None:
    original = (
        settings.upload_scan_command,
        settings.upload_scan_required,
        settings.attachment_storage_root,
    )
    try:
        with TemporaryDirectory(prefix="nesta-scanner-check-") as directory:
            root = Path(directory)
            settings.attachment_storage_root = str(root)
            settings.upload_scan_required = True
            settings.upload_scan_command = (
                "clamdscan --config-file=/app/scripts/clamd-client.conf --stream --no-summary"
            )
            clean = root / "clean.txt"
            clean.write_text("NestaPrime clean scanner integration test.\n")
            inspect_file(clean, clean.name)
            assert clean.exists(), "Clean file unexpectedly removed"
            print("PASS clean file accepted by actual upload inspection", flush=True)

            infected = root / "eicar.txt"
            infected.write_bytes(
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}"
                b"$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
            )
            try:
                inspect_file(infected, infected.name)
            except PolicyViolation as exc:
                assert exc.status_code == 422, f"Expected 422, got {exc.status_code}"
            else:
                raise AssertionError("EICAR accepted")
            assert not infected.exists(), "Flagged file not quarantined"
            assert len(list((root / "_quarantine").glob("*.quarantined"))) == 1
            print("PASS EICAR refused and quarantined", flush=True)

            config = root / "unavailable.conf"
            config.write_text(f"LocalSocket {root / 'absent.sock'}\n")
            settings.upload_scan_command = f"clamdscan --config-file={config} --stream --no-summary"
            try:
                inspect_file(clean, clean.name)
            except PolicyViolation as exc:
                assert exc.status_code == 503, f"Expected 503, got {exc.status_code}"
            else:
                raise AssertionError("Unavailable scanner accepted upload")
            print("PASS unavailable scanner refuses with 503", flush=True)
    finally:
        (
            settings.upload_scan_command,
            settings.upload_scan_required,
            settings.attachment_storage_root,
        ) = original


if __name__ == "__main__":
    main()
