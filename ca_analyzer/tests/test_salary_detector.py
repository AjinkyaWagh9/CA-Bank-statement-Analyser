"""
Tests for BRD §7.1 pattern-based salary detection.
"""

import pandas as pd
import pytest

from ca_analyzer.transaction_engine.salary_detector import detect_salary


def _make_df(rows):
    """Build a minimal DataFrame with the columns used by detect_salary."""
    df = pd.DataFrame(rows, columns=[
        "Date", "Credit", "Counterparty", "Narration",
        "Category", "Sub_Category", "Confidence",
    ])
    df["Date"] = pd.to_datetime(df["Date"])
    df["Credit"] = df["Credit"].astype(float)
    return df


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_df():
    rows = [
        # Recurring salary counterparty — 4 monthly credits ~₹50 000 (within ±5%)
        ("2024-01-25", 50_000.00, "ACME CORP",   "SALARY JAN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ("2024-02-25", 51_000.00, "ACME CORP",   "SALARY FEB", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ("2024-03-25", 49_500.00, "ACME CORP",   "SALARY MAR", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ("2024-04-25", 50_200.00, "ACME CORP",   "SALARY APR", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        # One-off large credit — should stay untouched
        ("2024-01-10", 2_00_000.00, "PROPERTY SALE", "PROP SALE", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        # Already keyword-detected Salary — must NOT be downgraded
        ("2024-01-28", 48_000.00, "ACME CORP",   "NEFT SALARY", "Salary", "Regular Salary", "High"),
    ]
    return _make_df(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecurringSalaryDetection:
    def test_recurring_credits_flagged_as_salary(self, sample_df):
        result = detect_salary(sample_df)
        salary_rows = result[result["Counterparty"] == "ACME CORP"]
        # Row 5 (index 5) is the existing High-confidence Salary — skip it
        detected = salary_rows[salary_rows["Sub_Category"] == "Potential Salary"]
        assert len(detected) == 4, f"Expected 4 detected rows, got {len(detected)}"

    def test_category_set_to_salary(self, sample_df):
        result = detect_salary(sample_df)
        detected = result[result["Sub_Category"] == "Potential Salary"]
        assert (detected["Category"] == "Salary").all()

    def test_sub_category_set(self, sample_df):
        result = detect_salary(sample_df)
        detected = result[result["Sub_Category"] == "Potential Salary"]
        assert (detected["Sub_Category"] == "Potential Salary").all()

    def test_confidence_set_to_medium(self, sample_df):
        result = detect_salary(sample_df)
        detected = result[result["Sub_Category"] == "Potential Salary"]
        assert (detected["Confidence"] == "Medium").all()


class TestOneOffCreditUntouched:
    def test_one_off_credit_not_flagged(self, sample_df):
        result = detect_salary(sample_df)
        one_off = result[result["Counterparty"] == "PROPERTY SALE"].iloc[0]
        assert one_off["Category"] == "Miscellaneous"
        assert one_off["Sub_Category"] == "Miscellaneous Inflow"
        assert one_off["Confidence"] == "Low"


class TestExistingSalaryNotDowngraded:
    def test_keyword_salary_preserved(self, sample_df):
        result = detect_salary(sample_df)
        existing = result[(result["Counterparty"] == "ACME CORP") & (result["Sub_Category"] == "Regular Salary")].iloc[0]
        assert existing["Category"] == "Salary"
        assert existing["Sub_Category"] == "Regular Salary"
        assert existing["Confidence"] == "High"


class TestEdgeCases:
    def test_returns_copy_not_inplace(self, sample_df):
        original_cats = sample_df["Category"].copy()
        detect_salary(sample_df)
        pd.testing.assert_series_equal(sample_df["Category"], original_cats)

    def test_index_and_order_preserved(self, sample_df):
        result = detect_salary(sample_df)
        assert list(result.index) == list(sample_df.index)
        assert list(result.columns) == list(sample_df.columns)

    def test_skip_blank_counterparty(self):
        rows = [
            ("2024-01-25", 50_000, "",        "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-02-25", 50_000, "",        "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-03-25", 50_000, "",        "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-04-25", 50_000, "",        "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ]
        df = _make_df(rows)
        result = detect_salary(df)
        assert (result["Category"] == "Miscellaneous").all()

    def test_skip_others_counterparty(self):
        rows = [
            ("2024-01-25", 50_000, "OTHERS",  "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-02-25", 50_000, "OTHERS",  "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-03-25", 50_000, "OTHERS",  "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ]
        df = _make_df(rows)
        result = detect_salary(df)
        assert (result["Category"] == "Miscellaneous").all()

    def test_only_two_months_not_flagged(self):
        rows = [
            ("2024-01-25", 50_000, "VENDOR X", "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-02-25", 50_000, "VENDOR X", "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ]
        df = _make_df(rows)
        result = detect_salary(df)
        assert (result["Category"] == "Miscellaneous").all()

    def test_outside_5pct_band_not_flagged(self):
        """Two months match the band but one is wildly different — only 2 qualify."""
        rows = [
            ("2024-01-25",  50_000, "VENDOR Y", "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-02-25",  50_000, "VENDOR Y", "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
            ("2024-03-25", 100_000, "VENDOR Y", "TXN", "Miscellaneous", "Miscellaneous Inflow", "Low"),
        ]
        df = _make_df(rows)
        result = detect_salary(df)
        # median is 50000; 100000 is outside band. Only 2 months qualify → no detection.
        assert (result["Category"] == "Miscellaneous").all()
