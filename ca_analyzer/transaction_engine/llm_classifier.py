"""
LLM fallback classifier for transactions left as Others/Miscellaneous/Low-confidence
by the rule engine. Uses the Anthropic Messages API via either:
  - Amazon Bedrock  (provider="bedrock", default)
  - Anthropic first-party API  (provider="anthropic")

The actual client.messages.parse() call shape is IDENTICAL for both providers —
same structured-output / output_format= usage and the same system prompt-cache block.
Only the client object and the resolved model id differ.

NOTE: Bedrock does NOT support the Files API or the Batches API; neither is used here.

CONFIG GATE: llm.enabled must be true in thresholds.yaml; defaults to false.
When disabled (or SDK/credentials absent) the function is a no-op and returns df unchanged.
"""
import os
import logging
from typing import Optional, Tuple

import pandas as pd

from ca_analyzer.core.config import config
from ca_analyzer.core.logger import get_logger

# Canonical taxonomy imported from report_builder (single source of truth so that
# categories here match the SUMIFS strings exactly).
from ca_analyzer.presentation.report_builder import (
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
)

logger = get_logger("llm_classifier")

# ---------------------------------------------------------------------------
# Allowed taxonomy (union of income + expense + terminal transfer category)
# ---------------------------------------------------------------------------
ALLOWED_CATEGORIES: frozenset = frozenset(
    INCOME_CATEGORIES + EXPENSE_CATEGORIES + ["Inter-Bank Transfer"]
)

# ---------------------------------------------------------------------------
# System prompt (cached across chunks — same text every call)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial analysis assistant helping a Chartered Accountant (CA) \
classify Indian bank statement transactions for ITR filing purposes.

Each input line has the format:
  id | DEBIT or CREDIT | amount | narration

Classify each transaction into exactly one category from the allowed list below, \
choose a short sub_category (2-5 words), and assign a confidence level.

ALLOWED CATEGORIES:
Income (credit) categories: """ + ", ".join(INCOME_CATEGORIES) + """
Expense (debit) categories: """ + ", ".join(EXPENSE_CATEGORIES) + """
Terminal: Inter-Bank Transfer

