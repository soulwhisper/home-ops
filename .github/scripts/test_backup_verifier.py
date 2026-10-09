"""Behavioral regressions for the Python shipped in postgres-backup-verify."""
import contextlib
import io
from pathlib import Path
import sys
import textwrap
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "kubernetes/apps/database-system/cnpg-operator/maintenance/cronjob-dr-test.yaml"
SCRIPT = textwrap.dedent(
    MANIFEST.read_text().split("          verify-backup-chain.py: |\n", 1)[1]
    .split("\n    controllers:", 1)[0]
)


def wal(logid, segment, timeline=1):
    return f"{timeline:08X}{logid:08X}{segment:08X}"


def verify(metadata, segments):
    backup = "postgres-v1/base/20261008T000000/backup.info"
    keys = [backup] + ["postgres-v1/wals/archive/" + segment for segment in segments]

    class Archive:
        def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
            selected = sorted(key for key in keys if key.startswith(Prefix))
            offset = int(ContinuationToken or 0)
            result = {
                "Contents": [{"Key": key} for key in selected[offset:offset + 2]],
                "IsTruncated": offset + 2 < len(selected),
            }
            if result["IsTruncated"]:
                result["NextContinuationToken"] = str(offset + 2)
            return result

        def get_object(self, Bucket, Key):
            if Key != backup:
                raise AssertionError("unexpected object read")
            content = "\n".join(f"{key}={value}" for key, value in metadata.items())
            return {"Body": io.BytesIO(content.encode())}

    boto3 = types.SimpleNamespace(client=lambda *args, **kwargs: Archive())
    output = io.StringIO()
    with patch.dict(sys.modules, {"boto3": boto3}), contextlib.redirect_stdout(output):
        try:
            exec(compile(SCRIPT, "verify-backup-chain.py", "exec"), {"__name__": "__main__"})
        except SystemExit as result:
            return result.code, output.getvalue()
    raise AssertionError("verifier did not exit")


class BackupVerifierTest(unittest.TestCase):
    def setUp(self):
        self.begin, self.middle, self.end = [wal(1, segment) for segment in (10, 11, 12)]
        self.metadata = {
            "begin_wal": self.begin,
            "end_wal": self.end,
            "xlog_segment_size": 16 * 1024 * 1024,
        }

    def assert_result(self, expected, metadata, segments):
        status, output = verify(metadata, segments)
        self.assertEqual(status, expected, output)
        if expected:
            self.assertIn("VERIFICATION FAILED:", output)

    def test_missing_boundary_or_interior_wal_fails(self):
        for segments in ([self.middle, self.end], [self.begin, self.middle],
                         [self.begin, self.end], []):
            with self.subTest(segments=segments):
                self.assert_result(1, self.metadata, segments)

    def test_partial_wal_is_not_complete(self):
        for suffix in (".partial", ".partial.zst"):
            with self.subTest(suffix=suffix):
                self.assert_result(1, self.metadata, [self.begin, self.middle + suffix, self.end])

    def test_complete_compressed_chain_ignores_unrelated_retention_gaps(self):
        segments = [wal(0, 1), wal(0, 4), wal(1, 1, 2), wal(1, 3, 2),
                    "00000002.history.gz", self.begin + ".gz", self.middle + ".zst",
                    self.middle, self.end, wal(2, 50)]
        self.assert_result(0, self.metadata, segments)

    def test_segment_size_controls_log_rollover(self):
        for size in (16 << 20, 32 << 20, 1 << 30):
            with self.subTest(size=size):
                last = (1 << 32) // size - 1
                begin, end = wal(1, last), wal(2, 1)
                metadata = {"begin_wal": begin, "end_wal": end, "xlog_segment_size": size}
                self.assert_result(0, metadata, [begin, wal(2, 0), end])
                self.assert_result(1, metadata, [begin, end])

    def test_missing_required_backup_metadata_fails(self):
        for field in self.metadata:
            with self.subTest(field=field):
                metadata = {key: value for key, value in self.metadata.items() if key != field}
                self.assert_result(1, metadata, [self.begin, self.middle, self.end])

    def test_incoherent_ranges_fail(self):
        for changes in ({"xlog_segment_size": 3 << 20}, {"begin_wal": wal(1, 256)},
                        {"begin_wal": wal(1, 10, 0)}, {"begin_wal": self.end, "end_wal": self.begin},
                        {"end_wal": wal(1, 12, 2)}):
            with self.subTest(changes=changes):
                self.assert_result(1, self.metadata | changes, [self.begin, self.middle, self.end])


if __name__ == "__main__":
    unittest.main()
