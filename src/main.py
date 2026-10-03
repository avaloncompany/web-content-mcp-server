"""Apify MCP 서버 -- Web Content API 의 기능(웹·진단·개발자 도구·Hyperliquid)을 AI 에이전트용 도구로 노출한다.

이 Actor 는 얇은 연결 계층이다: 실제 처리(보안 접속·추출·검사)는 우리 API 가 하고, 여기서는
호출·과금·오류 전달만 한다. 성공한 호출에만 과금한다.
"""
from __future__ import annotations

import asyncio
import os

import httpx
import uvicorn
from apify import Actor
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

API_BASE = os.environ.get("WCAPI_BASE", "https://api.avaloncompany.ai")
TIMEOUT = 60.0


async def _call(path: str, params: dict, event: str | None, *, body: bool = False,
                xml: str | None = None) -> dict:
    """``body=True`` 면 JSON 본문으로 보낸다 -- 긴 텍스트(정규식 대상 등)는 URL 길이 한도를 넘는다.
    ``xml`` 이 있으면 그 XML 을 본문으로 POST 한다(SAML 메타데이터)."""
    secret = os.environ.get("WCAPI_SECRET", "")
    params = {k: v for k, v in params.items() if v is not None}
    headers = {"X-RapidAPI-Proxy-Secret": secret}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            if xml is not None:
                r = await client.post(f"{API_BASE}{path}", params=params, content=xml.encode(),
                                      headers={**headers, "Content-Type": "application/xml"})
            elif body:
                r = await client.post(f"{API_BASE}{path}", json=params, headers=headers)
            else:
                r = await client.get(f"{API_BASE}{path}", params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ToolError(f"Service unreachable, please retry ({type(exc).__name__})") from exc
    try:
        data = r.json()
    except ValueError as exc:
        raise ToolError(f"Unexpected response (HTTP {r.status_code})") from exc
    if r.status_code >= 400:
        raise ToolError(f"{data.get('error', 'Request failed')} [{data.get('error_code', r.status_code)}]")
    if event:
        await Actor.charge(event_name=event)
    return data


def build_server() -> FastMCP:
    server = FastMCP(name="web-content-url-tools")

    @server.tool()
    async def to_markdown(url: str, include_links: bool = True, include_tables: bool = True,
                          main_content_only: bool = True) -> dict:
        """Convert a web page into clean, LLM-ready Markdown (navigation, ads and footers removed).
        Returns title, markdown, word_count, character_count, language and a warning when the
        page needs JavaScript to render."""
        return await _call("/v1/markdown", {"url": url, "include_links": include_links,
                                            "include_tables": include_tables,
                                            "main_content_only": main_content_only}, "page-tool")

    @server.tool()
    async def get_metadata(url: str) -> dict:
        """Get a page's title, description, preview image, site name, canonical URL, favicon,
        language, author, publish time and Open Graph / Twitter tags."""
        return await _call("/v1/metadata", {"url": url}, "page-tool")

    @server.tool()
    async def extract_structure(url: str) -> dict:
        """Extract a page's heading outline, links (internal/external), images, tables and JSON-LD."""
        return await _call("/v1/extract", {"url": url}, "page-tool")

    @server.tool()
    async def detect_technologies(url: str) -> dict:
        """Detect the CMS, framework, e-commerce platform, CDN, analytics and payment tools a
        website uses, with the evidence for each."""
        return await _call("/v1/tech", {"url": url}, "page-tool")

    @server.tool()
    async def trace_redirects(url: str) -> dict:
        """Expand a short link or trace every redirect hop (HTTP and meta refresh) to the final URL."""
        return await _call("/v1/redirects", {"url": url}, "check-tool")

    @server.tool()
    async def check_ssl(host: str) -> dict:
        """Check a domain's TLS certificate on port 443: issuer, expiry, days remaining, SANs and
        whether browsers trust it (with the reason when not)."""
        return await _call("/v1/ssl", {"host": host}, "check-tool")

    @server.tool()
    async def grade_security_headers(url: str) -> dict:
        """Grade a website's HTTP security headers from A+ to F, listing what is missing and why."""
        return await _call("/v1/security-headers", {"url": url}, "check-tool")

    @server.tool()
    async def parse_robots(url: str, path: str | None = None, user_agent: str = "*") -> dict:
        """Parse a site's robots.txt. With `path` (and optional `user_agent`), says whether that path
        may be crawled."""
        return await _call("/v1/robots", {"url": url, "path": path, "user_agent": user_agent},
                           "check-tool")

    @server.tool()
    async def parse_sitemap(url: str) -> dict:
        """List the URLs in a sitemap (or the child sitemaps of a sitemap index). Pass a site URL to
        find the sitemap automatically. Up to 5,000 URLs."""
        return await _call("/v1/sitemap", {"url": url}, "check-tool")

    @server.tool()
    async def lookup_domain(domain: str) -> dict:
        """WHOIS (RDAP) registration data for a domain — registrar, created/expiry dates, age in days,
        nameservers — plus DNS records and email setup (MX, SPF, DMARC)."""
        return await _call("/v1/domain", {"domain": domain}, "check-tool")

    @server.tool()
    async def audit_seo(url: str) -> dict:
        """On-page SEO audit of a page: 0-100 score, grade and prioritised issues with fixes
        (title, description, headings, canonical, noindex, alt text, structured data, robots, sitemap)."""
        return await _call("/v1/seo-audit", {"url": url}, "page-tool")

    @server.tool()
    async def check_broken_links(url: str, max_links: int = 50, include_external: bool = True) -> dict:
        """Check the links on a page (up to 100) and report broken, redirected and bot-blocked links."""
        return await _call("/v1/broken-links", {"url": url, "max_links": max_links,
                                                "include_external": include_external}, "page-tool")

    @server.tool()
    async def read_feed(url: str) -> dict:
        """Read an RSS, Atom or RDF feed as JSON (up to 200 items). A website URL finds its feed."""
        return await _call("/v1/feed", {"url": url}, "check-tool")

    # ── 개발자 도구 ──
    @server.tool()
    async def parse_cron(expression: str, count: int = 5, timezone: str = "UTC",
                         start: str | None = None) -> dict:
        """Validate a cron expression (5 or 6 fields, or @daily-style macros), explain it in plain
        English and list the previous and next run times in an IANA time zone."""
        return await _call("/v1/cron", {"expression": expression, "count": count, "timezone": timezone,
                                        "start": start}, "check-tool")

    @server.tool()
    async def test_regex(pattern: str, text: str, flags: str = "", replacement: str | None = None) -> dict:
        """Run a regular expression (Python/PCRE syntax) against text: every match with positions and
        groups, plus a find-and-replace result when `replacement` is given. Flags: i, m, s, x, u.
        Runaway patterns stop after 0.1 s with an error instead of hanging."""
        return await _call("/v1/regex", {"pattern": pattern, "text": text, "flags": flags,
                                         "replacement": replacement}, "check-tool", body=True)

    @server.tool()
    async def convert_color(color: str) -> dict:
        """Convert a color (#hex, rgb(), hsl() or CSS name) to HEX, RGB, HSL, HSV and CMYK, with
        luminance, best text color, contrast against white/black and matching palettes."""
        return await _call("/v1/color", {"color": color}, "check-tool")

    @server.tool()
    async def check_color_contrast(foreground: str, background: str) -> dict:
        """WCAG 2 contrast ratio between two colors with AA/AAA pass/fail for text and UI components."""
        return await _call("/v1/color/contrast", {"foreground": foreground, "background": background},
                           "check-tool")

    @server.tool()
    async def inspect_unicode(text: str) -> dict:
        """Inspect text character by character (code point, name, category, UTF-8 bytes) with length
        in code points, graphemes, UTF-8 bytes and UTF-16 units, and NFC/NFD/NFKC/NFKD forms."""
        return await _call("/v1/unicode", {"text": text}, "check-tool", body=True)

    @server.tool()
    async def convert_timezone(from_timezone: str, to_timezones: str, time: str | None = None) -> dict:
        """Convert a time (ISO 8601; now if omitted) from one IANA time zone to others
        (comma-separated), with offsets, abbreviations and daylight-saving status."""
        return await _call("/v1/timezone/convert", {"from": from_timezone, "to": to_timezones, "time": time},
                           "check-tool")

    @server.tool()
    async def list_timezones(region: str | None = None) -> dict:
        """List IANA time zone names, optionally only one region (Europe, Asia, America...)."""
        return await _call("/v1/timezone/list", {"region": region}, "check-tool")

    # ── Hyperliquid 무기한 선물 ──
    @server.tool()
    async def hyperliquid_markets(coin: str | None = None, sort: str = "volume", order: str = "desc",
                                  limit: int = 50) -> dict:
        """Hyperliquid perpetual markets: mark/oracle price, 24h change, hourly and annualized funding,
        open interest (coins and USD), 24h volume, max leverage. Filter with `coin` (e.g. "BTC,ETH");
        sort by volume, open_interest, funding, change or coin."""
        return await _call("/v1/hyperliquid/markets", {"coin": coin, "sort": sort, "order": order,
                                                       "limit": limit}, "check-tool")

    @server.tool()
    async def hyperliquid_funding_history(coin: str, hours: int = 24) -> dict:
        """Hourly funding rate history for a Hyperliquid perpetual (up to 720 hours) with average,
        annualized and cumulative rate."""
        return await _call("/v1/hyperliquid/funding", {"coin": coin, "hours": hours}, "check-tool")

    @server.tool()
    async def hyperliquid_candles(coin: str, interval: str = "1h", limit: int = 100) -> dict:
        """OHLCV candles for a Hyperliquid perpetual. Intervals: 1m 3m 5m 15m 30m 1h 2h 4h 8h 12h 1d 3d 1w;
        up to 500 candles."""
        return await _call("/v1/hyperliquid/candles", {"coin": coin, "interval": interval, "limit": limit},
                           "check-tool")

    # ── 진단 도구 ──
    @server.tool()
    async def check_email_domain(domain: str, dkim_selector: str | None = None) -> dict:
        """Email authentication health check for a domain (or email address): MX, SPF with the
        10-DNS-lookup limit, DMARC policy and alignment, DKIM keys (common selectors plus up to 5 of
        yours, comma-separated), MTA-STS, TLS-RPT and BIMI. Each check is pass/warn/fail with fixes,
        plus a 0-100 score and grade."""
        return await _call("/v1/email-domain", {"domain": domain, "dkim_selector": dkim_selector}, "page-tool")

    @server.tool()
    async def analyze_saml_metadata(xml: str | None = None, url: str | None = None) -> dict:
        """Analyse SAML 2.0 metadata given as XML text or a metadata URL: entity ID, IdP/SP roles,
        SSO/SLO/ACS endpoints and bindings, NameID formats, signing certificates (expiry, key size,
        hash) and prioritised issues such as certificates expiring within 45 days or HTTP endpoints."""
        if not xml and not url:
            raise ToolError("Provide either xml or url")
        if url:
            return await _call("/v1/saml/metadata", {"url": url}, "check-tool")
        return await _call("/v1/saml/metadata", {}, "check-tool", xml=xml)

    @server.tool()
    async def check_oidc_provider(issuer: str) -> dict:
        """Check an OpenID Connect provider from its issuer URL: discovery document, exact issuer
        match, required fields, HTTPS endpoints, PKCE S256, ID token algorithms ('none' flagged) and
        the JWKS keys (size, duplicate kid, exposed private material, certificate expiry)."""
        return await _call("/v1/oidc", {"issuer": issuer}, "check-tool")

    @server.custom_route("/", methods=["GET"])
    async def root(_: Request) -> JSONResponse:
        # Standby 준비 확인(x-apify-container-server-readiness-probe)에 응답한다.
        return JSONResponse({"status": "ok", "mcp": "/mcp"})

    return server


async def _self_check() -> None:
    """Standby 가 아닌 일반 실행(Apify 스토어의 매일 자동 시험 포함)은 짧은 점검 결과를 남기고 끝낸다.

    서버만 띄우고 결과를 안 남기면 자동 시험이 5분 시간 초과로 실패해 '점검 중' 으로 표시된다.
    점검 호출은 과금하지 않는다.
    """
    checks = {
        "trace_redirects": ("/v1/redirects", {"url": "http://example.com"}),
        "check_ssl": ("/v1/ssl", {"host": "example.com"}),
    }
    for tool, (path, params) in checks.items():
        try:
            data = await _call(path, params, None)
            await Actor.push_data({"tool": tool, "ok": True, "summary": {
                k: data.get(k) for k in ("final_url", "redirect_count", "trusted", "days_remaining") if k in data}})
        except ToolError as exc:
            await Actor.push_data({"tool": tool, "ok": False, "error": str(exc)})
    await Actor.push_data({"tool": "mcp_server", "ok": True,
                           "note": "Use the Standby URL with an MCP client: https://avalonai--web-content-url-tools-mcp.apify.actor/mcp"})


async def main() -> None:
    async with Actor:
        if os.environ.get("APIFY_META_ORIGIN") != "STANDBY":
            await _self_check()
            return
        app = build_server().http_app(transport="streamable-http", path="/mcp")
        config = uvicorn.Config(app, host="0.0.0.0", port=Actor.configuration.web_server_port,
                                log_level="warning")
        Actor.log.info("MCP server listening on /mcp")
        await uvicorn.Server(config).serve()
