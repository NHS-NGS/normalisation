"""Unit tests for the VCF normalisation Lambda handler."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set required env vars before importing the handler
os.environ.setdefault("GENOME_REF_BUCKET", "test-genome-bucket")
os.environ.setdefault("GENOME_REF_KEY", "genomes/hg38/genome.fa")
os.environ.setdefault("OUTPUT_PREFIX", "output/")

from handler import (
    _parse_event,
    _run_bcftools_norm,
    _upload_output,
    lambda_handler,
)


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------


class TestParseEvent:
    def test_s3_event(self):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "my-bucket"},
                        "object": {"key": "input/sample.vcf.gz"},
                    }
                }
            ]
        }
        bucket, key = _parse_event(event)
        assert bucket == "my-bucket"
        assert key == "input/sample.vcf.gz"

    def test_s3_event_url_encoded_key(self):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "my-bucket"},
                        "object": {"key": "input/my+sample.vcf.gz"},
                    }
                }
            ]
        }
        bucket, key = _parse_event(event)
        assert key == "input/my sample.vcf.gz"

    def test_manual_event(self):
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}
        bucket, key = _parse_event(event)
        assert bucket == "my-bucket"
        assert key == "input/sample.vcf.gz"

    def test_missing_fields_raises(self):
        with pytest.raises((KeyError, IndexError)):
            _parse_event({})


# ---------------------------------------------------------------------------
# bcftools norm subprocess
# ---------------------------------------------------------------------------


class TestBcftoolsNorm:
    @patch("handler.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        input_path = tmp_path / "sample.vcf.gz"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="Lines total/split/joined: 100/10/5\n")

        # Patch WORK_DIR so output lands in tmp_path
        with patch("handler.WORK_DIR", tmp_path):
            output = _run_bcftools_norm(input_path, genome_path)

        assert output == tmp_path / f"normalised_{input_path.name}"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bcftools"
        assert "-f" in cmd
        assert "--keep-sum" in cmd

    @patch("handler.subprocess.run")
    def test_failure_raises(self, mock_run, tmp_path):
        input_path = tmp_path / "sample.vcf.gz"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: genome mismatch")

        with patch("handler.WORK_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="bcftools norm failed"):
                _run_bcftools_norm(input_path, genome_path)


# ---------------------------------------------------------------------------
# Upload output
# ---------------------------------------------------------------------------


class TestUploadOutput:
    @patch("handler.s3")
    def test_upload_key(self, mock_s3, tmp_path):
        output_path = tmp_path / "normalised_sample.vcf.gz"
        output_path.touch()

        key = _upload_output("my-bucket", "input/sample.vcf.gz", output_path)
        assert key == "output/sample.vcf.gz"
        mock_s3.upload_file.assert_called_once_with(
            str(output_path), "my-bucket", "output/sample.vcf.gz"
        )


# ---------------------------------------------------------------------------
# Full handler (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestLambdaHandler:
    @patch("handler._cleanup")
    @patch("handler._upload_output", return_value="output/sample.vcf.gz")
    @patch("handler._run_bcftools_norm")
    @patch("handler._download_genome")
    @patch("handler._download_input")
    @patch("handler._setup_work_dir")
    def test_full_flow(
        self,
        mock_setup,
        mock_dl_input,
        mock_dl_genome,
        mock_norm,
        mock_upload,
        mock_cleanup,
    ):
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["input"] == "s3://my-bucket/input/sample.vcf.gz"
        assert body["output"] == "s3://my-bucket/output/sample.vcf.gz"

        mock_setup.assert_called_once()
        mock_dl_input.assert_called_once_with("my-bucket", "input/sample.vcf.gz")
        mock_dl_genome.assert_called_once()
        mock_norm.assert_called_once()
        mock_upload.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("handler._cleanup")
    @patch("handler._download_input", side_effect=Exception("S3 error"))
    @patch("handler._setup_work_dir")
    def test_cleanup_on_error(self, mock_setup, mock_dl, mock_cleanup):
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}

        with pytest.raises(Exception, match="S3 error"):
            lambda_handler(event, None)

        # Cleanup should still be called via finally
        mock_cleanup.assert_called_once()
