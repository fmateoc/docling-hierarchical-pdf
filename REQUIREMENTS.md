# Edval Extraction Pipeline Requirements

## Architectural Requirements & Domain Specifics

1. **The TOC Anchor & Hierarchy Flatness:**
   * Use `pymupdf`'s `get_toc()` method (or analyze the early physical Table of Contents pages) to build a rigid hierarchical skeleton of the document.
   * **Crucial:** Every rules table is associated with a specific TOC entry. Everything that exists below a TOC entry level (other than actual TOC sub-entries or tables) must **not** be nested hierarchically any deeper than standard, non-hierarchical Docling organizes it. Tie the content directly to its parent TOC node.

2. **Phase Segregation:**
   * The parser must recognize three distinct sections: `General Overview`, `Table of Contents`, and the `Body`.
   * The actual edval rules must only be nested under the `Body` section, with their heading levels normalized to start at 1.

3. **Rules Table Schema:**
   * Distinguish between ad-hoc tables and "Rules Tables". Rules tables deserve special parsing and have a nearly fixed 4-column format:
     1. `Attribute` or `Field Name`
     2. `Req/Opt` (Required or Optional)
     3. `Size/Format`
     4. `Rules`

4. **Table Pagination and Row Merging:**
   * Rules tables frequently span page boundaries.
   * **Table Merge Rule:** If a "new" table directly follows another table in the parsed stream, it is a page expansion. They must be merged into a single table structure.
   * **Row Merge Rule:** If the continuation table contains a row where the `Attribute/Field Name`, `Req/Opt`, and `Size/Format` cells are completely empty, and only the `Rules` cell has a value, this is a continuation of the previous row's long rule text. You must append this text to the previous row's `Rules` value rather than creating a new row object.

5. **Contextual Text Mapping (Overview vs. Notes):**
   * Free-form text immediately preceding a Rules Table under a TOC node must be classified and stored as the `"overview"` attribute for that node.
   * Free-form text immediately following a Rules Table must be classified and stored as the `"notes"` attribute for that node.

6. **License Extraction:**
   * The pipeline must scan the extracted text and rules for the phrase "separately licensed". If found, it must automatically flag the JSON node (`"separately_licensed": true`) and extract the specific name of the gated functionality.
