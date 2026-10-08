"""Fetching user-supplied URLs safely (job offers, portfolio pages) for the public sandbox.

A server that downloads any URL a visitor types is a classic SSRF vector: "http://127.0.0.1:5432",
"http://169.254.169.254/latest/meta-data", or a public name that resolves to a private address. Rules:

* http(s) only, default ports only, no credentials in the URL;
* every resolved address must be globally routable (no loopback, private, link-local, CGNAT, multicast);
* redirects are followed by hand (3 at most) and every hop is re-validated;
* bounded size and time; only HTML, text and PDF are read.

Residual risk, stated: a DNS answer can change between our check and the connection (rebinding). The
container network is the second line of defence; see docs/DEPLOYMENT.md.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 2_000_000
TIMEOUT = 10.0
USER_AGENT = "TalentEngine-AI/0.3 (+https://github.com/FlorianMartins/talentengine-ai)"


class FetchError(ValueError):
    pass


@dataclass
class Page:
    url: str
    title: str
    text: str
    content_type: str


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("only http(s) links are accepted")
    if parts.username or parts.password:
        raise FetchError("links with credentials are not accepted")
    if parts.port not in (None, 80, 443):
        raise FetchError("only standard web ports are accepted")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"unknown host {parts.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise FetchError("this address is not publicly reachable")


def fetch(url: str) -> Page:
    holder: list[str] = []
    final_url, body, ctype = _fetch_raw(url, holder)
    return _to_page(final_url, body, ctype)


def _fetch_raw(url: str, holder: list[str]) -> tuple[str, bytes, str]:
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False,
                      headers={"User-Agent": USER_AGENT, "Accept-Language": "fr,en;q=0.8"}) as client:
        for _ in range(4):
            _check_url(url)
            with client.stream("GET", url) as resp:
                if resp.is_redirect and "location" in resp.headers:
                    url = urljoin(url, resp.headers["location"])
                    continue
                if resp.status_code != 200:
                    raise FetchError(f"the page answered HTTP {resp.status_code}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ("text/html", "text/plain", "application/xhtml+xml", "application/pdf"):
                    raise FetchError(f"unsupported content type {ctype or 'unknown'}")
                body = b""
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise FetchError("page too large")
                holder.append(body.decode("utf-8", errors="replace"))
                return str(resp.url), body, ctype
    raise FetchError("too many redirects")


def _to_page(url: str, body: bytes, ctype: str) -> Page:
    if ctype == "application/pdf":
        from ..pipeline import extract_text

        return Page(url, "", extract_text("page.pdf", body), ctype)
    html = body.decode("utf-8", errors="replace")
    if ctype == "text/plain":
        return Page(url, "", html, ctype)
    posting = job_posting_from_jsonld(html)
    if posting:
        return Page(url, posting[0], posting[1], ctype)
    parser = _TextParser()
    parser.feed(html)
    return Page(url, parser.title.strip(), parser.text(), ctype)


# --------------------------------------------------------------------------------------------------
# HTML → text
# --------------------------------------------------------------------------------------------------

_SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button", "template", "iframe"}
_BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "ul", "ol",
          "dt", "dd", "blockquote", "pre"}


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in _BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)[:60_000]


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    return parser.text()


def job_posting_from_jsonld(html: str) -> tuple[str, str] | None:
    """Most job boards (Welcome to the Jungle, Indeed, LinkedIn, ATS career pages) embed schema.org JobPosting."""
    for raw in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("@type") == "JobPosting" and item.get("description"):
                    parts = [html_to_text(str(item["description"]))]
                    for key in ("qualifications", "skills", "experienceRequirements", "educationRequirements"):
                        if isinstance(item.get(key), str):
                            parts.append(html_to_text(item[key]))
                    return str(item.get("title", "")).strip(), "\n".join(parts)
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)
    return None


_LINKEDIN_JOB = re.compile(r"linkedin\.com/.*?(?:jobs/view/(?:[^/?#]*-)?|currentJobId=)(\d{6,})", re.IGNORECASE)


def fetch_offer(url: str) -> Page:
    """A job offer from a link. LinkedIn job pages are read through their public, logged-out view."""
    m = _LINKEDIN_JOB.search(url)
    if m:
        raw = fetch_html(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{m.group(1)}")
        body = re.search(r'class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', raw, re.DOTALL)
        title = re.search(r'class="[^"]*top-card-layout__title[^"]*"[^>]*>(.*?)<', raw, re.DOTALL)
        if not body:
            raise FetchError("LinkedIn did not return this offer publicly: paste its text instead")
        return Page(url, " ".join(title.group(1).split()) if title else "", html_to_text(body.group(1)), "text/html")
    return fetch(url)


def fetch_html(url: str) -> str:
    """Raw HTML of a page, with the same SSRF protections as ``fetch``."""
    holder: list[str] = []
    _fetch_raw(url, holder)
    return holder[0]
