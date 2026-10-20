from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_BUILDER = REPOSITORY_ROOT / "scripts" / "build_lambda_package.py"
EXPECTED_MODULES = {
    "disaster_fetcher.py",
    "earthquake_processing.py",
    "event_quality.py",
    "impact_estimation.py",
    "lambda_handler.py",
    "risk_assessment.py",
}


class LambdaPackageTests(unittest.TestCase):
    def test_zip_is_repeatable_and_contains_only_required_modules(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            first_zip = Path(temporary_directory) / "first.zip"
            second_zip = Path(temporary_directory) / "second.zip"
            for output_path in (first_zip, second_zip):
                subprocess.run(
                    [
                        sys.executable,
                        str(PACKAGE_BUILDER),
                        "--output",
                        str(output_path),
                    ],
                    cwd=REPOSITORY_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())
            with ZipFile(first_zip) as archive:
                self.assertEqual(set(archive.namelist()), EXPECTED_MODULES)

    def test_modules_import_from_extracted_zip_with_project_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            package_path = temporary_path / "lambda.zip"
            extracted_path = temporary_path / "extracted"
            extracted_path.mkdir()

            subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_BUILDER),
                    "--output",
                    str(package_path),
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            with ZipFile(package_path) as archive:
                archive.extractall(extracted_path)

            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import disaster_fetcher, earthquake_processing, event_quality, "
                        "impact_estimation, lambda_handler, risk_assessment; "
                        "assert callable(lambda_handler.handler)"
                    ),
                ],
                cwd=extracted_path,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
