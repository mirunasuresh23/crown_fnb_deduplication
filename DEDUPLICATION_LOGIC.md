# Deduplication Logic: Detailed Step-by-Step Guide

This document provides a technical deep-dive into the 5-step deduplication pipeline used by the Dedup Agent.

---

## Overview
The agent follows a "Cascade" architecture. Each step attempts to match records using a specific method. Once a match is found, those records are assigned a `group_id` and are often excluded from further, more expensive processing steps.

### Pre-processing: Text Normalization
Before any matching starts, descriptions are passed through a `normalize_text` function:
- **Lowercase**: Converts everything to lowercase.
- **Punctuation Removal**: Removes all special characters (e.g., `-`, `/`, `!`, `&`).
- **Whitespace Stripping**: Collapses multiple spaces into one.
*Why?* To ensure that "Syrup-Monin-Lavender" and "syrup monin lavender" are treated as the same string.

---

## Step 1: Exact Match
**Goal**: Catch the obvious duplicates using unique identifiers.
- **Logic**: The system checks for identical values in the `item_code` and `barcode` columns.
- **Priority**: This step runs first because it is 100% accurate and requires no AI.
- **Output**: Match type `exact_item_code` or `exact_barcode`. Confidence: **1.0**.

---

## Step 2: Advanced Fuzzy Match (Hybrid Search)
**Goal**: Identify potential duplicates based on description similarity.
- **Part A: Vector Embedding**:
  - Uses Vertex AI `text-embedding-004`.
  - Converts descriptions into 768-dimension vectors.
  - Measures **Cosine Similarity** between items.
- **Part B: Keyword Overlap**:
  - Calculates the count of shared words between two descriptions.
- **Hybrid Scoring**:
  - **Final Score = (Vector Similarity × 0.7) + (Keyword Overlap × 0.3)**
  - This prevents items with similar meanings but different specific keywords (like flavors) from being ranked too high initially.
- **Threshold**: Currently set at **0.90**.
- **Output**: Match type `fuzzy_hybrid`.

---

## Step 3: Cross-Encoder Re-ranking
**Goal**: Double-check borderline fuzzy matches using high-precision AI.
- **Logic**: Any matches with a confidence below 0.95 are sent to **Gemini 2.0 Flash**.
- **The Check**: Unlike Step 2, Gemini looks at both descriptions *simultaneously* and is specifically instructed to check for differentiating attributes:
  - Flavors (e.g., Lavender vs. Cherry)
  - Sizes (e.g., 700ml vs. 1L)
  - Pack Quantities
- **Temperature**: Set to **0.0** to ensure strict adherence to rules.
- **Output**: Match type `rerank_verified` or `rerank_discarded`.

---

## Step 4: LLM-Assisted Merge (Final Decision)
**Goal**: Make the final "Merge" or "Discard" call for remaining ambiguous groups.
- **Logic**: Groups that are still tagged for review are re-evaluated by Gemini.
- **Prompting**: Includes specific instructions to **never** match different varieties of the same brand.
- **Group Integrity**: If Gemini decides a group is invalid, the `group_id` is cleared for **all** members of that group to prevent "orphan" records.
- **Output**: Match type `llm_matched` or `llm_discarded`.

---

## Step 5: Human Review & Cleanup
**Goal**: Final safety pass and preparation for the UI.
- **Human Review Flag**: Any records where confidence is still below 0.8 are flagged with `review_required = True`. These appear in the Frontend Review Queue.
- **Orphan Cleanup**: A final scan ensures no record is left with a `group_id` if it doesn't have at least one other partner record. This guarantees that your results table only contains actual clusters of duplicates.

---

## Implementation Details
- **Batching**: Embedding requests are sent in batches of 250 rows to respect Vertex AI limits.
- **Memory Efficiency**: Similarity calculations are done in chunks of 5,000 to handle large BigQuery tables (60k+ rows) on local hardware.
