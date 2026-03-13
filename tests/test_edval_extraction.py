from io import BytesIO

import pandas as pd
import pytest
from docling.datamodel.base_models import DocumentStream
from docling.datamodel.document import ConversionResult
from docling_core.types.doc.document import (
    DoclingDocument,
    SectionHeaderItem,
    TableItem,
    TextItem,
)
from docling_core.types.doc.labels import DocItemLabel

from hierarchical.edval_postprocessor import EdvalPostprocessor


@pytest.fixture
def mock_conversion_result(monkeypatch):
    doc = DoclingDocument(name="test")

    _counter = 0

    def make_text(text_val):
        nonlocal _counter
        _counter += 1
        return TextItem.model_construct(
            self_ref=f"#/texts/{_counter}", label=DocItemLabel.TEXT, text=text_val, orig=text_val
        )

    doc.body.children.append(make_text("Document Title"))
    doc.body.children.append(make_text("Revision History: Separately licensed for CoolFeature on page 2"))
    doc.body.children.append(make_text("Table of Contents"))
    doc.body.children.append(make_text("1. Node One"))  # TOC entry
    doc.body.children.append(make_text("2. Node Two"))  # TOC entry

    # Body headers need to be SectionHeaderItem for level normalization testing
    h1 = SectionHeaderItem.model_construct(
        self_ref=f"#/texts/{_counter + 1}",
        label=DocItemLabel.SECTION_HEADER,
        text="1. Node One",
        orig="1. Node One",
        level=10,
    )
    _counter += 1
    doc.body.children.append(h1)
    doc.body.children.append(make_text("Here is an overview of Node One."))

    table_item = TableItem.model_construct(self_ref="#/tables/1", label=DocItemLabel.TABLE)
    doc.body.children.append(table_item)
    doc.body.children.append(make_text("These are notes after the table for Node One."))

    h2 = SectionHeaderItem.model_construct(
        self_ref=f"#/texts/{_counter + 1}",
        label=DocItemLabel.SECTION_HEADER,
        text="2. Node Two",
        orig="2. Node Two",
        level=10,
    )
    _counter += 1
    doc.body.children.append(h2)
    doc.body.children.append(make_text("Overview for Node Two."))

    table_item_1 = TableItem.model_construct(self_ref="#/tables/2", label=DocItemLabel.TABLE)
    doc.body.children.append(table_item_1)

    table_item_2 = TableItem.model_construct(self_ref="#/tables/3", label=DocItemLabel.TABLE)
    doc.body.children.append(table_item_2)
    doc.body.children.append(
        make_text(
            "Notes for Node Two. Internal Circles between two Host Bank Entities - Available as a patch with Release 6.0.09.08, the following separately licensed enhancement is available, Validate Host Bank and Risk Book Selection at Circle Level. This enhancement restricts users..."
        )
    )

    res = ConversionResult.model_construct(
        input=DocumentStream.model_construct(name="test.pdf", stream=BytesIO()), document=doc
    )

    # Mock EdvalPostprocessor._get_fitz_doc
    class MockFitzDoc:
        def get_toc(self, simple=False):
            return [
                (1, "1. Node One", 2, {}),
                (2, "2. Node Two", 3, {}),  # Let's say it's level 2 to test normalization
            ]

    monkeypatch.setattr(EdvalPostprocessor, "_get_fitz_doc", lambda self: MockFitzDoc())

    def mock_iterate_items(self):
        for child in self.body.children:
            yield child, 0

    monkeypatch.setattr(DoclingDocument, "iterate_items", mock_iterate_items)

    # Mock TableItem.export_to_dataframe at the class level
    def mock_export(self, doc=None, **kwargs):
        if self.self_ref == "#/tables/1":
            return pd.DataFrame({
                "Attribute": ["Attr1"],
                "Req/Opt": ["Req"],
                "Size/Format": ["10"],
                "Rules": ["Rule 1"],
            })
        elif self.self_ref == "#/tables/2":
            return pd.DataFrame({"Field Name": ["AttrA"], "Req": ["Opt"], "Size": ["20"], "Rule": ["Rule A part 1"]})
        elif self.self_ref == "#/tables/3":
            return pd.DataFrame({"Field Name": [""], "Req": [""], "Size": [""], "Rule": ["Rule A part 2"]})
        return pd.DataFrame()

    monkeypatch.setattr(TableItem, "export_to_dataframe", mock_export)

    return res


def test_edval_postprocessor_phase_segregation(mock_conversion_result):
    ep = EdvalPostprocessor(mock_conversion_result)
    output = ep.process()

    assert len(output["General Overview"]) == 2
    assert output["General Overview"][0].text == "Document Title"
    assert output["General Overview"][1].text == "Revision History: Separately licensed for CoolFeature on page 2"

    assert len(output["Table of Contents"]) == 3
    assert output["Table of Contents"][0].text == "Table of Contents"
    assert output["Table of Contents"][1].text == "1. Node One"
    assert output["Table of Contents"][2].text == "2. Node Two"

    assert len(output["Body"]) == 2  # 2 TOC nodes
    assert output["Body"][0]["title"] == "1. Node One"
    assert output["Body"][1]["title"] == "2. Node Two"

    # Test normalization
    assert output["Body"][0]["level"] == 1
    assert output["Body"][1]["level"] == 2

    # Test assignment logic
    assert len(output["Body"][0]["items"]) == 4  # 1. Node One (header text), Overview, Table, Notes
    assert output["Body"][0]["items"][0].text == "1. Node One"
    assert output["Body"][0]["items"][0].level == 2  # Nested below the normalized Body node level 1

    # Assert Table Schema & Parsing for Node One
    node_one = output["Body"][0]
    assert node_one["overview"].strip() == "Here is an overview of Node One."
    assert node_one["notes"].strip() == "These are notes after the table for Node One."
    assert len(node_one["rules_table"]) == 1
    assert node_one["rules_table"][0]["Rules"] == "Rule 1"

    # Assert Table Merging & Row Merging for Node Two
    node_two = output["Body"][1]
    assert node_two["overview"].strip() == "Overview for Node Two."
    assert node_two["notes"].startswith("Notes for Node Two.")
    assert len(node_two["rules_table"]) == 1  # 2 tables were merged into 1 rule row because second table only had rules
    assert node_two["rules_table"][0]["Rule"] == "Rule A part 1 Rule A part 2"

    # Assert License extraction (regex fallback parsing)
    assert len(node_two["licensed_functionality"]) == 1
    assert node_two["licensed_functionality"][0]["name"] == "Validate Host Bank and Risk Book Selection at Circle Level"
    assert node_two["licensed_functionality"][0]["description"] == "This enhancement restricts users..."
