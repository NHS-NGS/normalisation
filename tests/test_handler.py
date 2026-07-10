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

from handler import (  # noqa: E402
    _download_genome,
    _parse_event,
    _remove_ref_ref_records,
    _run_bcftools_norm,
    _upload_output,
    lambda_handler,
)


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------


class TestParseEvent:
    """Tests for _parse_event handling of S3 and manual payloads."""

    def test_s3_event(self):
        """S3 event record is parsed into bucket and key."""
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
        """URL-encoded key (+ as space) is decoded correctly."""
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
        """Manual invocation payload is parsed into bucket and key."""
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}
        bucket, key = _parse_event(event)
        assert bucket == "my-bucket"
        assert key == "input/sample.vcf.gz"

    def test_missing_fields_raises(self):
        """Empty event raises KeyError or IndexError."""
        with pytest.raises((KeyError, IndexError)):
            _parse_event({})


# ---------------------------------------------------------------------------
# Genome download
# ---------------------------------------------------------------------------


class TestDownloadGenome:
    """Tests for _download_genome with uncompressed and bgzipped genomes."""

    @patch("handler.s3")
    def test_uncompressed_genome(self, mock_s3, tmp_path):
        """Uncompressed genome downloads .fa and .fai only."""
        with patch("handler.WORK_DIR", tmp_path), \
             patch("handler.GENOME_REF_BUCKET", "ref-bucket"), \
             patch("handler.GENOME_REF_KEY", "genomes/genome.fa"):
            result = _download_genome()

        assert result == tmp_path / "genome.fa"
        assert mock_s3.download_file.call_count == 2
        mock_s3.download_file.assert_any_call(
            "ref-bucket", "genomes/genome.fa",
            str(tmp_path / "genome.fa"),
        )
        mock_s3.download_file.assert_any_call(
            "ref-bucket", "genomes/genome.fa.fai",
            str(tmp_path / "genome.fa.fai"),
        )

    @patch("handler.s3")
    def test_bgzipped_genome_downloads_gzi(self, mock_s3, tmp_path):
        """Bgzipped genome also downloads the .gzi index."""
        with patch("handler.WORK_DIR", tmp_path), \
             patch("handler.GENOME_REF_BUCKET", "ref-bucket"), \
             patch("handler.GENOME_REF_KEY", "genomes/genome.fa.gz"):
            result = _download_genome()

        assert result == tmp_path / "genome.fa.gz"
        assert mock_s3.download_file.call_count == 3
        mock_s3.download_file.assert_any_call(
            "ref-bucket", "genomes/genome.fa.gz",
            str(tmp_path / "genome.fa.gz"),
        )
        mock_s3.download_file.assert_any_call(
            "ref-bucket", "genomes/genome.fa.gz.fai",
            str(tmp_path / "genome.fa.gz.fai"),
        )
        mock_s3.download_file.assert_any_call(
            "ref-bucket", "genomes/genome.fa.gz.gzi",
            str(tmp_path / "genome.fa.gz.gzi"),
        )


# ---------------------------------------------------------------------------
# bcftools norm subprocess
# ---------------------------------------------------------------------------


