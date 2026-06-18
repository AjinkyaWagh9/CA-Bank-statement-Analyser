"""
LLM fallback classifier for transactions left as Others/Miscellaneous/Low-confidence
by the rule engine. Uses the OpenAI API (GPT-4o family).

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
# System prompt (stable across chunks — OpenAI caches identical prompt prefixes)
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
# Client construction helper — returns (client, model_id) or (None, None)
# Tests can monkeypatch this function directly to avoid real SDK/cred calls.
# ---------------------------------------------------------------------------

def _build_client_and_model(cfg: dict) -> Tuple[Optional[object], Optional[str], int]:
    """
    Build the OpenAI-compatible client and resolve the model id from config.

    Returns (client, model_id, temperature) on success, or (None, None, 0) when
    the provider is unavailable (missing SDK import, missing API key, etc.).

    The client is constructed with an optional base_url so the same code works
    for both the OpenAI cloud (base_url empty/absent) and NVIDIA NIM or any
    other OpenAI-compatible endpoint (base_url set).
    """
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "LLM classifier: 'openai' package is not installed. "
            "Install it with: pip install openai. Skipping LLM classification."
        )
        return None, None, 0

    api_key_env: str = cfg.get("api_key_env", "NVIDIA_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.warning(
            "LLM classifier: No API key found in %s. "
            "Skipping LLM classification.",
            api_key_env,
        )
        return None, None, 0

    model_id: str = cfg.get("model", "moonshotai/kimi-k2.6") or "moonshotai/kimi-k2.6"
    temperature: int = int(cfg.get("temperature", 0))

    # Use base_url when provided (e.g. NVIDIA NIM); None falls back to OpenAI cloud.
    base_url = cfg.get("base_url") or None

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        return client, model_id, temperature
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM classifier: Failed to construct OpenAI client: %s", exc)
        return None, None, 0


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
      llm.enabled       (bool, default false)
      llm.provider      (str,  "openai")
      llm.base_url      (str,  optional; "" or absent → OpenAI cloud; set for NVIDIA NIM etc.)
      llm.model         (str,  default "moonshotai/kimi-k2.6")
      llm.api_key_env   (str,  env var name for API key, default "NVIDIA_API_KEY")
      llm.temperature   (int,  default 0; must be 0 for Kimi to produce sane output)
      llm.chunk_size    (int,  default 25)
      llm.max_rows      (int,  default 2000)
    """
    # ------------------------------------------------------------------
    # Step 1: CONFIG GATE
    # ------------------------------------------------------------------
    llm_cfg = config.thresholds.get("llm", {})
    enabled: bool = bool(llm_cfg.get("enabled", False))

    if not enabled:
        logger.debug("LLM classifier is disabled (llm.enabled=false). Returning df unchanged.")
        return df

    # SDK / credentials availability check — build client and resolve model id
    client, model, temperature = _build_client_and_model(llm_cfg)
    if client is None:
        return df

    chunk_size: int = int(llm_cfg.get("chunk_size", 25))
    max_rows: int = int(llm_cfg.get("max_rows", 2000))

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
    # Step 3: CHUNK + CALL (OpenAI structured-output via beta.chat.completions.parse)
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
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                response_format=ChunkResult,
                temperature=temperature,
            )
            msg = completion.choices[0].message
            if getattr(msg, "refusal", None):   # safety refusal → skip this chunk
                logger.warning(
                    "LLM classifier: Chunk %d-%d refused by model. Leaving those rows unchanged.",
                    chunk_start, chunk_start + len(chunk_idx) - 1,
                )
                continue
            result = msg.parsed                 # a ChunkResult instance (or None → skip)
            if result is None:
                logger.warning(
                    "LLM classifier: Chunk %d-%d returned None parsed result. Leaving those rows unchanged.",
                    chunk_start, chunk_start + len(chunk_idx) - 1,
                )
                continue

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
