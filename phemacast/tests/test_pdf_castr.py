import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.castrs.pdf_castr import PDFCastr
from prompits.pools.filesystem import FileSystemPool


def test_pdf_castr_generates_pdf_from_nested_snapshot_content(tmp_path):
    pool = FileSystemPool("pdf_pool", "Temporary storage for pdf castr tests", str(tmp_path))
    castr = PDFCastr(name="PdfCastr", pool=pool, auto_register=False)

    phema = {
        "name": "Weekly Market 台積電 Brief",
        "description": "A concise cross-asset update for leadership — with nested data.",
        "sections": [
            {
                "name": "Macro Outlook",
                "description": "Key backdrop for the week ahead.",
                "content": [
                    "Inflation cooled for a second consecutive reading.",
                    {"pulse_name": "rates", "result": {"value": "Treasury yields eased across the curve."}},
                ],
            },
            {
                "name": "Equities",
                "content": [
                    {"key": "sp500", "data": {"close": 5123.45, "change_pct": 1.2}},
                    ["Breadth improved", "Leadership broadened"],
                ],
            },
        ],
    }

    result = castr.cast(
        phema,
        format="pdf",
        preferences={"audience": "Executive team", "language": "en-US"},
    )

    assert result["status"] == "success"
    assert result["format"] == "PDF"
    assert result["location"].startswith("media/")
    assert result["location"].endswith(".pdf")

    output_path = tmp_path / result["location"]
    assert output_path.exists()
    assert output_path.stat().st_size > 0
