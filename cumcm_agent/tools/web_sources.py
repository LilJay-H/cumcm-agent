from __future__ import annotations

import ipaddress
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any

import requests


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0 and data.strip():
            self.parts.append(data.strip())


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self.current_url: str | None = None
        self.current_title: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "a" and "result__a" in classes:
            href = attributes.get("href") or ""
            parsed = urllib.parse.urlparse(href)
            if "duckduckgo.com" in parsed.netloc or href.startswith("//"):
                href = urllib.parse.parse_qs(parsed.query).get("uddg", [href])[0]
            self.current_url = urllib.parse.unquote(href)
            self.current_title = []

    def handle_data(self, data: str) -> None:
        if self.current_url is not None:
            self.current_title.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_url is not None:
            self.results.append(
                {
                    "title": " ".join(
                        part for part in self.current_title if part
                    ),
                    "url": self.current_url,
                    "snippet": "",
                }
            )
            self.current_url = None
            self.current_title = []


def _safe_public_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public HTTP(S) URLs are allowed")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        raise ValueError("local network target rejected")
    try:
        ip = ipaddress.ip_address(hostname)
        if not ip.is_global:
            raise ValueError("private or non-global network target rejected")
    except ValueError as exc:
        if "rejected" in str(exc):
            raise
    return url


def search_bing_rss(
    query: str, max_results: int = 3, timeout_seconds: int = 20
) -> list[dict[str, str]]:
    search_url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"format": "rss", "q": query}
    )
    request = urllib.request.Request(
        search_url, headers={"User-Agent": "CUMCM-Agent-v0/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read(1_000_000)
    root = ET.fromstring(body)
    results: list[dict[str, str]] = []
    for item in root.findall("./channel/item")[:max_results]:
        results.append(
            {
                "title": item.findtext("title", default="").strip(),
                "url": item.findtext("link", default="").strip(),
                "snippet": item.findtext("description", default="").strip(),
            }
        )
    return results


def search_duckduckgo_html(
    query: str, max_results: int = 3, timeout_seconds: int = 20
) -> list[dict[str, str]]:
    search_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query}
    )
    response = requests.get(
        search_url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    parser = _DuckDuckGoResultParser()
    parser.feed(response.content[:1_000_000].decode("utf-8", errors="replace"))
    return parser.results[:max_results]


def fetch_visible_text(
    url: str,
    timeout_seconds: int = 20,
    max_bytes: int = 1_000_000,
    max_chars: int = 10_000,
) -> str:
    safe_url = _safe_public_url(url)
    request = urllib.request.Request(
        safe_url, headers={"User-Agent": "CUMCM-Agent-v0/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(max_bytes)
    if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
        raise ValueError(f"unsupported content type: {content_type}")
    decoded = body.decode(charset, errors="replace")
    if content_type == "text/plain":
        visible = decoded
    else:
        parser = _VisibleTextParser()
        parser.feed(decoded)
        visible = "\n".join(parser.parts)
    visible = re.sub(r"\n{3,}", "\n\n", visible)
    return visible[:max_chars]


def parse_query_plan(text: str, max_queries: int) -> list[str]:
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1))
    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))
    for candidate in candidates:
        try:
            payload: Any = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        queries = payload.get("queries", []) if isinstance(payload, dict) else payload
        if isinstance(queries, list):
            cleaned = [
                str(item).strip()
                for item in queries
                if str(item).strip()
            ]
            if cleaned:
                return cleaned[:max_queries]
    raise ValueError("research query planner did not return valid JSON queries")
