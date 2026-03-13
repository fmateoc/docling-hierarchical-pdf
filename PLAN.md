# Edval Extraction Pipeline Implementation Plan

## Phase 1: Completed Architecture Planning

**1. Create the Edval Postprocessor**
- I will create a new file `hierarchical/edval_postprocessor.py` containing an `EdvalPostprocessor` class.
- This class will accept a `ConversionResult` and use `pymupdf` to extract the TOC via `doc.get_toc()`.
- It will traverse the `DoclingDocument` items sequentially and assign each item (text, table, etc.) to the currently active TOC node. Below the TOC node level, the hierarchy will not be strictly flat, but rather it will retain the shallow structure provided by regular non-hierarchical Docling.

**2. Implement Phase Segregation**
- In `hierarchical/edval_postprocessor.py`, I will add a state machine within the main processing loop.
- It will classify items into three phases:
  - `General Overview`: Everything before the first TOC entry.
  - `Table of Contents`: The TOC itself.
  - `Body`: Everything after the TOC.
- Extracted rules will only be nested under the `Body` phase, and heading levels will be normalized to start at 1.

**3. Implement Rules Table Schema & Table Parsing**
- In `hierarchical/edval_postprocessor.py`, I will inspect each `TableItem`.
- Using `TableItem.export_to_dataframe()` (or direct grid traversal), I will check the table's column headers. If they match `['Attribute', 'Req/Opt', 'Size/Format', 'Rules']` (or variants like `Field Name`), it will be classified as a "Rules Table".

**4. Implement Table Pagination and Row Merging**
- Within the loop in `hierarchical/edval_postprocessor.py`, I will maintain a reference to the last processed item.
- **Table Merge:** If the current item is a Rules Table and the previous item was also a Rules Table within the same TOC node, I will merge the new table's rows into the previous table instead of creating a new one.
- **Row Merge:** During the row extraction of the continuation table, if I find a row where the first three cells are empty but the `Rules` cell is populated, I will append the text to the `Rules` cell of the preceding row.

**5. Implement Contextual Text Mapping**
- In `hierarchical/edval_postprocessor.py`, I will maintain a state flag `has_rules_table_passed` for each TOC node.
- Free-form `TextItem`s encountered before a Rules Table will be appended to the node's `"overview"` string.
- `TextItem`s encountered after a Rules Table will be appended to the node's `"notes"` string.

**6. Implement License Extraction (Refined)**
- In `hierarchical/edval_postprocessor.py`, I will implement a two-pronged license extraction strategy:
  - **Revision History Pointers:** During the `General Overview` phase, scan the text and tables (specifically the revision history) for mentions of licenses along with their associated page numbers. Store a mapping of page numbers to extracted feature names.
  - **Contextual Mapping & Regex Fallback:** While traversing the `Body` items, if an item is located on a page matching a pointer from the revision history, use that feature name to flag the active TOC node. Additionally, scan the extracted body text (overview, notes, and rules) with a regex (`r"(?i)separately licensed\s*(?:for|by)?\s*([^.,\n]+)"`) to catch unindexed mentions.
  - If a license is found via either method, set `"separately_licensed": true` and populate `"licensed_functionality"` on the active JSON node.

**7. Harden Postprocessor for Infinite Loops**
- The original `postprocessor.py` has a `while last_len_processed < len(processed):` loop that can get stuck in an infinite loop if `processed.append` is skipped or if the graph has an issue.
- I will inspect `hierarchical/postprocessor.py` to identify why it stops after 86 out of 184 pages. The loop structure or missing edge case processing might cause an early exit without an exception (since `last_len_processed < len(processed)` becomes false).
- I will modify the loop to ensure robust processing, possibly throwing an error instead of silently halting if it gets stuck, or fixing the condition causing the halt.

**8. Write and Execute Concrete Verification Tests**
- I will create a new test file `tests/test_edval_extraction.py`.
- I will programmatically generate a dummy `ConversionResult` (using `docling_core` models) that contains:
  - Pre-TOC text (including a dummy revision history pointing to a licensed feature on page X).
  - TOC entries.
  - A TOC header.
  - "Overview" text.
  - Two adjacent `TableItem`s (simulating a split rules table with a dangling continuation row).
  - "Notes" text containing "separately licensed Feature X" and another text node falling on the referenced page X.
- I will run the `EdvalPostprocessor` on this dummy result and assert:
  - The three root sections exist.
  - Rules are correctly nested under `Body` with level 1.
  - Tables are merged into a single structure.
  - The dangling row text is appended to the previous row.
  - `overview` and `notes` are correctly segregated.
  - `"separately_licensed"` is `True` and `"Feature X"` is extracted via both the page pointer and the regex.
- I will run all tests (`pytest tests/`) to ensure the full test suite passes.

**9. Pre-Commit Steps**
- Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
