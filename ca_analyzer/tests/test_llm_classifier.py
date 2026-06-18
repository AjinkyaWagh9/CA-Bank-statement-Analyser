"""
Tests for ca_analyzer.transaction_engine.llm_classifier.

All tests mock the Anthropic SDK — no real API calls are made.
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
        {"llm": {"enabled": False, "provider": "bedrock", "model": "", "chunk_size": 25, "max_rows": 2000}},
    ):
        result = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# Test 2 — no SDK / no key: df returned unchanged, warning logged
# ---------------------------------------------------------------------------

def test_no_sdk_or_no_key_returns_df_unchanged_with_warning(caplog):
    """
    When the SDK is absent OR the API key is missing, classify_with_llm must:
    - return df unchanged
    - log a warning

    Uses provider="anthropic" so we can test the ANTHROPIC_API_KEY path.
    The Bedrock missing-creds path is tested separately (test_bedrock_missing_creds).
    """
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df()

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "anthropic",
            "model": "",
            "anthropic_model_default": "claude-haiku-4-5",
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    # --- Path A: _build_client_and_model returns (None, None) directly ---
    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(llm_classifier, "_build_client_and_model", return_value=(None, None)):
            with caplog.at_level(logging.WARNING, logger="llm_classifier"):
                result = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result, df)

    # --- Path B: SDK importable but no API key in environment ---
    import sys  # noqa: PLC0415
    import types  # noqa: PLC0415

    # Create a stub 'anthropic' module so the import succeeds
    stub_anthropic = types.ModuleType("anthropic")

    class _FakeAnthropicClient:
        pass

    stub_anthropic.Anthropic = _FakeAnthropicClient

    env_without_key = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }

    caplog.clear()
    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.dict(os.environ, env_without_key, clear=True):
            with patch.dict(sys.modules, {"anthropic": stub_anthropic}):
                with caplog.at_level(logging.WARNING, logger="llm_classifier"):
                    result2 = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result2, df)
    warning_messages = " ".join(caplog.messages)
    assert any(
        phrase in warning_messages
        for phrase in ("ANTHROPIC_API_KEY", "API key", "api key", "key", "No API key", "no api key")
    ), f"Expected key-related warning, got: {caplog.messages}"


# ---------------------------------------------------------------------------
# Test 3 — mocked client: Others rows reclassified, Salary row untouched
# ---------------------------------------------------------------------------

def test_mocked_client_reclassifies_others_rows():
    """
    Monkeypatches _build_client_and_model() and messages.parse to return a canned
    ChunkResult.  Verifies that:
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

    mock_resp = MagicMock()
    mock_resp.parsed_output = canned_result

    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_resp

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "bedrock",
            "model": "",
            "bedrock_model_env": "BEDROCK_HAIKU_INFERENCE_PROFILE_ID",
            "bedrock_model_default": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock_region_env": "AWS_REGION",
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(
            llm_classifier, "_build_client_and_model",
            return_value=(mock_client, "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
        ):
            result = llm_classifier.classify_with_llm(df)

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

    mock_resp = MagicMock()
    mock_resp.parsed_output = canned_result

    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_resp

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "bedrock",
            "model": "",
            "bedrock_model_env": "BEDROCK_HAIKU_INFERENCE_PROFILE_ID",
            "bedrock_model_default": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock_region_env": "AWS_REGION",
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.object(
            llm_classifier, "_build_client_and_model",
            return_value=(mock_client, "global.anthropic.claude-haiku-4-5-20251001-v1:0"),
        ):
            result = llm_classifier.classify_with_llm(df)

    # Category must remain "Others" since the LLM returned an invalid category
    assert result.at[0, "Category"] == "Others"
    assert result.at[0, "Match_Reason"] == "no rule matched"


# ---------------------------------------------------------------------------
# Test 5 — Bedrock path: env creds + region → reclassification works, model
#           id resolves to the inference-profile default
# ---------------------------------------------------------------------------

def test_bedrock_path_reclassifies_with_env_creds():
    """
    Simulates a valid Bedrock environment (AWS_ACCESS_KEY_ID + AWS_REGION set)
    and monkeypatches _build_client_and_model to return a canned mock client.
    Asserts that:
    - Others rows are reclassified correctly.
    - The resolved model id equals the bedrock_model_default (inference-profile ID).
    """
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df()

    _TxnClass, ChunkResult = llm_classifier._build_pydantic_models()
    assert ChunkResult is not None

    canned_result = ChunkResult(
        classifications=[
            _TxnClass(id=0, category="Food", sub_category="Restaurant Bill", confidence="High"),
            _TxnClass(id=1, category="Shopping", sub_category="Online Purchase", confidence="Medium"),
        ]
    )

    mock_resp = MagicMock()
    mock_resp.parsed_output = canned_result

    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_resp

    expected_model = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "bedrock",
            "model": "",
            "bedrock_model_env": "BEDROCK_HAIKU_INFERENCE_PROFILE_ID",
            "bedrock_model_default": expected_model,
            "bedrock_region_env": "AWS_REGION",
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    bedrock_env = {
        "AWS_ACCESS_KEY_ID": "AKIAFAKEKEY",
        "AWS_REGION": "us-east-1",
    }

    # _build_client_and_model is monkeypatched so no real SDK/cred calls happen.
    # We capture the returned model_id to assert resolution order is correct.
    captured = {}

    def fake_build(cfg):
        captured["model"] = (
            cfg.get("model") or
            os.environ.get(cfg.get("bedrock_model_env", "")) or
            cfg.get("bedrock_model_default")
        )
        return mock_client, captured["model"]

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.dict(os.environ, bedrock_env, clear=False):
            with patch.object(llm_classifier, "_build_client_and_model", side_effect=fake_build):
                result = llm_classifier.classify_with_llm(df)

    # Model id resolved to the inference-profile default (no env override, no model override)
    assert captured["model"] == expected_model, (
        f"Expected model={expected_model!r}, got {captured['model']!r}"
    )

    # Reclassification actually happened
    assert result.at[0, "Category"] == "Food"
    assert result.at[0, "Confidence"] == "High"
    assert result.at[1, "Category"] == "Shopping"
    assert result.at[1, "Confidence"] == "Medium"
    assert result.at[2, "Category"] == "Salary"  # untouched


# ---------------------------------------------------------------------------
# Test 6 — Bedrock missing creds: df unchanged + warning logged
# ---------------------------------------------------------------------------

def test_bedrock_missing_creds_returns_df_unchanged_with_warning(caplog):
    """
    When provider=bedrock and no AWS_* credentials are in env,
    _build_client_and_model must log a warning and return (None, None),
    causing classify_with_llm to return df unchanged.
    """
    from ca_analyzer.transaction_engine import llm_classifier  # noqa: PLC0415

    df = _make_df()

    patched_thresholds = {
        "llm": {
            "enabled": True,
            "provider": "bedrock",
            "model": "",
            "bedrock_model_env": "BEDROCK_HAIKU_INFERENCE_PROFILE_ID",
            "bedrock_model_default": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
            "bedrock_region_env": "AWS_REGION",
            "chunk_size": 25,
            "max_rows": 2000,
        }
    }

    # Strip all AWS-related env vars and mock the SDK import to succeed
    clean_env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("AWS_")
    }

    import sys   # noqa: PLC0415
    import types  # noqa: PLC0415

    stub_anthropic = types.ModuleType("anthropic")

    class _FakeBedrockClient:
        pass

    stub_anthropic.AnthropicBedrock = _FakeBedrockClient

    with patch.object(llm_classifier.config, "thresholds", patched_thresholds):
        with patch.dict(os.environ, clean_env, clear=True):
            with patch.dict(sys.modules, {"anthropic": stub_anthropic}):
                with caplog.at_level(logging.WARNING, logger="llm_classifier"):
                    result = llm_classifier.classify_with_llm(df)

    pd.testing.assert_frame_equal(result, df)

    warning_text = " ".join(caplog.messages)
    assert any(
        phrase in warning_text
        for phrase in (
            "AWS credentials", "AWS_ACCESS_KEY_ID", "AWS_PROFILE",
            "AWS_BEARER_TOKEN_BEDROCK", "region", "Missing Bedrock",
        )
    ), f"Expected AWS-creds-related warning, got: {caplog.messages}"