class TestBcftoolsNorm:
    """Tests for _run_bcftools_norm subprocess execution."""

    @patch("handler.subprocess.run")
    def test_success_gzipped(self, mock_run, tmp_path):
        """Gzipped input produces a _norm.vcf.gz output path and -Oz is passed."""
        input_path = tmp_path / "sample.vcf.gz"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        mock_run.return_value = MagicMock(
            returncode=0, stdout="",
            stderr="Lines total/split/joined: 100/10/5\n",
        )

        with patch("handler.WORK_DIR", tmp_path):
            output = _run_bcftools_norm(input_path, genome_path)

        assert output == tmp_path / "sample_norm.vcf.gz"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bcftools"
        assert "-Oz" in cmd
        assert "-f" in cmd
        assert "--keep-sum" in cmd

    @patch("handler.subprocess.run")
    def test_success_uncompressed(self, mock_run, tmp_path):
        """Uncompressed .vcf input should produce a .vcf.gz output path."""
        input_path = tmp_path / "sample.vcf"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        mock_run.return_value = MagicMock(
            returncode=0, stdout="",
            stderr="Lines total/split/joined: 100/10/5\n",
        )

        with patch("handler.WORK_DIR", tmp_path):
            output = _run_bcftools_norm(input_path, genome_path)

        assert output == tmp_path / "sample_norm.vcf.gz"
        cmd = mock_run.call_args[0][0]
        assert "-Oz" in cmd

    @patch("handler.subprocess.run")
    def test_failure_raises(self, mock_run, tmp_path):
        """Non-zero bcftools exit code raises RuntimeError."""
        input_path = tmp_path / "sample.vcf.gz"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: genome mismatch")

        with patch("handler.WORK_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="bcftools norm failed"):
                _run_bcftools_norm(input_path, genome_path)

    def test_unsupported_extension_raises(self, tmp_path):
        """Input filenames that are neither .vcf nor .vcf.gz raise ValueError."""
        input_path = tmp_path / "sample.txt"
        input_path.touch()
        genome_path = tmp_path / "genome.fa"
        genome_path.touch()

        with patch("handler.WORK_DIR", tmp_path):
            with pytest.raises(ValueError, match="Unsupported input file extension"):
                _run_bcftools_norm(input_path, genome_path)


# ---------------------------------------------------------------------------
# ref/ref record removal subprocess
# ---------------------------------------------------------------------------


class TestRemoveRefRefRecords:
    """Tests for _remove_ref_ref_records subprocess execution."""

    @patch("handler.subprocess.run")
    def test_success_g_vcf_gz(self, mock_run, tmp_path):
        """.g.vcf.gz input produces a .vcf.gz output path and -m2 is passed."""
        input_path = tmp_path / "sample.g.vcf.gz"
        input_path.touch()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("handler.WORK_DIR", tmp_path):
            output = _remove_ref_ref_records(input_path)

        assert output == tmp_path / "sample.vcf.gz"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "bcftools"
        assert cmd[1] == "view"
        assert "-m2" in cmd
        assert "-Oz" in cmd

    @patch("handler.subprocess.run")
    def test_success_genome_vcf(self, mock_run, tmp_path):
        """.genome.vcf input produces a .vcf.gz output path."""
        input_path = tmp_path / "sample.genome.vcf"
        input_path.touch()

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with patch("handler.WORK_DIR", tmp_path):
            output = _remove_ref_ref_records(input_path)

        assert output == tmp_path / "sample.vcf.gz"

    @patch("handler.subprocess.run")
    def test_failure_raises(self, mock_run, tmp_path):
        """Non-zero bcftools exit code raises RuntimeError."""
        input_path = tmp_path / "sample.g.vcf.gz"
        input_path.touch()

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: bad record")

        with patch("handler.WORK_DIR", tmp_path):
            with pytest.raises(RuntimeError, match="Ref/ref removal via bcftools view failed"):
                _remove_ref_ref_records(input_path)

    def test_unsupported_extension_raises(self, tmp_path):
        """Input filenames that don't match a genome VCF suffix raise ValueError."""
        input_path = tmp_path / "sample.vcf.gz"
        input_path.touch()

        with patch("handler.WORK_DIR", tmp_path):
            with pytest.raises(ValueError, match="Unsupported input file extension"):
                _remove_ref_ref_records(input_path)


# ---------------------------------------------------------------------------
# Upload output
# ---------------------------------------------------------------------------


class TestUploadOutput:
    """Tests for _upload_output S3 key derivation logic."""

    @patch("handler.s3")
    def test_upload_output_key(self, mock_s3, tmp_path):
        """Output key is derived from OUTPUT_PREFIX and output filename."""
        output_path = tmp_path / "sample_norm.vcf.gz"
        output_path.touch()

        with patch("handler.OUTPUT_PREFIX", "output/"):
            result_key = _upload_output("my-bucket", output_path)

        assert result_key == "output/sample_norm.vcf.gz"
        mock_s3.upload_file.assert_called_once_with(
            str(output_path), "my-bucket", "output/sample_norm.vcf.gz"
        )


# ---------------------------------------------------------------------------
# Full handler (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestLambdaHandler:
    """End-to-end handler tests with mocked dependencies."""

    @patch("handler._cleanup")
    @patch("handler._upload_output", return_value="output/sample_norm.vcf.gz")
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
        """All pipeline stages are called in order and the response is well-formed."""
        mock_dl_input.return_value = Path("/tmp/vcf_work/sample.vcf.gz")
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["input"] == "s3://my-bucket/input/sample.vcf.gz"
        assert body["output"] == "s3://my-bucket/output/sample_norm.vcf.gz"

        mock_setup.assert_called_once()
        mock_dl_input.assert_called_once_with("my-bucket", "input/sample.vcf.gz")
        mock_dl_genome.assert_called_once()
        mock_norm.assert_called_once()
        mock_upload.assert_called_once()
        mock_cleanup.assert_called_once()

    @patch("handler._cleanup")
    @patch("handler._upload_output", return_value="output/sample.vcf.gz")
    @patch("handler._run_bcftools_norm")
    @patch("handler._remove_ref_ref_records")
    @patch("handler._download_genome")
    @patch("handler._download_input")
    @patch("handler._setup_work_dir")
    def test_full_flow_gvcf_removes_ref_ref_records(
        self,
        mock_setup,
        mock_dl_input,
        mock_dl_genome,
        mock_remove_ref_ref,
        mock_norm,
        mock_upload,
        mock_cleanup,
    ):
        """A .g.vcf.gz input is routed through ref/ref removal before bcftools norm,
        and the ref/ref-removed path (not the raw input) is passed to norm."""
        mock_dl_input.return_value = Path("/tmp/vcf_work/sample.g.vcf.gz")
        ref_removed_path = Path("/tmp/vcf_work/sample.vcf.gz")
        mock_remove_ref_ref.return_value = ref_removed_path
        event = {"bucket": "my-bucket", "key": "input/sample.g.vcf.gz"}

        lambda_handler(event, None)

        mock_remove_ref_ref.assert_called_once_with(input_path=mock_dl_input.return_value)
        mock_norm.assert_called_once_with(
            input_path=ref_removed_path, genome_path=mock_dl_genome.return_value
        )

    @patch("handler._cleanup")
    @patch("handler._download_input", side_effect=Exception("S3 error"))
    @patch("handler._setup_work_dir")
    def test_cleanup_on_error(self, mock_setup, mock_dl, mock_cleanup):
        """Cleanup is called even when an exception is raised mid-pipeline."""
        event = {"bucket": "my-bucket", "key": "input/sample.vcf.gz"}

        with pytest.raises(Exception, match="S3 error"):
            lambda_handler(event, None)

        # Cleanup should still be called via finally
        mock_cleanup.assert_called_once()
