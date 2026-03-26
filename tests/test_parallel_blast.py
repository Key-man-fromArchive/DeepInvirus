"""Tests for bin/parallel_blast.py.

Tests cover:
- FASTA record counting
- FASTA chunk splitting (edge cases: empty, single record, more chunks than records)
- BLAST command building for blastn / blastx / diamond
- Result merging logic
- CLI argument parsing
- RAM disk flag validation
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Ensure bin/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))

import parallel_blast  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FASTA = """\
>seq1
ATCGATCGATCGATCG
>seq2
GGGGCCCCAAAATTTT
>seq3
ACGTACGTACGTACGT
>seq4
TTTTAAAACCCCGGGG
>seq5
ATATATATATATATAT
"""

SAMPLE_FASTA_SINGLE = """\
>only_one
ATCGATCGATCG
"""

SAMPLE_FASTA_EMPTY = ""


@pytest.fixture()
def fasta_file(tmp_path: Path) -> str:
    """Write a 5-record FASTA to a temp file."""
    p = tmp_path / "input.fasta"
    p.write_text(SAMPLE_FASTA)
    return str(p)


@pytest.fixture()
def fasta_single(tmp_path: Path) -> str:
    """Write a 1-record FASTA to a temp file."""
    p = tmp_path / "single.fasta"
    p.write_text(SAMPLE_FASTA_SINGLE)
    return str(p)


@pytest.fixture()
def fasta_empty(tmp_path: Path) -> str:
    """Write an empty FASTA to a temp file."""
    p = tmp_path / "empty.fasta"
    p.write_text(SAMPLE_FASTA_EMPTY)
    return str(p)


# ---------------------------------------------------------------------------
# count_fasta_records
# ---------------------------------------------------------------------------


class TestCountFastaRecords:
    """Tests for count_fasta_records()."""

    def test_count_normal(self, fasta_file: str) -> None:
        assert parallel_blast.count_fasta_records(fasta_file) == 5

    def test_count_single(self, fasta_single: str) -> None:
        assert parallel_blast.count_fasta_records(fasta_single) == 1

    def test_count_empty(self, fasta_empty: str) -> None:
        assert parallel_blast.count_fasta_records(fasta_empty) == 0


# ---------------------------------------------------------------------------
# chunk_fasta
# ---------------------------------------------------------------------------


class TestChunkFasta:
    """Tests for chunk_fasta()."""

    def test_chunk_into_requested_parts(self, fasta_file: str, tmp_path: Path) -> None:
        chunks = parallel_blast.chunk_fasta(fasta_file, 3, temp_dir=str(tmp_path))
        assert len(chunks) == 3
        # All records should be preserved across chunks
        total = 0
        for chunk in chunks:
            total += parallel_blast.count_fasta_records(chunk)
        assert total == 5

    def test_chunk_more_than_records(self, fasta_file: str, tmp_path: Path) -> None:
        """Requesting 100 chunks from 5 records should yield 5 chunks."""
        chunks = parallel_blast.chunk_fasta(fasta_file, 100, temp_dir=str(tmp_path))
        assert len(chunks) == 5
        total = 0
        for chunk in chunks:
            total += parallel_blast.count_fasta_records(chunk)
        assert total == 5

    def test_chunk_single_record(self, fasta_single: str, tmp_path: Path) -> None:
        chunks = parallel_blast.chunk_fasta(fasta_single, 4, temp_dir=str(tmp_path))
        assert len(chunks) == 1
        assert parallel_blast.count_fasta_records(chunks[0]) == 1

    def test_chunk_empty_file(self, fasta_empty: str, tmp_path: Path) -> None:
        chunks = parallel_blast.chunk_fasta(fasta_empty, 4, temp_dir=str(tmp_path))
        assert chunks == []

    def test_chunk_one_chunk(self, fasta_file: str, tmp_path: Path) -> None:
        """Single chunk should contain all records."""
        chunks = parallel_blast.chunk_fasta(fasta_file, 1, temp_dir=str(tmp_path))
        assert len(chunks) == 1
        assert parallel_blast.count_fasta_records(chunks[0]) == 5

    def test_chunk_content_integrity(self, fasta_file: str, tmp_path: Path) -> None:
        """Verify that chunk content is valid FASTA (records start with >)."""
        chunks = parallel_blast.chunk_fasta(fasta_file, 2, temp_dir=str(tmp_path))
        for chunk_path in chunks:
            with open(chunk_path) as fh:
                first_line = fh.readline()
            assert first_line.startswith(">"), (
                f"Chunk {chunk_path} does not start with >"
            )

    def test_chunk_cleanup(self, fasta_file: str, tmp_path: Path) -> None:
        """Chunks should be real files that can be removed."""
        chunks = parallel_blast.chunk_fasta(fasta_file, 3, temp_dir=str(tmp_path))
        for c in chunks:
            assert os.path.isfile(c)
            os.remove(c)
            assert not os.path.isfile(c)


# ---------------------------------------------------------------------------
# _build_blast_cmd
# ---------------------------------------------------------------------------


class TestBuildBlastCmd:
    """Tests for _build_blast_cmd()."""

    def test_blastn_cmd(self) -> None:
        cmd = parallel_blast._build_blast_cmd(
            program="blastn",
            query="/tmp/q.fa",
            db="/db/nt",
            out="/tmp/out.tsv",
            threads=4,
            evalue="1e-5",
            max_target_seqs=10,
            outfmt="6 qseqid sseqid pident",
            extra_args=[],
        )
        assert cmd[0] == "blastn"
        assert "-query" in cmd
        assert cmd[cmd.index("-query") + 1] == "/tmp/q.fa"
        assert "-db" in cmd
        assert cmd[cmd.index("-db") + 1] == "/db/nt"
        assert "-num_threads" in cmd
        assert cmd[cmd.index("-num_threads") + 1] == "4"
        assert "-evalue" in cmd
        assert cmd[cmd.index("-evalue") + 1] == "1e-5"
        assert "-outfmt" in cmd
        assert cmd[cmd.index("-outfmt") + 1] == "6 qseqid sseqid pident"

    def test_blastx_cmd(self) -> None:
        cmd = parallel_blast._build_blast_cmd(
            program="blastx",
            query="/tmp/q.fa",
            db="/db/nr",
            out="/tmp/out.tsv",
            threads=2,
            evalue="1e-10",
            max_target_seqs=5,
            outfmt="6 qseqid sseqid evalue",
            extra_args=[],
        )
        assert cmd[0] == "blastx"
        assert "-num_threads" in cmd

    def test_diamond_cmd(self) -> None:
        cmd = parallel_blast._build_blast_cmd(
            program="diamond",
            query="/tmp/q.fa",
            db="/db/viral.dmnd",
            out="/tmp/out.tsv",
            threads=8,
            evalue="1e-10",
            max_target_seqs=5,
            outfmt="6 qseqid sseqid pident length",
            extra_args=[],
        )
        assert cmd[0] == "diamond"
        assert cmd[1] == "blastx"
        assert "--query" in cmd
        assert "--threads" in cmd
        assert cmd[cmd.index("--threads") + 1] == "8"
        # Diamond outfmt fields are split
        fmt_idx = cmd.index("--outfmt")
        assert cmd[fmt_idx + 1] == "6"
        assert cmd[fmt_idx + 2] == "qseqid"

    def test_diamond_extra_args(self) -> None:
        cmd = parallel_blast._build_blast_cmd(
            program="diamond",
            query="/tmp/q.fa",
            db="/db/viral.dmnd",
            out="/tmp/out.tsv",
            threads=1,
            evalue="1e-3",
            max_target_seqs=1,
            outfmt="6 qseqid",
            extra_args=["--sensitive", "--block-size", "4"],
        )
        assert "--sensitive" in cmd
        assert "--block-size" in cmd
        assert "4" in cmd

    def test_unsupported_program(self) -> None:
        with pytest.raises(ValueError, match="Unsupported program"):
            parallel_blast._build_blast_cmd(
                program="tblastn",
                query="/tmp/q.fa",
                db="/db/nt",
                out="/tmp/out.tsv",
                threads=1,
                evalue="1e-10",
                max_target_seqs=5,
                outfmt="6",
                extra_args=[],
            )


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for CLI argument parsing and main()."""

    def test_help_exits_zero(self) -> None:
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            parallel_blast.build_parser().parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_required_args(self) -> None:
        """Missing required args should cause exit code 2."""
        with pytest.raises(SystemExit) as exc_info:
            parallel_blast.build_parser().parse_args([])
        assert exc_info.value.code == 2

    def test_parse_full_args(self) -> None:
        args = parallel_blast.build_parser().parse_args([
            "--query", "contigs.fa",
            "--db", "viral_nt",
            "--output", "results.tsv",
            "--program", "blastn",
            "--num-chunks", "16",
            "--threads-per-chunk", "2",
            "--use-ramdisk",
            "--evalue", "1e-5",
            "--max-target-seqs", "10",
            "--outfmt", "6 qseqid sseqid pident",
        ])
        assert args.query == "contigs.fa"
        assert args.db == "viral_nt"
        assert args.output == "results.tsv"
        assert args.program == "blastn"
        assert args.num_chunks == 16
        assert args.threads_per_chunk == 2
        assert args.use_ramdisk is True
        assert args.evalue == "1e-5"
        assert args.max_target_seqs == 10
        assert args.outfmt == "6 qseqid sseqid pident"

    def test_defaults(self) -> None:
        args = parallel_blast.build_parser().parse_args([
            "--query", "q.fa",
            "--db", "db",
            "--output", "o.tsv",
        ])
        assert args.program == "blastn"
        assert args.num_chunks == 0  # auto
        assert args.threads_per_chunk == 1
        assert args.use_ramdisk is False
        assert args.evalue == "1e-10"
        assert args.max_target_seqs == 5
        assert args.verbose == 0

    def test_main_missing_query(self, tmp_path: Path) -> None:
        """main() should return 1 if query file does not exist."""
        rc = parallel_blast.main([
            "--query", str(tmp_path / "nonexistent.fa"),
            "--db", "/db/nt",
            "--output", str(tmp_path / "out.tsv"),
            "-v",
        ])
        assert rc == 1


