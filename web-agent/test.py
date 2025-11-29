#!/usr/bin/env python3
"""
Quick sanity check for duckduckgo_search.DDGS.

Usage:
    python test_ddgs.py "lamar jackson contract" --max-results 5
    python test_ddgs.py "supabase pgBouncer pooling"
"""

import argparse
from ddgs import DDGS
import textwrap
from typing import Iterable, Mapping, Any


def print_results(label: str, results: Iterable[Mapping[str, Any]], *, show_image_url: bool = False):
    results = list(results)
    print(f"\n=== {label} (got {len(results)} results) ===")
    for i, r in enumerate(results, start=1):
        title = r.get("title") or "<no title>"

        # ddgs.text() -> "href"
        # ddgs.news() / ddgs.images() -> "url"
        # ddgs.images() also has "image" (direct image URL)
        href = r.get("href") or r.get("url") or r.get("image") or "<no url>"

        body = r.get("body") or r.get("excerpt") or r.get("description") or ""
        if body:
            body = textwrap.shorten(str(body), width=180, placeholder="...")

        print(f"\n[{i}] {title}")
        print(f"    URL: {href}")

        if show_image_url and r.get("image"):
            # For images, show both the page URL (above) and the direct image URL
            print(f"    Image: {r['image']}")

        if body:
            print(f"    Snippet: {body}")


def run_text_search(query: str, max_results: int = 5):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    print("TEXT SEARCH", results)


def run_news_search(query: str, max_results: int = 5):
    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=max_results))
    print_results("NEWS SEARCH", results)


def run_image_search(query: str, max_results: int = 5):
    with DDGS() as ddgs:
        results = list(ddgs.images(query, max_results=max_results))
    print_results("IMAGE SEARCH (metadata only)", results, show_image_url=True)


def main():
    parser = argparse.ArgumentParser(description="Test duckduckgo_search (DDGS) outputs.")
    parser.add_argument("query", help="Search query string, e.g. 'lamar jackson contract'")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Max results per search type (default: 5)",
    )
    parser.add_argument(
        "--no-news",
        action="store_true",
        help="Skip news search",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image search",
    )

    args = parser.parse_args()

    print(f"Query: {args.query!r}")

    # Basic text search
    run_text_search(args.query, args.max_results)

    # Optional news
    if not args.no_news:
        run_news_search(args.query, args.max_results)

    # Optional images (you’ll just see metadata, not actual images)
    if not args.no_images:
        run_image_search(args.query, min(args.max_results, 5))


if __name__ == "__main__":
    main()
