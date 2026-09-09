#!/usr/bin/env python3
"""Verify that every script and stylesheet referenced by the deployed page exists."""

import argparse
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.assets.append(("script", values["src"]))
        elif tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.assets.append(("stylesheet", values["href"]))


def fetch(url):
    request = Request(url, headers={"User-Agent": "quant-workbench-deploy-check/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.status, response.headers.get_content_type(), response.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Deployed site URL, such as http://127.0.0.1")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/") + "/"

    status, content_type, body = fetch(base_url)
    if status != 200 or content_type != "text/html":
        raise RuntimeError(f"homepage returned {status} {content_type}")

    asset_parser = AssetParser()
    asset_parser.feed(body.decode("utf-8"))
    if not asset_parser.assets:
        raise RuntimeError("homepage does not reference any scripts or stylesheets")

    failures = []
    for kind, path in asset_parser.assets:
        asset_url = urljoin(base_url, path)
        if urlparse(asset_url).netloc != urlparse(base_url).netloc:
            continue
        try:
            asset_status, asset_type, asset_body = fetch(asset_url)
            expected = "javascript" if kind == "script" else "css"
            if asset_status != 200 or expected not in asset_type:
                failures.append(f"{path}: {asset_status} {asset_type}")
            elif asset_body.lstrip().startswith(b"<"):
                failures.append(f"{path}: returned HTML instead of {kind}")
            else:
                print(f"OK {path} ({asset_type}, {len(asset_body)} bytes)")
        except Exception as exc:
            failures.append(f"{path}: {exc}")

    if failures:
        print("Deployment verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Deployment verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