# ---------------------------------------------------------------------------
# run_parallel_blast (integration-style, with mocked subprocess)
# ---------------------------------------------------------------------------


class TestRunParallelBlast:
    """Integration tests for run_parallel_blast with mocked BLAST execution."""

    def test_empty_query_produces_empty_output(
        self, fasta_empty: str, tmp_path: Path
    ) -> None:
        output = str(tmp_path / "out.tsv")
        result = parallel_blast.run_parallel_blast(
            query=fasta_empty,
            db="/fake/db",
            output=output,
        )
        assert result == output
        assert os.path.isfile(output)
        assert os.path.getsize(output) == 0

    def test_nonexistent_query_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parallel_blast.run_parallel_blast(
                query=str(tmp_path / "ghost.fa"),
                db="/fake/db",
                output=str(tmp_path / "out.tsv"),
            )

    def test_all_chunks_fail_raises(self, fasta_file: str, tmp_path: Path) -> None:
        """If every BLAST chunk fails, RuntimeError should be raised."""
        output = str(tmp_path / "out.tsv")

        def fake_blast(args_tuple):
            return None  # simulate failure

        with mock.patch.object(parallel_blast, "_run_blast_on_chunk", fake_blast):
            with mock.patch("parallel_blast.Pool") as mock_pool_cls:
                mock_pool = mock.MagicMock()
                mock_pool_cls.return_value.__enter__ = mock.Mock(return_value=mock_pool)
                mock_pool_cls.return_value.__exit__ = mock.Mock(return_value=False)
                mock_pool.map.return_value = [None, None]

                with pytest.raises(RuntimeError, match="All BLAST chunks failed"):
                    parallel_blast.run_parallel_blast(
                        query=fasta_file,
                        db="/fake/db",
                        output=output,
                        num_chunks=2,
                    )

    def test_successful_merge(self, fasta_file: str, tmp_path: Path) -> None:
        """Mock BLAST to write known output, verify merge."""
        output = str(tmp_path / "merged.tsv")

        # Create fake BLAST output files
        fake_results = []
        for i in range(2):
            p = tmp_path / f"fake_chunk_{i}.tsv"
            p.write_text(f"seq{i}\thit{i}\t99.0\t100\n")
            fake_results.append(str(p))

        def fake_blast(args_tuple):
            # Write result to the expected output path
            _, _, out_path, *_ = args_tuple
            idx = int(out_path.split("_chunk_")[1].split(".")[0])
            if idx < len(fake_results):
                with open(fake_results[idx]) as src, open(out_path, "w") as dst:
                    dst.write(src.read())
            return out_path

        with mock.patch("parallel_blast.Pool") as mock_pool_cls:
            mock_pool = mock.MagicMock()
            mock_pool_cls.return_value.__enter__ = mock.Mock(return_value=mock_pool)
            mock_pool_cls.return_value.__exit__ = mock.Mock(return_value=False)
            mock_pool.map.side_effect = lambda fn, args: [fn(a) for a in args]

            with mock.patch.object(
                parallel_blast, "_run_blast_on_chunk", side_effect=fake_blast
            ):
                result = parallel_blast.run_parallel_blast(
                    query=fasta_file,
                    db="/fake/db",
                    output=output,
                    num_chunks=2,
                )

        assert result == output
        content = Path(output).read_text()
        assert "seq0" in content
        assert "seq1" in content


# ---------------------------------------------------------------------------
# _safe_remove
# ---------------------------------------------------------------------------


class TestSafeRemove:
    """Tests for _safe_remove()."""

    def test_removes_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "to_delete.txt"
        p.write_text("hello")
        parallel_blast._safe_remove(str(p))
        assert not p.exists()

    def test_nonexistent_file_no_error(self, tmp_path: Path) -> None:
        parallel_blast._safe_remove(str(tmp_path / "ghost.txt"))
        # should not raise


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_default_level_warning(self) -> None:
        parallel_blast.setup_logging(0)
        assert parallel_blast.logger.level == logging.WARNING

    def test_info_level(self) -> None:
        parallel_blast.setup_logging(1)
        assert parallel_blast.logger.level == logging.INFO

    def test_debug_level(self) -> None:
        parallel_blast.setup_logging(2)
        assert parallel_blast.logger.level == logging.DEBUG
