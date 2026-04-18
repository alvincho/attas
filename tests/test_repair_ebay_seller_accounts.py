from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from private.collectibles.workers.repair_ebay_seller_accounts import (
    _fetch_listing_page_seller_account_name_curl,
)


def test_fetch_listing_page_seller_account_name_curl_reads_storefront_sid(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=(
                '<a href="https://www.ebay.com/sch/i.html?sid=wrgstamp&_trksid='
                'p4429486.m2548.l2792">Visit store</a>'
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    account_name, response_url = _fetch_listing_page_seller_account_name_curl(
        source_listing_ids=["318117549159"],
        listing_urls=["https://www.ebay.com/itm/318117549159"],
        timeout_sec=12,
    )

    assert account_name == "wrgstamp"
    assert response_url == "https://www.ebay.com/itm/318117549159"
    assert calls == [["curl", "-L", "--max-time", "12", "https://www.ebay.com/itm/318117549159"]]
