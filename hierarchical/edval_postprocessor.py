import re
from io import BytesIO
from pathlib import Path, PurePath
from typing import Any, Optional

import fitz
import pandas as pd
from docling.datamodel.base_models import DocumentStream
from docling.datamodel.document import ConversionResult
from docling_core.types.doc.document import DocItem, DocItemLabel, SectionHeaderItem, TableItem

from hierarchical.hierarchy_builder_metadata import HierarchyBuilderMetadata


class EdvalPostprocessor:
    def __init__(
        self,
        result: ConversionResult,
        source: Optional[str | PurePath | DocumentStream | BytesIO] = None,
        raise_on_error: bool = False,
    ):
        self.result = result
        self.source = source
        self.raise_on_error = raise_on_error

        # State machine
        self.current_phase = "General Overview"
        self.toc_nodes = []
        self.active_toc_index = -1
        self.last_table = None
        self._seen_toc_nodes_in_toc = set()
        self.revision_licenses = {}

    def _get_fitz_doc(self) -> fitz.Document:
        source = self.source
        if source is None:
            source = self.result.input.file if hasattr(self.result.input, "file") else None

        if isinstance(source, str):
            source = Path(source)

        if isinstance(source, PurePath):
            if not Path(source).exists():
                if self.raise_on_error:
                    raise Exception(f"PDF file {source} does not exist!")
                return None
            return fitz.open(str(source))
        elif isinstance(source, DocumentStream):
            if source.stream.closed:
                if self.raise_on_error:
                    raise Exception("Stream is closed")
                return None
            source.stream.seek(0)
            return fitz.open(stream=source.stream.read(), filetype="pdf")
        elif isinstance(source, BytesIO):
            if source.closed:
                if self.raise_on_error:
                    raise Exception("Stream is closed")
                return None
            source.seek(0)
            return fitz.open(stream=source.read(), filetype="pdf")
        return None

    def process(self) -> dict[str, Any]:
        doc_fitz = self._get_fitz_doc()
        raw_toc = []
        if doc_fitz:
            raw_toc = doc_fitz.get_toc(simple=False)

        if not raw_toc:
            # Fallback
            hbm = HierarchyBuilderMetadata(self.result, self.source, self.raise_on_error)
            raw_toc = hbm.toc

        base_level = min([item[0] for item in raw_toc]) if raw_toc else 1

        for level, title, page, add_info in raw_toc:
            # Normalize heading level to start at 1
            normalized_level = level - base_level + 1
            self.toc_nodes.append({
                "level": normalized_level,
                "title": title.strip(),
                "page": page,
                "items": [],
                "overview": "",
                "notes": "",
                "has_rules_table_passed": False,
                "licensed_functionality": [],
                "rules_table": [],
            })

        self.output = {"General Overview": [], "Table of Contents": [], "Body": self.toc_nodes}

        doc = self.result.document

        for item, _ in doc.iterate_items():
            self._process_item(item)

        self._extract_licenses_from_revision_history()

        return self.output

    def _extract_licenses_from_revision_history(self):
        # We also want to map the findings back to the Body nodes
        for item in self.output["General Overview"]:
            if hasattr(item, "text") and item.text:
                text = item.text
                match = re.search(r"(?i)separately licensed\s*(?:for|by)?\s*([^.,\n\s]+).*?page\s*(\d+)", text)
                if match:
                    feature = match.group(1).strip()
                    page = int(match.group(2))
                    self.revision_licenses[page] = feature

        # Apply page-based licenses to TOC nodes
        for node in self.toc_nodes:
            if node["page"] in self.revision_licenses:
                node["licensed_functionality"].append({
                    "name": self.revision_licenses[node["page"]],
                    "description": "Found via Revision History pointer."
                })

    def _check_license_in_text(self, text: str, node: dict):
        match1 = re.search(r"(?i)separately licensed.*?available,\s*([^.]+)\s*\.\s*(.*)", text, re.DOTALL)
        match2 = re.search(r"(?i)separately licensed\s+(?:for|by)\s+([A-Za-z0-9_\s]+?)(?:[\.,\n]|$)\s*(.*)", text, re.DOTALL)

        if match1:
            node["licensed_functionality"].append({
                "name": match1.group(1).strip(),
                "description": match1.group(2).strip()
            })
        elif match2:
            node["licensed_functionality"].append({
                "name": match2.group(1).strip(),
                "description": match2.group(2).strip()
            })
        elif "separately licensed" in text.lower():
            node["licensed_functionality"].append({
                "name": "Unknown Feature",
                "description": text.strip()
            })
    def _process_item(self, item: DocItem):
        text = ""
        if hasattr(item, "text") and item.text:
            text = item.text
        elif hasattr(item, "orig") and item.orig:
            text = item.orig

        text = text.strip() if text else ""

        matched_toc_index = -1
        for i in range(len(self.toc_nodes)):
            if self._matches_toc_node(text, i):
                matched_toc_index = i
                break

        if self.current_phase == "General Overview":
            if text.lower() == "table of contents":
                self.current_phase = "Table of Contents"
            elif matched_toc_index == 0:
                self.current_phase = "Body"
                self.active_toc_index = 0

        elif self.current_phase == "Table of Contents":
            if matched_toc_index != -1:
                if matched_toc_index in self._seen_toc_nodes_in_toc:
                    self.current_phase = "Body"
                    self.active_toc_index = matched_toc_index
                else:
                    self._seen_toc_nodes_in_toc.add(matched_toc_index)

        elif self.current_phase == "Body":
            if matched_toc_index != -1 and matched_toc_index > self.active_toc_index:
                self.active_toc_index = matched_toc_index
                self.last_table = None

        if self.current_phase == "General Overview":
            self.output["General Overview"].append(item)
        elif self.current_phase == "Table of Contents":
            self.output["Table of Contents"].append(item)
        elif self.current_phase == "Body":
            self._process_body_item(item)

    def _matches_toc_node(self, text: str, index: int) -> bool:
        if index >= len(self.toc_nodes) or index < 0:
            return False
        toc_title = re.sub(r"[^A-Za-z0-9]", "", self.toc_nodes[index]["title"])
        item_title = re.sub(r"[^A-Za-z0-9]", "", text)
        return toc_title == item_title and len(toc_title) > 0

    def _process_body_item(self, item: DocItem):
        if self.active_toc_index == -1:
            return

        current_node = self.toc_nodes[self.active_toc_index]
        current_node["items"].append(item)

        # Heading normalisation
        if isinstance(item, SectionHeaderItem):
            item.level = current_node["level"] + 1  # Nest rules under Body phase

        text = ""
        if hasattr(item, "text") and item.text:
            text = item.text
        elif hasattr(item, "orig") and item.orig:
            text = item.orig

        if text:
            self._check_license_in_text(text, current_node)

        if isinstance(item, TableItem):
            df = item.export_to_dataframe()
            if self._is_rules_table(df):
                current_node["has_rules_table_passed"] = True
                self._merge_rules_table(df, current_node)
        elif hasattr(item, "label") and item.label == DocItemLabel.TEXT:
            if not current_node["has_rules_table_passed"]:
                current_node["overview"] += text + "\n"
            else:
                current_node["notes"] += text + "\n"

    def _is_rules_table(self, table: pd.DataFrame) -> bool:
        if table.empty:
            return False

        columns = [str(c).lower().strip() for c in table.columns]
        attr_match = any("attribute" in c or "field name" in c for c in columns)
        req_match = any("req/opt" in c or "required" in c or "req" in c for c in columns)
        size_match = any("size" in c or "format" in c for c in columns)
        rules_match = any("rules" in c or "rule" in c for c in columns)

        return attr_match and req_match and size_match and rules_match

    def _merge_rules_table(self, df_new: pd.DataFrame, current_node: dict):
        current_rules = current_node["rules_table"]
        if not current_rules:
            current_node["rules_table"] = df_new.to_dict("records")
            return

        new_records = df_new.to_dict("records")

        for record in new_records:
            keys = list(record.keys())
            attr_val = str(record[keys[0]]).strip()
            req_val = str(record[keys[1]]).strip()
            size_val = str(record[keys[2]]).strip()
            rules_val = str(record[keys[3]]).strip() if len(keys) > 3 else ""

            if not attr_val and not req_val and not size_val and rules_val:
                last_rule = current_rules[-1]
                last_rule_keys = list(last_rule.keys())
                if len(last_rule_keys) > 3:
                    last_rule[last_rule_keys[3]] += " " + rules_val
            else:
                current_rules.append(record)
