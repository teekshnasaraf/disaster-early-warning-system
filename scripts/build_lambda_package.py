"""Build a deterministic, standard-library-only Lambda deployment ZIP."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "backend" / "src"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "build" / "lambda-deployment.zip"
PACKAGE_MODULES = (
    "disaster_fetcher.py",
    "earthquake_processing.py",
    "event_quality.py",
    "impact_estimation.py",
    "lambda_handler.py",
    "regional_relevance.py",
    "risk_assessment.py",
)
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def build_package(output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Write only the allowlisted handler modules to ``output_path``."""
    missing = [
        filename
        for filename in PACKAGE_MODULES
        if not (SOURCE_DIRECTORY / filename).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"Required Lambda source modules are missing: {', '.join(missing)}"
        )

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        with ZipFile(
            temporary_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for filename in PACKAGE_MODULES:
                entry = ZipInfo(filename, date_time=FIXED_ZIP_TIMESTAMP)
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(
                    entry,
                    (SOURCE_DIRECTORY / filename).read_bytes(),
                    compress_type=ZIP_DEFLATED,
                    compresslevel=9,
                )

        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"ZIP output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    package_path = build_package(args.output)
    print(f"Created {package_path} ({package_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
