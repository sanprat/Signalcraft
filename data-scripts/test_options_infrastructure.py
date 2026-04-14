"""
Tests for options data infrastructure:
- dhan_client.py oi/iv/spot parsing
- parquet_writer.py schema with oi, iv, spot
- options_audit.py readiness checks
"""

import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from dhan_client import DhanClient, REQUIRED_DATA
from parquet_writer import SCHEMA, OPTIONS_SCHEMA, _raw_to_df


class TestDhanClientRequiredData:
    """Test that dhan_client includes oi, iv, spot in requiredData."""

    def test_required_data_includes_oi_iv_spot(self):
        """REQUIRED_DATA should include oi, iv, spot for v1 options."""
        assert "oi" in REQUIRED_DATA, "oi should be in REQUIRED_DATA"
        assert "iv" in REQUIRED_DATA, "iv should be in REQUIRED_DATA"
        assert "spot" in REQUIRED_DATA, "spot should be in REQUIRED_DATA"
        assert "strike" in REQUIRED_DATA


class TestDhanClientExpiryList:
    """Test expirylist endpoint."""

    def test_get_expiry_list_returns_dates(self):
        """expirylist should return list of expiry date strings."""
        import requests as req

        with patch.object(req.Session, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": {"expiryDates": ["2025-04-24", "2025-05-01", "2025-05-08"]}
            }
            mock_post.return_value = mock_resp

            client = DhanClient("test_client", "test_token")
            result = client.get_expiry_list("NIFTY")

            assert isinstance(result, list)
            assert len(result) == 3
            assert "2025-04-24" in result


class TestParquetWriterSchema:
    """Test parquet schema includes oi, iv, spot."""

    def test_options_schema_has_oi_iv_spot(self):
        """OPTIONS_SCHEMA should have oi, iv, spot columns."""
        field_names = [f.name for f in OPTIONS_SCHEMA]
        assert "oi" in field_names, "oi should be in schema"
        assert "iv" in field_names, "iv should be in schema"
        assert "spot" in field_names, "spot should be in schema"

    def test_schema_types(self):
        """Schema should have correct types."""
        oi_field = OPTIONS_SCHEMA.field("oi")
        assert oi_field.type == pa.float64(), "oi should be float64"

        iv_field = OPTIONS_SCHEMA.field("iv")
        assert iv_field.type == pa.float32(), "iv should be float32"

        spot_field = OPTIONS_SCHEMA.field("spot")
        assert spot_field.type == pa.float32(), "spot should be float32"


class TestRawToDf:
    """Test _raw_to_df handles oi/iv/spot."""

    def test_raw_to_df_with_oi_iv_spot(self):
        """_raw_to_df should parse oi, iv, spot when present."""
        raw = [
            {
                "time": "2025-04-10T09:15:00+05:30",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 1000,
                "oi": 5000.0,
                "iv": 0.15,
                "spot": 25000.0,
            }
        ]
        df = _raw_to_df(raw, include_oi_iv_spot=True)

        assert not df.empty
        assert "oi" in df.columns
        assert "iv" in df.columns
        assert "spot" in df.columns
        assert df.iloc[0]["oi"] == 5000.0
        assert df.iloc[0]["iv"] == 0.15

    def test_raw_to_df_without_oi_iv_spot(self):
        """_raw_to_df should work without oi/iv/spot columns."""
        raw = [
            {
                "time": "2025-04-10T09:15:00+05:30",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 1000,
            }
        ]
        df = _raw_to_df(raw, include_oi_iv_spot=False)

        assert not df.empty
        assert "oi" not in df.columns


class TestOptionsAudit:
    """Test options_audit.py logic."""

    def test_scan_directory_handles_missing_data(self):
        """Empty data directory should work fine."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import scan_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            scan = scan_directory(Path(tmpdir))
            # temp directory exists, so scan should report exists=True
            assert scan["exists"] == True
            assert scan["path"] == tmpdir

    def test_audit_runs_successfully(self):
        """options_audit.py should run without errors."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import main
        import argparse

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("sys.argv", ["options_audit.py", "--data-root", tmpdir]):
                result = main()
                assert result == 1  # not_ready exit code


class TestBacktestCompatibility:
    """Test that existing backtest readers work with extended schema."""

    def test_parquet_with_extra_columns_readable(self):
        """Pyarrow can read parquet with extra columns not in schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.parquet"

            df = pd.DataFrame(
                {
                    "time": pd.date_range("2025-01-01", periods=3, freq="D"),
                    "open": [100.0, 101.0, 102.0],
                    "high": [105.0, 106.0, 107.0],
                    "low": [99.0, 100.0, 101.0],
                    "close": [103.0, 104.0, 105.0],
                    "volume": [1000, 1100, 1200],
                    "oi": [5000.0, 5500.0, 6000.0],
                    "iv": [0.15, 0.16, 0.17],
                    "spot": [25000.0, 25100.0, 25200.0],
                }
            )
            df["time"] = df["time"].dt.tz_localize("Asia/Kolkata")

            table = pa.Table.from_pandas(df, schema=OPTIONS_SCHEMA)
            pa.parquet.write_table(table, path)

            read_df = pd.read_parquet(
                path, columns=["time", "open", "high", "low", "close", "volume"]
            )

            assert len(read_df) == 3
            assert list(read_df.columns) == [
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]

    def test_parquet_without_oi_iv_spot_readable(self):
        """Old parquet files (without oi/iv/spot) should still be readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_old.parquet"

            old_schema = pa.schema(
                [
                    ("time", pa.timestamp("s", tz="Asia/Kolkata")),
                    ("open", pa.float32()),
                    ("high", pa.float32()),
                    ("low", pa.float32()),
                    ("close", pa.float32()),
                    ("volume", pa.int64()),
                ]
            )

            df = pd.DataFrame(
                {
                    "time": pd.date_range("2025-01-01", periods=3, freq="D"),
                    "open": [100.0, 101.0, 102.0],
                    "high": [105.0, 106.0, 107.0],
                    "low": [99.0, 100.0, 101.0],
                    "close": [103.0, 104.0, 105.0],
                    "volume": [1000, 1100, 1200],
                }
            )
            df["time"] = df["time"].dt.tz_localize("Asia/Kolkata")

            table = pa.Table.from_pandas(df, schema=old_schema)
            pa.parquet.write_table(table, path)

            read_df = pd.read_parquet(path)

            assert len(read_df) == 3
            assert "oi" not in read_df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
