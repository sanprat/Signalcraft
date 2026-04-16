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
    """Test expirylist endpoint.

    Note: Current test uses mock. Run integration test on VPS with real credentials:
    python -c "
    import os, sys
    sys.path.insert(0, 'data-scripts')
    from dhan_client import DhanClient
    c = DhanClient(os.environ['DHAN_CLIENT_ID'], os.environ['DHAN_ACCESS_TOKEN'])
    r = c.get_expiry_list('NIFTY')
    print('expirylist response:', r)
    assert isinstance(r, list) and len(r) > 0
    "
    """

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

    def test_get_expiry_list_list_response_shape(self):
        """expirylist should handle list response shape: {"data": ["2025-04-24"]}"""
        import requests as req

        with patch.object(req.Session, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": ["2025-04-24", "2025-05-01"]}
            mock_post.return_value = mock_resp

            client = DhanClient("test_client", "test_token")
            result = client.get_expiry_list("NIFTY")

            assert isinstance(result, list)
            assert len(result) == 2
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

    def test_ec10_counts_as_ec2plus_not_ec1(self):
        """ec10, ec11 should be counted as ec2+, not ec1."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import count_expiry_families

        scan = {
            "path": "/tmp",
            "underlying": {
                "NIFTY": {"exists": True, "files": {}},
                "BANKNIFTY": {"exists": True, "files": {}},
                "FINNIFTY": {"exists": True, "files": {}},
            },
            "candles": {
                "NIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {
                            "1min": {
                                "exists": True,
                                "files": {
                                    "dhan_ec0_25000": "",
                                    "dhan_ec1_25000": "",
                                    "dhan_ec10_25000": "",
                                    "dhan_ec11_25000": "",
                                },
                            }
                        },
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "BANKNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "FINNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
            },
        }
        families = count_expiry_families(scan)

        assert families["NIFTY"]["CE"]["1min"]["ec0"] == 1
        assert families["NIFTY"]["CE"]["1min"]["ec1"] == 1
        assert families["NIFTY"]["CE"]["1min"]["ec2+"] == 2

    def test_timestamp_overlap_check(self):
        """Timestamp overlap should check date ranges, not just presence."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import determine_readiness

        scan = {
            "path": "/tmp",
            "underlying": {
                "NIFTY": {"exists": True, "files": {"1min": ""}},
                "BANKNIFTY": {"exists": True, "files": {"5min": ""}},
                "FINNIFTY": {"exists": True, "files": {"15min": ""}},
            },
            "candles": {
                "NIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {
                            "1min": {"exists": True, "files": {"dhan_ec1_25000": ""}}
                        },
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "BANKNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "FINNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
            },
        }
        timestamps = {
            "underlying": {
                "NIFTY/1min": {
                    "min": "2025-01-01T00:00:00",
                    "max": "2025-01-31T23:59:59",
                }
            },
            "options": {
                "NIFTY/CE/1min/dhan_ec1_25000": {
                    "min": "2025-02-01T00:00:00",
                    "max": "2025-02-28T23:59:59",
                }
            },
        }
        families = {
            "NIFTY": {
                "CE": {
                    "1min": {"ec0": 0, "ec1": 1, "ec2+": 1},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
                "PE": {
                    "1min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
            },
            "BANKNIFTY": {
                "CE": {
                    "1min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
                "PE": {
                    "1min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
            },
            "FINNIFTY": {
                "CE": {
                    "1min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
                "PE": {
                    "1min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "5min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                    "15min": {"ec0": 0, "ec1": 0, "ec2+": 0},
                },
            },
        }
        verdict, findings = determine_readiness(scan, timestamps, families, True)

        assert any("timestamp overlap" in f for f in findings)

    def test_timestamp_overlap_detects_overlap(self):
        """Timestamp overlap should be detected when ranges overlap."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import determine_readiness

        scan = {
            "path": "/tmp",
            "underlying": {
                "NIFTY": {"exists": True, "files": {"1min": ""}},
                "BANKNIFTY": {"exists": True, "files": {}},
                "FINNIFTY": {"exists": True, "files": {}},
            },
            "candles": {
                "NIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {
                            "1min": {"exists": True, "files": {"dhan_ec1_25000": ""}}
                        },
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "BANKNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
                "FINNIFTY": {
                    "CE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                    "PE": {
                        "exists": True,
                        "intervals": {"1min": {"exists": True, "files": {}}},
                    },
                },
            },
        }
        timestamps = {
            "underlying": {
                "NIFTY/1min": {
                    "min": "2025-01-15T09:00:00",
                    "max": "2025-01-15T15:30:00",
                }
            },
            "options": {
                "NIFTY/CE/1min/dhan_ec1_25000": {
                    "min": "2025-01-15T09:15:00",
                    "max": "2025-01-15T15:25:00",
                }
            },
        }
        families = {
            "NIFTY": {
                "CE": {"1min": {"ec0": 0, "ec1": 1, "ec2+": 0}},
                "PE": {"1min": {"ec0": 0, "ec1": 0, "ec2+": 0}},
            },
            "BANKNIFTY": {
                "CE": {"1min": {"ec0": 0, "ec1": 0, "ec2+": 0}},
                "PE": {"1min": {"ec0": 0, "ec1": 0, "ec2+": 0}},
            },
            "FINNIFTY": {
                "CE": {"1min": {"ec0": 0, "ec1": 0, "ec2+": 0}},
                "PE": {"1min": {"ec0": 0, "ec1": 0, "ec2+": 0}},
            },
        }
        verdict, findings = determine_readiness(scan, timestamps, families, True)

        assert "timestamp overlap" not in " ".join(findings)

    def test_scan_directory_handles_missing_data(self):
        """Empty data directory should work fine."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "data-scripts"))
        from options_audit import scan_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            scan = scan_directory(Path(tmpdir))
            assert scan["exists"] == True

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


class TestDhanBulkLoaderTimestampMerge:
    """Test save_dhan_candles() handles tz-aware merge correctly."""

    def test_merge_tz_aware_existing_with_tz_naive_new(self):
        """Merging tz-aware existing parquet with tz-naive new data should not crash."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        import dhan_bulk_loader

        with tempfile.TemporaryDirectory() as tmpdir:
            import pyarrow.parquet as pq
            import pyarrow as pa

            tmpdir_path = Path(tmpdir)
            candles_dir = tmpdir_path / "candles" / "NIFTY" / "CE" / "1min"
            candles_dir.mkdir(parents=True, exist_ok=True)
            out_path = candles_dir / "dhan_ec1_25000.parquet"

            existing_df = pd.DataFrame(
                {
                    "time": pd.to_datetime(
                        ["2025-04-10T09:15:00", "2025-04-10T09:16:00"]
                    ).tz_localize("Asia/Kolkata"),
                    "open": [100.0, 101.0],
                    "high": [105.0, 106.0],
                    "low": [99.0, 100.0],
                    "close": [103.0, 104.0],
                    "volume": [1000, 1100],
                }
            )
            table = pa.Table.from_pandas(existing_df)
            pq.write_table(table, out_path)

            new_candles = [
                {
                    "time": "2025-04-10T09:15:00+05:30",
                    "strike": 25000,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 103.0,
                    "volume": 1000,
                },
                {
                    "time": "2025-04-10T09:16:00+05:30",
                    "strike": 25000,
                    "open": 101.0,
                    "high": 106.0,
                    "low": 100.0,
                    "close": 104.0,
                    "volume": 1100,
                },
                {
                    "time": "2025-04-10T09:17:00+05:30",
                    "strike": 25000,
                    "open": 102.0,
                    "high": 107.0,
                    "low": 101.0,
                    "close": 105.0,
                    "volume": 1200,
                },
            ]

            orig_base_dir = dhan_bulk_loader.BASE_DIR
            dhan_bulk_loader.BASE_DIR = tmpdir_path

            try:
                total = dhan_bulk_loader.save_dhan_candles(
                    new_candles, "NIFTY", "CE", "1min", 1
                )
            finally:
                dhan_bulk_loader.BASE_DIR = orig_base_dir

            result_df = pd.read_parquet(out_path)

            assert len(result_df) == 5, (
                f"Expected 5 rows (2 existing + 3 new), got {len(result_df)}"
            )
            assert result_df["time"].is_monotonic_increasing, (
                "Timestamps should be sorted"
            )
            assert result_df["time"].dt.tz is None, "Time should be naive"


class TestDhanClientActiveInstrumentResolution:
    """Test active weekly option instrument resolution."""

    def test_resolve_active_weekly_options_returns_ce_and_pe(self):
        """resolve_active_weekly_options should return contract metadata for CE and PE."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from dhan_client import DhanClient

        client = DhanClient("test_client", "test_token")
        result = client.resolve_active_weekly_options(
            index="NIFTY",
            expiry_date="2025-04-24",
            strikes=[25000, 25100],
            option_type="CE",
        )
        assert isinstance(result, list)
        if result:
            assert "security_id" in result[0]

    def test_get_active_option_intraday_method_exists(self):
        """get_active_option_intraday method should exist."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        from dhan_client import DhanClient

        client = DhanClient("test_client", "test_token")
        assert hasattr(client, "get_active_option_intraday")
        assert callable(client.get_active_option_intraday)


class TestDailyUpdaterLiveOptions:
    """Test daily_updater.py --fno-live-only uses active instrument resolution."""

    def test_fno_live_options_uses_active_instrument_resolution(self):
        """update_fno_live_options should use resolve_active_weekly_options, not get_expired_options_full."""
        import sys
        from unittest.mock import MagicMock
        from datetime import date, timedelta

        sys.path.insert(0, str(Path(__file__).parent))
        import daily_updater

        tomorrow = date.today() + timedelta(days=1)
        future_expiry = tomorrow.strftime("%Y-%m-%d")

        mock_client = MagicMock()
        mock_client.derive_active_expiry_from_master.return_value = future_expiry
        mock_client.get_expiry_list.return_value = [future_expiry]
        mock_client.resolve_active_weekly_options.return_value = [
            {
                "security_id": "12345",
                "exchange_segment": "NSE_FNO",
                "instrument": "OPTIDX",
                "strike": 25000,
                "option_type": "CE",
                "expiry_date": future_expiry,
            }
        ]
        mock_client.get_active_option_intraday.return_value = [
            {
                "time": "2025-04-24T09:15:00+05:30",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 1000,
                "oi": 5000.0,
            }
        ]
        mock_client.get_expired_options_full = MagicMock()

        end_date = date.today()
        daily_updater.update_fno_live_options(mock_client, end_date, dry_run=False)

        mock_client.resolve_active_weekly_options.assert_called()
        mock_client.get_active_option_intraday.assert_called()
        mock_client.get_expired_options_full.assert_not_called()


class TestOptionsAuditEc0:
    """Test options_audit.py handles ec0 data correctly."""

    def test_audit_no_ec0_warning_when_recent_ec0_exists(self):
        """When recent ec0 files exist, no warning should be added."""
        import sys
        import tempfile
        from pathlib import Path
        from datetime import datetime, timedelta

        sys.path.insert(0, str(Path(__file__).parent))
        import options_audit

        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)

            recent_time = datetime.now() - timedelta(days=1)
            for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                for opt in ["CE", "PE"]:
                    for iv in ["1min"]:
                        dirpath = data_root / "candles" / idx / opt / iv
                        dirpath.mkdir(parents=True)

                        df = pd.DataFrame(
                            {
                                "time": pd.date_range(
                                    recent_time, periods=10, freq="min"
                                ),
                                "open": [100.0] * 10,
                                "high": [105.0] * 10,
                                "low": [99.0] * 10,
                                "close": [103.0] * 10,
                                "volume": [1000] * 10,
                            }
                        )
                        df.to_parquet(dirpath / "dhan_ec0_25000.parquet")

            for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                ud = data_root / "underlying" / idx
                ud.mkdir(parents=True)
                df = pd.DataFrame(
                    {
                        "time": pd.date_range(recent_time, periods=10, freq="min"),
                        "open": [25000.0] * 10,
                        "high": [25100.0] * 10,
                        "low": [24900.0] * 10,
                        "close": [25050.0] * 10,
                        "volume": [10000] * 10,
                    }
                )
                df.to_parquet(ud / "1min.parquet")

            scan = options_audit.scan_directory(data_root)
            timestamps = options_audit.analyze_timestamps(scan)
            families = options_audit.count_expiry_families(scan)

            verdict, findings = options_audit.determine_readiness(
                scan, timestamps, families, updater_wired=True
            )

            ec0_warning = [f for f in findings if "ec0" in f.lower()]
            assert len(ec0_warning) == 0, (
                f"Expected no ec0 warnings, got: {ec0_warning}"
            )


class TestDhanClientInstrumentMasterNormalization:
    """Test dhan_client handles different instrument master column formats."""

    def test_normalize_spaced_column_names(self):
        """_normalize_instrument_master_columns should map spaced column names."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent))
        from dhan_client import DhanClient

        df = pd.DataFrame(
            {
                "Exchange Segment": ["NSE_FNO"],
                "Instrument": ["OPTIDX"],
                "Security Id": ["12345"],
                "Strike Price": [25000],
                "Option Type": ["CALL"],
                "Expiry Date": ["24-APR-2025"],
                "DRV Underlying Scrip Code": [13],
            }
        )

        client = DhanClient("test", "test")
        normalized = client._normalize_instrument_master_columns(df)

        assert "exchange_segment" in normalized.columns
        assert "security_id" in normalized.columns
        assert "strike_price" in normalized.columns
        assert "option_type" in normalized.columns

    def test_normalize_camel_case_column_names(self):
        """_normalize_instrument_master_columns should map camelCase column names."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent))
        from dhan_client import DhanClient

        df = pd.DataFrame(
            {
                "ExchangeSegment": ["NSE_FNO"],
                "Instrument": ["OPTIDX"],
                "SecurityId": ["12345"],
                "StrikePrice": [25000],
                "OptionType": ["CALL"],
                "ExpiryDate": ["24-APR-2025"],
                "DRVUnderlyingScripCode": [13],
            }
        )

        client = DhanClient("test", "test")
        normalized = client._normalize_instrument_master_columns(df)

        assert "exchange_segment" in normalized.columns
        assert "security_id" in normalized.columns
        assert "strike_price" in normalized.columns

    def test_normalize_uppercase_snake_case_column_names(self):
        """_normalize_instrument_master_columns should map UPPER_SNAKE_CASE names."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent))
        from dhan_client import DhanClient

        df = pd.DataFrame(
            {
                "SEGMENT": ["NSE_FNO"],
                "INSTRUMENT": ["OPTIDX"],
                "SECURITY_ID": ["12345"],
                "UNDERLYING_SECURITY_ID": [13],
                "UNDERLYING_SYMBOL": ["NIFTY"],
                "STRIKE_PRICE": [25000],
                "OPTION_TYPE": ["CE"],
                "SM_EXPIRY_DATE": ["24-APR-2025"],
            }
        )

        client = DhanClient("test", "test")
        normalized = client._normalize_instrument_master_columns(df)

        assert "segment" in normalized.columns
        assert "instrument" in normalized.columns
        assert "security_id" in normalized.columns
        assert "underlying_security_id" in normalized.columns
        assert "underlying_symbol" in normalized.columns
        assert "strike_price" in normalized.columns
        assert "option_type" in normalized.columns
        assert "expiry_date" in normalized.columns


class TestCurrentWeekExpirySelection:
    """Test daily_updater.py selects the correct current-week expiry."""

    def test_selects_current_week_not_next_future(self):
        """Should select expiry where week_start <= end_date <= expiry_date."""
        import sys
        from unittest.mock import MagicMock
        from datetime import date, timedelta
        import pandas as pd

        sys.path.insert(0, str(Path(__file__).parent))
        import daily_updater

        today = date(2025, 4, 14)
        monday = date(2025, 4, 14)
        friday = date(2025, 4, 18)
        next_monday = date(2025, 4, 21)
        following_monday = date(2025, 4, 28)

        expiry_list = [
            friday.strftime("%Y-%m-%d"),
            next_monday.strftime("%Y-%m-%d"),
            following_monday.strftime("%Y-%m-%d"),
        ]

        mock_client = MagicMock()
        mock_client.derive_active_expiry_from_master.return_value = friday.strftime(
            "%Y-%m-%d"
        )
        mock_client.get_expiry_list.return_value = expiry_list
        mock_client.resolve_active_weekly_options.return_value = [
            {
                "security_id": "12345",
                "exchange_segment": "NSE_FNO",
                "instrument": "OPTIDX",
                "strike": 25000,
                "option_type": "CE",
                "expiry_date": friday.strftime("%Y-%m-%d"),
            }
        ]
        mock_client.get_active_option_intraday.return_value = []

        daily_updater.update_fno_live_options(mock_client, friday, dry_run=False)

        mock_client.resolve_active_weekly_options.assert_called()
        call_args = mock_client.resolve_active_weekly_options.call_args
        assert call_args[1]["expiry_date"] == friday.strftime("%Y-%m-%d")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
