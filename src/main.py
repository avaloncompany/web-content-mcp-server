"""Apify MCP 서버 -- Web Content API 의 기능(웹·진단·개발자 도구·Hyperliquid)을 AI 에이전트용 도구로 노출한다.

이 Actor 는 얇은 연결 계층이다: 실제 처리(보안 접속·추출·검사)는 우리 API 가 하고, 여기서는
호출·과금·오류 전달만 한다. 성공한 호출에만 과금한다.
"""
from __future__ import annotations

import asyncio
import os

from typing import Annotated

import httpx
import uvicorn
from apify import Actor
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

API_BASE = os.environ.get("WCAPI_BASE", "https://api.avaloncompany.ai")
#: 웹 도구 공통 인자. 모듈 최상단에 둬야 한다 -- annotations 가 지연 평가라 함수 안 별칭은 풀리지 않는다.
URL = Annotated[str, Field(description="Full public http(s) URL of the page, e.g. https://example.com/blog/post")]
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
    server = FastMCP(
        name="web-content-url-tools",
        instructions=(
            "Read-only tools for AI agents. Web tools fetch one public http/https page (no JavaScript rendering, "
            "private/internal addresses refused). Developer tools compute locally. Hyperliquid tools read public market "
            "data. Failed calls return an error with a reason and are not charged."),
    )
    # 도구 정의 품질(목적·사용 시점·동작·파라미터 의미)이 디렉터리 점수와 에이전트의 도구 선택을 좌우한다.
    # 모든 도구가 읽기 전용이고, 웹 도구만 외부 사이트에 접속한다.
    web = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
    local = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

    # ── Page tools: read one page ──
    @server.tool(title="Web page to Markdown", annotations=web)
    async def to_markdown(
        url: URL,
        include_links: Annotated[bool, Field(description="Keep hyperlinks as [text](url) in the Markdown")] = True,
        include_tables: Annotated[bool, Field(description="Keep HTML tables as Markdown tables")] = True,
        main_content_only: Annotated[bool, Field(description="Drop navigation, ads, sidebars and footers; set false to keep the whole page")] = True,
    ) -> dict:
        """Read a web page as clean, LLM-ready Markdown.

        Use this to read or summarise an article, doc or product page. For only the title, description and
        preview image use get_metadata; for headings/links/tables as JSON use extract_structure.
        Returns: title, markdown, word_count, character_count, language, and a warning when the page needs
        JavaScript to render (its static HTML has little text).
        Behavior: fetches the URL once (no JavaScript, max 5 MB, ~1-10 s). Sites that block bots return
        target_blocked. Cost: $0.003 per successful call; errors are free."""
        return await _call("/v1/markdown", {"url": url, "include_links": include_links,
                                            "include_tables": include_tables,
                                            "main_content_only": main_content_only}, "page-tool")

    @server.tool(title="URL metadata and Open Graph", annotations=web)
    async def get_metadata(url: URL) -> dict:
        """Get a page's link-preview metadata without its body text.

        Use this to build a link preview or check how a URL will look when shared. For the full text use
        to_markdown.
        Returns: title, description, preview image, site name, type, canonical URL, favicon, language,
        author, published time, keywords, Twitter card type, theme color and JSON-LD types (Open Graph and
        Twitter tags are used where present).
        Behavior: fetches the URL once (no JavaScript). Cost: $0.003 per successful call; errors are free."""
        return await _call("/v1/metadata", {"url": url}, "page-tool")

    @server.tool(title="Page structure as JSON", annotations=web)
    async def extract_structure(url: URL) -> dict:
        """Extract a page's structure as JSON: heading outline, links, images, tables and JSON-LD.

        Use this to analyse how a page is organised, list its links or pull its tables. For readable text use
        to_markdown; to test whether its links work use check_broken_links.
        Returns: headings, links (internal and external), images, tables, JSON-LD objects and counts.
        Behavior: fetches the URL once (no JavaScript). Cost: $0.003 per successful call; errors are free."""
        return await _call("/v1/extract", {"url": url}, "page-tool")

    @server.tool(title="Detect website technologies", annotations=web)
    async def detect_technologies(url: URL) -> dict:
        """Detect the technology stack behind a website.

        Use this for competitor or lead research: which CMS, framework, e-commerce platform, CDN, analytics,
        payment and chat tools a site runs (including Korean platforms such as Cafe24 and Naver).
        Returns: technologies with name, category and the evidence (header, script or meta tag) for each.
        Behavior: fetches the URL once and inspects HTML and response headers. Cost: $0.003 per successful
        call; errors are free."""
        return await _call("/v1/tech", {"url": url}, "page-tool")

    @server.tool(title="SEO audit of a page", annotations=web)
    async def audit_seo(url: URL) -> dict:
        """Audit one page's on-page SEO and list what to fix, most important first.

        Use this to review a page before publishing or to explain low search visibility. It checks one page,
        not the whole site; for crawl rules use parse_robots, for the URL list use parse_sitemap.
        Returns: score 0-100, grade, summary, and issues (severity, code, message with the fix) covering title, meta
        description, headings, canonical, noindex, image alt text, structured data, robots.txt and sitemap.
        Behavior: fetches the page plus robots.txt and the sitemap. Cost: $0.003 per successful call."""
        return await _call("/v1/seo-audit", {"url": url}, "page-tool")

    @server.tool(title="Check links on a page", annotations=web)
    async def check_broken_links(
        url: URL,
        max_links: Annotated[int, Field(ge=1, le=100, description="How many links to test, 1-100")] = 50,
        include_external: Annotated[bool, Field(description="Also test links to other sites, not just the same site")] = True,
    ) -> dict:
        """Find broken links on a page.

        Use this to clean up a page or audit outbound links. To list links without testing them use
        extract_structure; to follow one URL's redirects use trace_redirects.
        Returns: links_found, checked, broken_count, broken, redirected, blocked_count (targets that refuse
        bots, not counted as broken), per-link results with status codes, and not_checked.
        Behavior: fetches the page, then requests up to max_links links (at most 20 per host). Cost: $0.003
        per successful call; errors are free."""
        return await _call("/v1/broken-links", {"url": url, "max_links": max_links,
                                                "include_external": include_external}, "page-tool")

    # ── Check tools: one quick check ──
    @server.tool(title="Trace redirects / unshorten URL", annotations=web)
    async def trace_redirects(url: Annotated[str, Field(description="URL to follow, including short links such as https://bit.ly/abc")]) -> dict:
        """Follow every redirect hop of a URL to its final destination.

        Use this to expand a short link, check where a link really goes, or debug redirect chains and loops.
        Returns: input_url, final_url, final_status_code, redirect_count, the chain of hops (url, status_code,
        location, type -- HTTP or meta refresh), and flags for loop_detected, too_many_redirects,
        https_upgrade and domain_changed.
        Behavior: requests each hop without downloading page bodies. Cost: $0.001 per successful call."""
        return await _call("/v1/redirects", {"url": url}, "check-tool")

    @server.tool(title="Check SSL/TLS certificate", annotations=web)
    async def check_ssl(host: Annotated[str, Field(description="Domain or https URL, e.g. example.com (port 443)")]) -> dict:
        """Check a domain's TLS certificate on port 443.

        Use this to see when a certificate expires or why browsers distrust it. For HTTP security headers use
        grade_security_headers; for domain registration use lookup_domain.
        Returns: trusted (with the verification error when not), issuer, subject common name, SANs,
        valid_from, valid_to, days_remaining, expired, self_signed, signature algorithm, TLS version, cipher
        and SHA-256 fingerprint.
        Behavior: opens one TLS connection. Cost: $0.001 per successful call; errors are free."""
        return await _call("/v1/ssl", {"host": host}, "check-tool")

    @server.tool(title="Grade security headers", annotations=web)
    async def grade_security_headers(url: URL) -> dict:
        """Grade a website's HTTP security headers from A+ to F.

        Use this for a quick security posture check of a site. For the certificate itself use check_ssl.
        Returns: grade, score, each header (HSTS, CSP, X-Frame-Options, X-Content-Type-Options,
        Referrer-Policy, Permissions-Policy and more) with present/missing and why it matters, plus
        information-leaking headers and cookies missing Secure/HttpOnly/SameSite.
        Behavior: one request for the response headers. Cost: $0.001 per successful call."""
        return await _call("/v1/security-headers", {"url": url}, "check-tool")

    @server.tool(title="Parse robots.txt", annotations=web)
    async def parse_robots(
        url: Annotated[str, Field(description="Any URL on the site; its /robots.txt is read")],
        path: Annotated[str | None, Field(description="Optional path to test, e.g. /private/page")] = None,
        user_agent: Annotated[str, Field(description="Crawler user agent to test the path for, e.g. Googlebot")] = "*",
    ) -> dict:
        """Read a site's robots.txt and optionally test whether a path may be crawled.

        Use this before crawling a site or to debug why a page is not indexed. For the site's URL list use
        parse_sitemap.
        Returns: groups of rules per user agent, sitemap URLs, and when path is given: allowed (true/false)
        with the matching rule.
        Behavior: fetches /robots.txt once. Cost: $0.001 per successful call; errors are free."""
        return await _call("/v1/robots", {"url": url, "path": path, "user_agent": user_agent},
                           "check-tool")

    @server.tool(title="Parse XML sitemap", annotations=web)
    async def parse_sitemap(url: Annotated[str, Field(description="Sitemap URL, or a site URL to discover the sitemap from robots.txt and common paths")]) -> dict:
        """List the URLs in a site's XML sitemap.

        Use this to enumerate a site's pages before reading or auditing them. For crawl permissions use
        parse_robots.
        Returns: sitemap_url, type (urlset or sitemapindex), count, truncated, and up to 5,000 URLs, or the
        child sitemaps (loc, lastmod) of an index. Gzip sitemaps are supported.
        Behavior: fetches the sitemap (discovering it if needed). Cost: $0.001 per successful call."""
        return await _call("/v1/sitemap", {"url": url}, "check-tool")

    @server.tool(title="Domain WHOIS and DNS lookup", annotations=web)
    async def lookup_domain(domain: Annotated[str, Field(description="Domain or URL, e.g. example.com")]) -> dict:
        """Look up a domain's registration (RDAP/WHOIS) and DNS records.

        Use this to check who registered a domain, when it expires or how old it is. For a full email
        authentication diagnosis use check_email_domain.
        Returns: registrar, created/updated/expiry dates, age_days, status, nameservers, A/AAAA/MX/NS/TXT/CAA
        records, and SPF and DMARC strings.
        Behavior: RDAP and DNS queries only, no web page fetch. Cost: $0.001 per successful call."""
        return await _call("/v1/domain", {"domain": domain}, "check-tool")

    @server.tool(title="Read RSS/Atom feed", annotations=web)
    async def read_feed(url: Annotated[str, Field(description="Feed URL, or a website URL to discover its feed")]) -> dict:
        """Read an RSS, Atom or RDF feed as JSON.

        Use this to get a site's latest posts. Given a normal page URL it finds the feed from the page.
        Returns: feed_url, type, title, link, updated and up to 200 items (title, link, published, author,
        summary, id).
        Behavior: fetches the page and/or the feed. Cost: $0.001 per successful call; errors are free."""
        return await _call("/v1/feed", {"url": url}, "check-tool")

    # ── Diagnostics ──
    @server.tool(title="Email domain health check", annotations=web)
    async def check_email_domain(
        domain: Annotated[str, Field(description="Domain or email address, e.g. example.com or info@example.com")],
        dkim_selector: Annotated[str | None, Field(description="Your DKIM selector(s), comma-separated, up to 5 (common selectors are always tried)")] = None,
    ) -> dict:
        """Diagnose a domain's email authentication and deliverability setup.

        Use this when mail lands in spam or before setting up a sending service. For raw DNS/WHOIS use
        lookup_domain.
        Returns: score 0-100, grade, and pass/warn/fail with fixes for MX, SPF (including the 10-DNS-lookup
        limit), DMARC policy and alignment, DKIM keys, MTA-STS, TLS-RPT and BIMI.
        Behavior: DNS queries plus the MTA-STS policy file. Cost: $0.003 per successful call."""
        return await _call("/v1/email-domain", {"domain": domain, "dkim_selector": dkim_selector}, "page-tool")

    @server.tool(title="Analyze SAML metadata", annotations=web)
    async def analyze_saml_metadata(
        xml: Annotated[str | None, Field(description="SAML 2.0 metadata XML text (give this or url)")] = None,
        url: Annotated[str | None, Field(description="Public metadata URL (give this or xml)")] = None,
    ) -> dict:
        """Analyse SAML 2.0 identity-provider or service-provider metadata.

        Use this when setting up or debugging SSO. Give either the XML or its URL. For OpenID Connect
        providers use check_oidc_provider.
        Returns: entity ID, IdP/SP roles, SSO/SLO/ACS endpoints and bindings, NameID formats, signing
        certificates (expiry, key size, hash) and prioritised issues such as certificates expiring within
        45 days or plain-HTTP endpoints.
        Behavior: parses the XML safely (no external entities); fetches the URL when given. Cost: $0.001."""
        if not xml and not url:
            raise ToolError("Provide either xml or url")
        if url:
            return await _call("/v1/saml/metadata", {"url": url}, "check-tool")
        return await _call("/v1/saml/metadata", {}, "check-tool", xml=xml)

    @server.tool(title="Check OpenID Connect provider", annotations=web)
    async def check_oidc_provider(issuer: Annotated[str, Field(description="Issuer URL, e.g. https://accounts.google.com")]) -> dict:
        """Check an OpenID Connect provider's discovery document and signing keys.

        Use this when integrating OIDC login or auditing an identity provider. For SAML use
        analyze_saml_metadata.
        Returns: discovery URL, exact issuer match, required fields, HTTPS endpoints, PKCE S256 support,
        ID-token algorithms ('none' flagged), and JWKS keys (size, duplicate kid, exposed private material,
        certificate expiry) with issues.
        Behavior: fetches the discovery document and JWKS. Cost: $0.001 per successful call."""
        return await _call("/v1/oidc", {"issuer": issuer}, "check-tool")

    # ── Developer tools: computed locally, no web access ──
    @server.tool(title="Explain a cron expression", annotations=local)
    async def parse_cron(
        expression: Annotated[str, Field(description="Cron expression: 5 fields (min hour day month weekday), 6 with seconds, or @daily/@hourly/@weekly/@monthly/@yearly")],
        count: Annotated[int, Field(ge=1, le=50, description="How many upcoming run times to list, 1-50")] = 5,
        timezone: Annotated[str, Field(description="IANA time zone for the run times, e.g. America/New_York")] = "UTC",
        start: Annotated[str | None, Field(description="ISO 8601 date-time to count from; defaults to now")] = None,
    ) -> dict:
        """Validate a cron expression, explain it in plain English and list its run times.

        Use this to check a schedule before deploying it or to explain one to a user. Daylight-saving changes
        are handled like standard cron (fixed-time jobs run once; skipped times move to the next real time).
        Returns: valid, description, fields, previous_run and next_runs (ISO 8601 with offset).
        Behavior: computed locally. Cost: $0.001 per successful call; invalid expressions return the reason."""
        return await _call("/v1/cron", {"expression": expression, "count": count, "timezone": timezone,
                                        "start": start}, "check-tool")

    @server.tool(title="Test a regular expression", annotations=local)
    async def test_regex(
        pattern: Annotated[str, Field(description="Regular expression (Python/PCRE syntax), up to 2,000 characters")],
        text: Annotated[str, Field(description="Text to search, up to 100,000 characters")],
        flags: Annotated[str, Field(description="Any of i (ignore case), m (multiline), s (dot matches newline), x (verbose), u (unicode)")] = "",
        replacement: Annotated[str | None, Field(description="Optional replacement, with \\1 or \\g<name> group references")] = None,
    ) -> dict:
        """Run a regular expression against text and show every match.

        Use this to verify a pattern before using it in code or to extract values from text.
        Returns: valid (or the parser error), match_count, matches (text, start, end, groups, named_groups),
        and the replaced text when replacement is given.
        Behavior: computed locally with a time limit, so catastrophic patterns stop in about 0.1 s with an
        error instead of hanging. Cost: $0.001 per successful call."""
        return await _call("/v1/regex", {"pattern": pattern, "text": text, "flags": flags,
                                         "replacement": replacement}, "check-tool", body=True)

    @server.tool(title="Convert a color", annotations=local)
    async def convert_color(color: Annotated[str, Field(description="Color as #hex, rgb(), hsl() or a CSS name, e.g. #ff6347 or tomato")]) -> dict:
        """Convert one color between formats and suggest matching palettes.

        Use this for design work: format conversion, picking readable text color or building a palette. To
        compare two colors for accessibility use check_color_contrast.
        Returns: hex, rgb, hsl, hsv, cmyk, CSS strings, luminance, best text color, contrast vs white/black,
        nearest CSS name and palettes (complementary, analogous, triadic, tetradic, shades).
        Behavior: computed locally. Cost: $0.001 per successful call."""
        return await _call("/v1/color", {"color": color}, "check-tool")

    @server.tool(title="Check color contrast (WCAG)", annotations=local)
    async def check_color_contrast(
        foreground: Annotated[str, Field(description="Text color as #hex, rgb(), hsl() or CSS name")],
        background: Annotated[str, Field(description="Background color as #hex, rgb(), hsl() or CSS name")],
    ) -> dict:
        """Check whether a text/background color pair is readable under WCAG 2.

        Use this for accessibility checks. For converting a single color use convert_color.
        Returns: contrast ratio and pass/fail for AA and AAA (normal and large text) and UI components.
        Behavior: computed locally. Cost: $0.001 per successful call."""
        return await _call("/v1/color/contrast", {"foreground": foreground, "background": background},
                           "check-tool")

    @server.tool(title="Inspect Unicode text", annotations=local)
    async def inspect_unicode(text: Annotated[str, Field(description="Text to inspect, up to 2,000 characters")]) -> dict:
        """Show exactly which Unicode characters a string contains.

        Use this to find invisible or look-alike characters, count characters the way users see them, or
        check normalization before comparing strings.
        Returns: length in code points, graphemes (user-perceived characters), UTF-8 bytes and UTF-16 units;
        NFC/NFD/NFKC/NFKD forms; and per character the code point, name, category, UTF-8 bytes and HTML entity.
        Behavior: computed locally. Cost: $0.001 per successful call."""
        return await _call("/v1/unicode", {"text": text}, "check-tool", body=True)

    @server.tool(title="Convert time between time zones", annotations=local)
    async def convert_timezone(
        from_timezone: Annotated[str, Field(description="Source IANA time zone, e.g. Asia/Seoul")],
        to_timezones: Annotated[str, Field(description="Target IANA time zones, comma-separated (up to 50), e.g. Europe/London,America/New_York")],
        time: Annotated[str | None, Field(description="ISO 8601 time in the source zone, e.g. 2026-10-03T09:00; defaults to now")] = None,
    ) -> dict:
        """Convert one moment from a time zone to others.

        Use this to schedule across time zones. For valid zone names use list_timezones.
        Returns: source and each target with local date-time, weekday, UTC offset, abbreviation and whether
        daylight saving is in effect, plus UTC and Unix time.
        Behavior: computed locally with the IANA database. Cost: $0.001 per successful call."""
        return await _call("/v1/timezone/convert", {"from": from_timezone, "to": to_timezones, "time": time},
                           "check-tool")

    @server.tool(title="List IANA time zones", annotations=local)
    async def list_timezones(region: Annotated[str | None, Field(description="Optional region prefix, e.g. Europe, Asia or America")] = None) -> dict:
        """List valid IANA time zone names.

        Use this to find the exact zone name before calling convert_timezone or parse_cron.
        Returns: count and timezones (sorted names).
        Behavior: computed locally. Cost: $0.001 per successful call."""
        return await _call("/v1/timezone/list", {"region": region}, "check-tool")

    # ── Hyperliquid market data ──
    @server.tool(title="Hyperliquid perpetual markets", annotations=web)
    async def hyperliquid_markets(
        coin: Annotated[str | None, Field(description="One or more coins, comma-separated, e.g. BTC,ETH; omit for all markets")] = None,
        sort: Annotated[str, Field(description="Sort by volume, open_interest, funding, change or coin")] = "volume",
        order: Annotated[str, Field(description="asc or desc")] = "desc",
        limit: Annotated[int, Field(ge=1, le=300, description="Maximum markets to return, 1-300")] = 50,
    ) -> dict:
        """Get current Hyperliquid perpetual futures markets.

        Use this for prices, funding rates or open interest right now. For history use
        hyperliquid_funding_history or hyperliquid_candles.
        Returns: per market mark/oracle/mid price, 24h change, hourly and annualized funding (%), premium,
        open interest (coins and USD), 24h volume and max leverage; not_found lists unknown coins.
        Behavior: reads Hyperliquid's public market data (refreshed every 10 s). Not financial advice.
        Cost: $0.001 per successful call."""
        return await _call("/v1/hyperliquid/markets", {"coin": coin, "sort": sort, "order": order,
                                                       "limit": limit}, "check-tool")

    @server.tool(title="Hyperliquid funding history", annotations=web)
    async def hyperliquid_funding_history(
        coin: Annotated[str, Field(description="Coin symbol, e.g. BTC")],
        hours: Annotated[int, Field(ge=1, le=720, description="How many hours back, 1-720 (30 days)")] = 24,
    ) -> dict:
        """Get the hourly funding rate history of one Hyperliquid perpetual.

        Use this to judge funding trends or carry. For current rates across markets use hyperliquid_markets.
        Returns: hourly funding_rate and premium points, average hourly and annualized rate, cumulative rate.
        Behavior: reads Hyperliquid's public data. Cost: $0.001 per successful call."""
        return await _call("/v1/hyperliquid/funding", {"coin": coin, "hours": hours}, "check-tool")

    @server.tool(title="Hyperliquid candles (OHLCV)", annotations=web)
    async def hyperliquid_candles(
        coin: Annotated[str, Field(description="Coin symbol, e.g. ETH")],
        interval: Annotated[str, Field(description="Candle interval: 1m 3m 5m 15m 30m 1h 2h 4h 8h 12h 1d 3d 1w")] = "1h",
        limit: Annotated[int, Field(ge=1, le=500, description="Number of most recent candles, 1-500")] = 100,
    ) -> dict:
        """Get OHLCV price candles for one Hyperliquid perpetual.

        Use this for charts or technical analysis. For current price and funding use hyperliquid_markets.
        Returns: candles with open_time, close_time, open, high, low, close, volume and trade count.
        Behavior: reads Hyperliquid's public data. Cost: $0.001 per successful call."""
        return await _call("/v1/hyperliquid/candles", {"coin": coin, "interval": interval, "limit": limit},
                           "check-tool")

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
