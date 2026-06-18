"""
Tests for ca_analyzer.transaction_engine.llm_classifier.

All tests mock the OpenAI SDK — no real API calls are made.
"""
import logging
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df():
    """Three-row DataFrame: two Others/Low rows + one already-classified Salary row."""
    return pd.DataFrame(
        {
            "Narration": [
                "UNKNOWN VENDOR XYZ",
                "SOME RANDOM DEBIT 123",
                "SALARY CREDIT FROM EMPLOYER",
            ],
            "Debit": [500.0, 1200.0, 0.0],
            "Credit": [0.0, 0.0, 60000.0],
            "Category": ["Others", "Others", "Salary"],
            "Sub_Category": ["Other Expense", "Other Expense", "Monthly Salary"],
            "Confidence": ["Low", "Low", "High"],
            "Match_Reason": ["no rule matched", "no rule matched", "keyword: 'salary'"],
        }
    )


# ---------------------------------------------------------------------------
# Test 1 — flag disabled: df returned unchanged
# ---------------------------------------------------------------------------

def test_flag_off_returns_df_unchanged():
    """When llm.enabled is false, classify_with_llm must return df unchanged."""
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df()

    # Patch the config singleton so llm.enabled == False
    with patch.object(
        llm_classifier.config,
        "thresholds",
        {"llm": {"enabled": False, "provider": "openai", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY", "chunk_size": 25, "max_rows": 2000}},
    ):
        result = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# Test 2 — missing API key: df returned unchanged, warning logged
# ---------------------------------------------------------------------------

def test_missing_key_returns_df_unchanged_with_warning(caplog):
    """
    When provider=openai and NVIDIA_API_KEY is absent, classify_with_llm must:
    - return df unchanged
    - log a warning naming the missing env var (NVIDIA_API_KEY)
    """
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df()

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "moonshotai/kimi-k2.6",
            "api_key_env": "NVIDIA_API_KEY",
            "temperature": 0,
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    import sys    # noqa: PLC0415
    import types  # noqa: PLC0415

    # Create a stub 'openai' module so the import succeeds
    stub_openai = types.ModuleType("openai")

    class _FakeOpenAIClient:
        pass

    stub_openai.OpenAI = _FakeOpenAIClient

    env_without_key = {
        k: v
        for k, v in os.environ.items()
        if k != "NVIDIA_API_KEY"
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.dict(os.environ, env_without_key, clear=True):
            with patch.dict(sys.modules, {"openai": stub_openai}):
                with caplog.at_level(logging.WARNING, logger="llm_classifier"):
                    result = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result, df)
    warning_messages = " ".join(caplog.messages)
    assert any(
        phrase in warning_messages
        for phrase in ("NVIDIA_API_KEY", "API key", "api key", "No API key", "no api key")
    ), f"Expected NVIDIA_API_KEY-related warning, got: {caplog.messages}"


# ---------------------------------------------------------------------------
# Test 3 — mocked client: Others rows reclassified, Salary row untouched
# ---------------------------------------------------------------------------

def test_mocked_client_reclassifies_others_rows():
    """
    Monkeypatches _build_client_and_model() and beta.chat.completions.parse to return
    a canned ChunkResult.  Verifies that:
    - Others rows get updated Category / Confidence / Match_Reason.
    - Salary row is untouched.
    - Only allowed-taxonomy categories are written.
    """
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415
    from ca_analyzer.presentation.report_builder import INCOME_CATEGORIES, EXPENSE_CATEGORIES  # noqa: PLC0415

    allowed = frozenset(INCOME_CATEGORIES + EXPENSE_CATEGORIES + ["Inter-Bank Transfer"])

    df = _make_df()

    # Build canned ChunkResult using the same Pydantic models the classifier builds
    _TxnClass, ChunkResult = llm_classifier._build_pydantic_models()
    assert ChunkResult is not None, "pydantic must be available for this test"

    canned_result = ChunkResult(
        classifications=[
            _TxnClass(id=0, category="Food", sub_category="Restaurant Bill", confidence="High"),
            _TxnClass(id=1, category="Shopping", sub_category="Online Purchase", confidence="Medium"),
        ]
    )

    # Shape the mock to match: completion.choices[0].message.parsed / .refusal
    mock_message = MagicMock()
    mock_message.parsed = canned_result
    mock_message.refusal = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    # Use a real function for parse so we can capture kwargs (including temperature).
    parse_calls = []

    class _FakeBetaCompletions:
        def parse(self, **kwargs):
            parse_calls.append(kwargs)
            return mock_completion

    class _FakeBeta:
        chat = type("_FakeChat", (), {"completions": _FakeBetaCompletions()})()

    mock_client = MagicMock()
    mock_client.beta = _FakeBeta()

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "moonshotai/kimi-k2.6",
            "api_key_env": "NVIDIA_API_KEY",
            "temperature": 0,
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(
            llm_classifier, "_build_client_and_model",
            return_value=(mock_client, "moonshotai/kimi-k2.6", 0),
        ):
            result = llm_classifier.classify_with_llm(df)

    # Verify temperature=0 was forwarded to the parse call
    assert parse_calls, "parse() was never called"
    assert parse_calls[0].get("temperature") == 0, (
        f"Expected temperature=0 in parse call, got: {parse_calls[0]}"
    )

    # Row 0 (was "Others"): should be reclassified to Food
    assert result.at[0, "Category"] == "Food"
    assert result.at[0, "Sub_Category"] == "Restaurant Bill"
    assert result.at[0, "Confidence"] == "High"
    assert result.at[0, "Match_Reason"].startswith("llm:")

    # Row 1 (was "Others"): should be reclassified to Shopping
    assert result.at[1, "Category"] == "Shopping"
    assert result.at[1, "Sub_Category"] == "Online Purchase"
    assert result.at[1, "Confidence"] == "Medium"
    assert result.at[1, "Match_Reason"].startswith("llm:")

    # Row 2 (Salary / High): must be untouched
    assert result.at[2, "Category"] == "Salary"
    assert result.at[2, "Confidence"] == "High"
    assert result.at[2, "Match_Reason"] == "keyword: 'salary'"

    # Taxonomy-guard: all written categories must be in the allowed set
    reclassified_cats = result.loc[[0, 1], "Category"].tolist()
    for cat in reclassified_cats:
        assert cat in allowed, f"Out-of-taxonomy category written: {cat}"


# ---------------------------------------------------------------------------
# Test 4 — taxonomy guard: out-of-taxonomy LLM response is silently dropped
# ---------------------------------------------------------------------------

def test_out_of_taxonomy_category_not_written():
    """If LLM returns an unknown category, that row must remain unchanged."""
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df().iloc[:1].copy().reset_index(drop=True)  # single Others row

    _TxnClass, ChunkResult = llm_classifier._build_pydantic_models()
    assert ChunkResult is not None

    canned_result = ChunkResult(
        classifications=[
            _TxnClass(id=0, category="INVENTED_CATEGORY", sub_category="Bogus", confidence="High"),
        ]
    )

    mock_message = MagicMock()
    mock_message.parsed = canned_result
    mock_message.refusal = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "moonshotai/kimi-k2.6",
            "api_key_env": "NVIDIA_API_KEY",
            "temperature": 0,
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(
            llm_classifier, "_build_client_and_model",
            return_value=(mock_client, "moonshotai/kimi-k2.6", 0),
        ):
            result = llm_classifier.classify_with_llm(df)

    # Category must remain "Others" since the LLM returned an invalid category
    assert result.at[0, "Category"] == "Others"
    assert result.at[0, "Match_Reason"] == "no rule matched"


# ---------------------------------------------------------------------------
# Test 5 — refusal: message has truthy .refusal → rows unchanged
# ---------------------------------------------------------------------------

def test_refusal_skips_chunk():
    """When the model returns a refusal, that chunk's rows must remain unchanged."""
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df().iloc[:1].copy().reset_index(drop=True)  # single Others row

    mock_message = MagicMock()
    mock_message.parsed = None
    mock_message.refusal = "I cannot classify this content."

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "moonshotai/kimi-k2.6",
            "api_key_env": "NVIDIA_API_KEY",
            "temperature": 0,
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(
            llm_classifier, "_build_client_and_model",
            return_value=(mock_client, "moonshotai/kimi-k2.6", 0),
        ):
            result = llm_classifier.classify_with_llm(df)

    # Row must remain unchanged because model refused
    assert result.at[0, "Category"] == "Others"
    assert result.at[0, "Match_Reason"] == "no rule matched"