RULES:
- Pick the single best category from the allowed list above. Do NOT invent new categories.
- sub_category: a short 2-5 word descriptor (e.g. "Grocery Store", "EMI Payment").
- confidence: "High" (clear match), "Medium" (likely but not certain), "Low" (genuinely unclear).
- If genuinely unclear for a CREDIT transaction → category "Miscellaneous", sub_category "Miscellaneous Inflow", confidence "Low".
- If genuinely unclear for a DEBIT transaction → category "Others", sub_category "Other Expense", confidence "Low".
- Do NOT guess wildly; prefer Low confidence over a wrong category.
- Return one classification per id, in a JSON array under key "classifications".
- Each element: {"id": <int>, "category": "<str>", "sub_category": "<str>", "confidence": "High"|"Medium"|"Low"}
"""


# ---------------------------------------------------------------------------
# Client construction helper — returns (client, model_id) or (None, None)
# Tests can monkeypatch this function directly to avoid real SDK/cred calls.
# ---------------------------------------------------------------------------

def _build_client_and_model(cfg: dict) -> Tuple[Optional[object], Optional[str]]:
    """
    Build the appropriate Anthropic client and resolve the model id from config/env.

    Returns (client, model_id) on success, or (None, None) when the provider is
    unavailable (missing SDK import, missing credentials, etc.).

    Supports two providers:
      "bedrock"    — AnthropicBedrock client (requires anthropic[bedrock] extra + AWS creds)
      "anthropic"  — Anthropic first-party client (requires ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN)
    """
    provider: str = cfg.get("provider", "bedrock")
    model_override: str = cfg.get("model", "") or ""

    # ------------------------------------------------------------------
    # Bedrock path
    # ------------------------------------------------------------------
    if provider == "bedrock":
        # SDK import guard (requires anthropic[bedrock] extra)
        try:
            from anthropic import AnthropicBedrock  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "LLM classifier: 'AnthropicBedrock' not importable. "
                "Install the Bedrock extra with: pip install 'anthropic[bedrock]'. "
                "Skipping LLM classification."
            )
            return None, None

        # Credential guard: require at least one AWS identity signal + a region
        has_creds = bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
        )
        region_env_key: str = cfg.get("bedrock_region_env", "AWS_REGION")
        region: Optional[str] = os.environ.get(region_env_key) or os.environ.get("AWS_REGION")

        if not has_creds or not region:
            missing = []
            if not has_creds:
                missing.append(
                    "AWS credentials (AWS_ACCESS_KEY_ID, AWS_PROFILE, or AWS_BEARER_TOKEN_BEDROCK)"
                )
            if not region:
                missing.append(f"AWS region ({region_env_key} or AWS_REGION)")
            logger.warning(
                "LLM classifier: Missing Bedrock prerequisites — %s. "
                "Skipping LLM classification.",
                "; ".join(missing),
            )
            return None, None

        # Resolve model id: config override → env var → built-in default
        bedrock_model_env: str = cfg.get("bedrock_model_env", "BEDROCK_HAIKU_INFERENCE_PROFILE_ID")
        bedrock_model_default: str = cfg.get(
            "bedrock_model_default",
            "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        )
        model_id: str = (
            model_override
            or os.environ.get(bedrock_model_env, "")
            or bedrock_model_default
        )

        try:
            # aws_region is passed explicitly; the SDK resolves all other AWS creds
            # from the standard credential chain (env vars, ~/.aws/credentials, IAM role, etc.)
            client = AnthropicBedrock(aws_region=region)
            return client, model_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM classifier: Failed to construct AnthropicBedrock client: %s", exc)
            return None, None

    # ------------------------------------------------------------------
    # Anthropic first-party path
    # ------------------------------------------------------------------
    if provider == "anthropic":
        try:
            import anthropic  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "LLM classifier: 'anthropic' package is not installed. "
                "Install it with: pip install anthropic. Skipping LLM classification."
            )
            return None, None

        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        if not api_key:
            logger.warning(
                "LLM classifier: No API key found in ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN. "
                "Skipping LLM classification."
            )
            return None, None

        anthropic_model_default: str = cfg.get("anthropic_model_default", "claude-haiku-4-5")
        model_id = model_override or anthropic_model_default

        try:
            client = anthropic.Anthropic()
            return client, model_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM classifier: Failed to construct Anthropic client: %s", exc)
            return None, None

    # Unknown provider
    logger.warning(
        "LLM classifier: Unknown provider '%s'. Expected 'bedrock' or 'anthropic'. "
        "Skipping LLM classification.",
        provider,
    )
    return None, None


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------

def _build_pydantic_models():
    """Import Pydantic and define response models; return (TxnClass, ChunkResult) or None."""
    try:
        from pydantic import BaseModel  # noqa: PLC0415

        class TxnClass(BaseModel):
            id: int
            category: str
            sub_category: str
            confidence: str  # "High" | "Medium" | "Low"

        class ChunkResult(BaseModel):
            classifications: list[TxnClass]

        return TxnClass, ChunkResult
    except ImportError:
        logger.warning("LLM classifier: 'pydantic' package unavailable. Skipping.")
        return None, None


# ---------------------------------------------------------------------------
# Core classification function
# ---------------------------------------------------------------------------

def classify_with_llm(df: pd.DataFrame) -> pd.DataFrame:
    """
    LLM fallback classifier.

    Refines rows where Category in {"Others","Miscellaneous"} OR Confidence == "Low"
    (excluding "Inter-Bank Transfer" rows, which are terminal).

    Returns a copy of df with updated Category, Sub_Category, Confidence, Match_Reason
    for reclassified rows. Returns df unchanged when the feature is disabled or
    unavailable.

    Config keys read from thresholds.yaml:
      llm.enabled               (bool, default false)
      llm.provider              (str,  "bedrock" | "anthropic", default "bedrock")
      llm.model                 (str,  if blank, resolved from env per provider)
      llm.bedrock_model_env     (str,  env var name for Bedrock inference-profile ID)
      llm.bedrock_model_default (str,  fallback Bedrock inference-profile ID)
      llm.bedrock_region_env    (str,  env var name for AWS region)
      llm.anthropic_model_default (str, fallback first-party model name)
      llm.chunk_size            (int,  default 25)
      llm.max_rows              (int,  default 2000)
    """
    # ------------------------------------------------------------------
    # Step 1: CONFIG GATE
    # ------------------------------------------------------------------
    llm_cfg = config.thresholds.get("llm", {})
    enabled: bool = bool(llm_cfg.get("enabled", False))

    if not enabled:
        logger.debug("LLM classifier is disabled (llm.enabled=false). Returning df unchanged.")
        return df

    chunk_size: int = int(llm_cfg.get("chunk_size", 25))
    max_rows: int = int(llm_cfg.get("max_rows", 2000))

    # SDK / credentials availability check — build client and resolve model id
    client, model = _build_client_and_model(llm_cfg)
    if client is None:
        return df

    # Pydantic models
    _TxnClass, ChunkResult = _build_pydantic_models()
    if ChunkResult is None:
        return df

    # ------------------------------------------------------------------
    # Step 2: ROW SELECTION
    # ------------------------------------------------------------------
    df_out = df.copy()

    target_mask = (
        (df_out["Category"].isin({"Others", "Miscellaneous"}))
        | (df_out["Confidence"] == "Low")
    ) & (df_out["Category"] != "Inter-Bank Transfer")

    selected_idx = df_out.index[target_mask].tolist()

    if not selected_idx:
        logger.info("LLM classifier: No eligible rows to reclassify.")
        return df_out

    if len(selected_idx) > max_rows:
        logger.warning(
            "LLM classifier: %d eligible rows exceed max_rows=%d. "
            "Capping to first %d rows; remaining rows are left unchanged.",
            len(selected_idx), max_rows, max_rows,
        )
        selected_idx = selected_idx[:max_rows]

    logger.info("LLM classifier: Reclassifying %d rows in chunks of %d.", len(selected_idx), chunk_size)

    # ------------------------------------------------------------------
    # Step 3: CHUNK + CALL
    # The client.messages.parse() call shape is IDENTICAL for both Bedrock and
    # the first-party Anthropic client — same output_format= structured-output
    # usage and the same system prompt-cache block.  Only the client object
    # and the resolved model id differ (set above by _build_client_and_model).
    # ------------------------------------------------------------------
    for chunk_start in range(0, len(selected_idx), chunk_size):
        chunk_idx = selected_idx[chunk_start: chunk_start + chunk_size]

        # Build user text: 0-based local id | direction | amount | narration (truncated)
        lines = []
        local_id_to_real_idx = {}
        for local_id, real_idx in enumerate(chunk_idx):
            row = df_out.loc[real_idx]
            debit = float(row.get("Debit", 0.0) or 0.0)
            credit = float(row.get("Credit", 0.0) or 0.0)
            direction = "DEBIT" if debit > 0 else "CREDIT"
            amount = debit if debit > 0 else credit
            narration = str(row.get("Narration", ""))[:200]
            lines.append(f"{local_id} | {direction} | {amount:.2f} | {narration}")
            local_id_to_real_idx[local_id] = real_idx

        user_text = "\n".join(lines)

        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_text}],
                output_format=ChunkResult,
            )
            result = resp.parsed_output  # a ChunkResult instance

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "LLM classifier: Chunk %d-%d failed (%s). Leaving those rows unchanged.",
                chunk_start, chunk_start + len(chunk_idx) - 1, exc,
            )
            continue

        # Apply results back — only for allowed-taxonomy categories
        for txn in result.classifications:
            local_id = txn.id
            real_idx = local_id_to_real_idx.get(local_id)
            if real_idx is None:
                continue

            new_cat = txn.category
            if new_cat not in ALLOWED_CATEGORIES:
                logger.debug(
                    "LLM classifier: Discarding out-of-taxonomy category '%s' for idx %s.",
                    new_cat, real_idx,
                )
                continue

            df_out.at[real_idx, "Category"] = new_cat
            df_out.at[real_idx, "Sub_Category"] = txn.sub_category
            df_out.at[real_idx, "Confidence"] = txn.confidence
            df_out.at[real_idx, "Match_Reason"] = f"llm: {txn.sub_category}"

    logger.info("LLM classifier: Reclassification complete.")
    return df_out
