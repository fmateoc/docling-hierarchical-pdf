import sys
import json
import json.encoder
from pathlib import Path
from docling.document_converter import DocumentConverter
from hierarchical.edval_postprocessor import EdvalPostprocessor
import pandas as pd

class DocItemEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return super().default(obj)

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_full.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    converter = DocumentConverter()
    result = converter.convert(pdf_path)

    ep = EdvalPostprocessor(result)
    output = ep.process()

    out_path = Path(pdf_path).with_suffix(".json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, cls=DocItemEncoder)

if __name__ == "__main__":
    main()
