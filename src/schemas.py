"""도구별 출력 스키마(MCP outputSchema) -- Web Content API 의 실제 응답 필드에 맞춘 모델.

응답은 그대로 통과시킨다(모델로 재구성하지 않는다). 모델은 tools/list 에 실리는 스키마를 만드는 데만 쓴다.
그래서 응답이 스키마와 어긋나면 클라이언트 쪽 검증에서 호출이 깨진다 -- 이를 막으려고
- 모든 필드를 선택(Optional, null 허용)으로 둔다. 실패·예외 경로에서 값이 비거나 키가 빠질 수 있다.
- extra="allow" 로 API 에 필드가 늘어도 통과시킨다(additionalProperties: true).
- 경로마다 모양이 다른 깊은 값은 Any 로 둔다.
필드는 녹화한 실제 응답(tests/samples/*.json)과 대조해 정했다.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="allow")


def F(description: str) -> Any:  # noqa: N802 -- 필드 선언을 짧게 쓰려는 별칭
    return Field(default=None, description=description)


# ── 공통 조각 ──
class Issue(_Out):
    severity: Optional[str] = F("Severity, e.g. high, medium, low or info")
    code: Optional[str] = F("Stable machine-readable issue code")
    message: Optional[str] = F("What is wrong and how to fix it")


class _Fetched(_Out):
    url: Optional[str] = F("Final URL that was fetched (after redirects)")
    status_code: Optional[int] = F("HTTP status code of the page")
    fetch_ms: Optional[int] = F("Time taken to fetch the page, in milliseconds")


# ── Page tools ──
class MarkdownOut(_Fetched):
    title: Optional[str] = F("Page title")
    markdown: Optional[str] = F("Page content as Markdown")
    word_count: Optional[int] = F("Number of words in the Markdown")
    character_count: Optional[int] = F("Number of characters in the Markdown")
    language: Optional[str] = F("Page language code, e.g. en")
    warning: Optional[str] = F("Set when the page likely needs JavaScript to render (little static text)")


class MetadataOut(_Fetched):
    title: Optional[str] = F("Page title (Open Graph title when present)")
    description: Optional[str] = F("Meta or Open Graph description")
    image: Optional[str] = F("Preview image URL")
    site_name: Optional[str] = F("Site name")
    type: Optional[str] = F("Open Graph type, e.g. website or article")
    canonical_url: Optional[str] = F("Canonical URL")
    favicon: Optional[str] = F("Favicon URL")
    language: Optional[str] = F("Page language code")
    author: Optional[str] = F("Author")
    published_time: Optional[str] = F("Publish time as given by the page")
    keywords: Optional[list[str]] = F("Meta keywords")
    twitter_card: Optional[str] = F("Twitter card type")
    theme_color: Optional[str] = F("Theme color")
    json_ld_types: Optional[list[Any]] = F("@type values of JSON-LD objects on the page")


class Heading(_Out):
    level: Optional[int] = F("Heading level 1-6")
    text: Optional[str] = F("Heading text")


class PageLink(_Out):
    url: Optional[str] = F("Absolute link URL")
    text: Optional[str] = F("Link text")
    internal: Optional[bool] = F("True when the link points to the same site")


class PageImage(_Out):
    url: Optional[str] = F("Absolute image URL")
    alt: Optional[str] = F("Alt text (null when missing)")


class StructureOut(_Fetched):
    headings: Optional[list[Heading]] = F("Heading outline in page order")
    links: Optional[list[PageLink]] = F("Links on the page")
    images: Optional[list[PageImage]] = F("Images on the page")
    tables: Optional[list[Any]] = F("Tables, each a list of rows, each row a list of cell texts")
    json_ld: Optional[list[Any]] = F("JSON-LD objects found on the page")
    counts: Optional[dict[str, Any]] = F("Counts of headings, links, images and tables")


class Technology(_Out):
    name: Optional[str] = F("Technology name")
    category: Optional[str] = F("Category, e.g. CMS, CDN or Analytics")
    evidence: Optional[str] = F("What revealed it: header, script or meta tag")


class TechOut(_Fetched):
    technologies: Optional[list[Technology]] = F("Detected technologies")
    by_category: Optional[dict[str, Any]] = F("Technology names grouped by category")
    count: Optional[int] = F("Number of technologies detected")


class SeoOut(_Out):
    url: Optional[str] = F("Audited URL")
    score: Optional[int] = F("SEO score 0-100")
    grade: Optional[str] = F("Letter grade")
    issues: Optional[list[Issue]] = F("Problems to fix, most important first")
    summary: Optional[dict[str, Any]] = F("Measured values: title, description, h1, canonical, word count, images, robots.txt, sitemap and more")


class LinkResult(_Out):
    url: Optional[str] = F("Link URL")
    text: Optional[str] = F("Link text")
    internal: Optional[bool] = F("True when the link points to the same site")
    status: Optional[str] = F("ok, broken, redirected, blocked or not_checked")
    status_code: Optional[int] = F("HTTP status code of the link")
    redirected_to: Optional[str] = F("Final URL when the link redirects")
    error: Optional[str] = F("Error code when the link could not be fetched")


class BrokenLinksOut(_Out):
    url: Optional[str] = F("Page URL")
    links_found: Optional[int] = F("Links found on the page")
    checked: Optional[int] = F("Links actually tested")
    broken_count: Optional[int] = F("Number of broken links")
    broken: Optional[list[LinkResult]] = F("Broken links")
    blocked_count: Optional[int] = F("Links whose site refuses bots (not counted as broken)")
    redirected: Optional[list[LinkResult]] = F("Links that redirect")
    results: Optional[list[LinkResult]] = F("Result for every tested link")
    not_checked: Optional[int] = F("Links skipped because of the limits")


# ── Check tools ──
class RedirectHop(_Out):
    url: Optional[str] = F("URL requested at this hop")
    status_code: Optional[int] = F("HTTP status code")
    location: Optional[str] = F("Where this hop redirects to (null on the final hop)")
    server: Optional[str] = F("Server header")
    elapsed_ms: Optional[int] = F("Time for this hop, in milliseconds")
    type: Optional[str] = F("http or meta-refresh")


class RedirectsOut(_Out):
    input_url: Optional[str] = F("URL given")
    final_url: Optional[str] = F("Final destination URL")
    final_status_code: Optional[int] = F("Status code of the final URL")
    redirect_count: Optional[int] = F("Number of redirects")
    chain: Optional[list[RedirectHop]] = F("Every hop in order")
    redirect_types: Optional[list[Any]] = F("Redirect status codes used, or meta-refresh")
    loop_detected: Optional[bool] = F("True when the chain loops")
    too_many_redirects: Optional[bool] = F("True when the hop limit was reached")
    https_upgrade: Optional[bool] = F("True when http was upgraded to https")
    domain_changed: Optional[bool] = F("True when the final host differs from the input host")
    total_ms: Optional[int] = F("Total time, in milliseconds")


class SslOut(_Out):
    host: Optional[str] = F("Host checked")
    trusted: Optional[bool] = F("True when browsers would trust the certificate")
    verification_error: Optional[str] = F("Why the certificate is not trusted")
    subject_common_name: Optional[str] = F("Subject common name")
    subject_alt_names: Optional[list[str]] = F("Subject alternative names")
    issuer: Optional[str] = F("Issuer")
    valid_from: Optional[str] = F("Start of validity (ISO 8601)")
    valid_to: Optional[str] = F("End of validity (ISO 8601)")
    days_remaining: Optional[int] = F("Days until expiry")
    expired: Optional[bool] = F("True when expired")
    self_signed: Optional[bool] = F("True when self-signed")
    serial_number: Optional[str] = F("Serial number")
    signature_algorithm: Optional[str] = F("Signature algorithm")
    sha256_fingerprint: Optional[str] = F("SHA-256 fingerprint")
    tls_version: Optional[str] = F("Negotiated TLS version")
    cipher: Optional[str] = F("Negotiated cipher")
    handshake_ms: Optional[int] = F("TLS handshake time, in milliseconds")


class HeaderCheck(_Out):
    header: Optional[str] = F("Header name")
    present: Optional[bool] = F("True when the header is sent")
    passed: Optional[bool] = F("True when the value is good")
    value: Optional[str] = F("Header value")
    points: Optional[int] = F("Points earned")
    max_points: Optional[int] = F("Points available")
    why: Optional[str] = F("Why it matters")


class SecurityHeadersOut(_Out):
    url: Optional[str] = F("URL checked")
    https: Optional[bool] = F("True when served over https")
    score: Optional[int] = F("Score 0-100")
    grade: Optional[str] = F("Grade A+ to F")
    checks: Optional[list[HeaderCheck]] = F("Each security header checked")
    missing: Optional[list[str]] = F("Missing headers")
    information_leaks: Optional[dict[str, Any]] = F("Headers revealing software versions")
    cookies: Optional[list[dict[str, Any]]] = F("Cookies with their Secure, HttpOnly and SameSite flags")
    insecure_cookies: Optional[list[str]] = F("Cookies missing a protective flag")


class RobotsGroup(_Out):
    user_agents: Optional[list[str]] = F("User agents this group applies to")
    rules: Optional[list[dict[str, Any]]] = F("Rules: type (allow/disallow) and path")
    crawl_delay: Optional[str] = F("Crawl-delay value")


class RobotsOut(_Out):
    robots_url: Optional[str] = F("robots.txt URL")
    exists: Optional[bool] = F("True when robots.txt exists")
    status_code: Optional[int] = F("HTTP status code of robots.txt")
    groups: Optional[list[RobotsGroup]] = F("Rule groups")
    sitemaps: Optional[list[str]] = F("Sitemap URLs listed")
    path: Optional[str] = F("Path tested")
    user_agent: Optional[str] = F("User agent tested")
    allowed: Optional[bool] = F("Whether the path may be crawled (null when no path given)")


class SitemapUrl(_Out):
    loc: Optional[str] = F("URL")
    lastmod: Optional[str] = F("Last modified")
    changefreq: Optional[str] = F("Change frequency")
    priority: Optional[str] = F("Priority")


class SitemapOut(_Out):
    sitemap_url: Optional[str] = F("Sitemap URL read")
    type: Optional[str] = F("urlset or sitemapindex")
    count: Optional[int] = F("Number of entries")
    urls: Optional[list[SitemapUrl]] = F("Page URLs (urlset)")
    sitemaps: Optional[list[SitemapUrl]] = F("Child sitemaps (sitemapindex)")
    truncated: Optional[bool] = F("True when the list was cut at the limit")


class Whois(_Out):
    lookup_ok: Optional[bool] = F("True when RDAP lookup succeeded")
    reason: Optional[str] = F("Why the lookup failed")
    registered: Optional[bool] = F("True when the domain is registered")
    registrar: Optional[str] = F("Registrar")
    created: Optional[str] = F("Registration date")
    updated: Optional[str] = F("Last update date")
    expires: Optional[str] = F("Expiry date")
    age_days: Optional[int] = F("Domain age in days")
    statuses: Optional[list[str]] = F("Domain status codes")
    nameservers: Optional[list[str]] = F("Nameservers")
    dnssec: Optional[bool] = F("True when DNSSEC is signed")


class DomainOut(_Out):
    input: Optional[str] = F("Input given")
    host: Optional[str] = F("Host name")
    registered_domain: Optional[str] = F("Registrable domain")
    whois: Optional[Whois] = F("Registration data (RDAP)")
    dns: Optional[dict[str, Any]] = F("DNS records by type: A, AAAA, MX, NS, TXT, CNAME, CAA")
    email: Optional[dict[str, Any]] = F("has_mx, SPF and DMARC strings")


class FeedItem(_Out):
    title: Optional[str] = F("Item title")
    link: Optional[str] = F("Item link")
    published: Optional[str] = F("Publish date")
    author: Optional[str] = F("Author")
    summary: Optional[str] = F("Summary text")
    id: Optional[str] = F("Item ID")


class FeedOut(_Out):
    feed_url: Optional[str] = F("Feed URL read")
    type: Optional[str] = F("rss, atom or rdf")
    title: Optional[str] = F("Feed title")
    link: Optional[str] = F("Site link")
    description: Optional[str] = F("Feed description")
    updated: Optional[str] = F("Last updated")
    item_count: Optional[int] = F("Number of items")
    items: Optional[list[FeedItem]] = F("Items, newest first as given by the feed")


# ── Diagnostics ──
class EmailCheck(_Out):
    status: Optional[str] = F("pass, warn, fail or info")
    points: Optional[int] = F("Points earned")
    max_points: Optional[int] = F("Points available")
    issues: Optional[list[str]] = F("Problems found")
    recommendations: Optional[list[str]] = F("Fixes")


class EmailDomainOut(_Out):
    domain: Optional[str] = F("Domain checked")
    organizational_domain: Optional[str] = F("Organizational domain used for DMARC")
    score: Optional[int] = F("Score 0-100")
    grade: Optional[str] = F("Letter grade")
    summary: Optional[dict[str, Any]] = F("Status per check: mx, spf, dmarc, dkim, mta_sts, tls_rpt, bimi")
    counts: Optional[dict[str, Any]] = F("Number of pass, warn, fail and info checks")
    recommendations: Optional[list[dict[str, Any]]] = F("Prioritised fixes: check, severity, recommendation")
    mx: Optional[EmailCheck] = F("MX records and their addresses")
    spf: Optional[EmailCheck] = F("SPF record, policy, DNS lookup count and include tree")
    dmarc: Optional[EmailCheck] = F("DMARC policy, alignment and reporting")
    dkim: Optional[EmailCheck] = F("DKIM selectors found with key type and size")
    mta_sts: Optional[EmailCheck] = F("MTA-STS record and policy")
    tls_rpt: Optional[EmailCheck] = F("TLS-RPT record")
    bimi: Optional[EmailCheck] = F("BIMI record")
    dns_queries: Optional[int] = F("DNS queries made")
    incomplete: Optional[bool] = F("True when some lookups failed and the result may be partial")


class SamlEntity(_Out):
    entity_id: Optional[str] = F("Entity ID")
    kind: Optional[str] = F("IdP, SP or both")
    organization: Optional[Any] = F("Organization details when given")
    roles: Optional[list[dict[str, Any]]] = F("Roles with endpoints, bindings, NameID formats and certificates")


class SamlOut(_Out):
    source: Optional[str] = F("url or xml")
    root: Optional[str] = F("Root element")
    entity_count: Optional[int] = F("Entities in the metadata")
    entities_returned: Optional[int] = F("Entities included in this response")
    valid_until: Optional[str] = F("validUntil attribute")
    valid_until_days: Optional[int] = F("Days until validUntil")
    cache_duration: Optional[str] = F("cacheDuration attribute")
    signature: Optional[dict[str, Any]] = F("Whether the metadata is signed, and how")
    note: Optional[str] = F("Note about what is and is not verified")
    score: Optional[int] = F("Score 0-100")
    grade: Optional[str] = F("Letter grade")
    status: Optional[str] = F("Overall status")
    issues: Optional[list[Issue]] = F("Problems found, most important first")
    entities: Optional[list[SamlEntity]] = F("Entities with their roles")


class OidcOut(_Out):
    issuer: Optional[str] = F("Issuer checked")
    discovery_url: Optional[str] = F("Discovery document URL")
    score: Optional[int] = F("Score 0-100")
    grade: Optional[str] = F("Letter grade")
    status: Optional[str] = F("Overall status")
    issues: Optional[list[Issue]] = F("Problems found, most important first")
    summary: Optional[dict[str, Any]] = F("Issuer match, endpoints, PKCE, algorithms, scopes and more")
    missing_required: Optional[list[str]] = F("Required discovery fields that are missing")
    jwks: Optional[dict[str, Any]] = F("JWKS URL, key count and keys (kid, kty, alg, use, size)")


# ── Developer tools ──
class CronOut(_Out):
    expression: Optional[str] = F("Expression given")
    valid: Optional[bool] = F("True when the expression is valid")
    description: Optional[str] = F("Plain-English explanation")
    timezone: Optional[str] = F("Time zone of the run times")
    fields: Optional[dict[str, Any]] = F("Each field: minute, hour, day_of_month, month, day_of_week")
    next_runs: Optional[list[str]] = F("Upcoming run times (ISO 8601 with offset)")
    previous_run: Optional[str] = F("Most recent past run time")


class RegexMatch(_Out):
    match: Optional[str] = F("Matched text")
    start: Optional[int] = F("Start offset")
    end: Optional[int] = F("End offset")
    groups: Optional[list[Optional[str]]] = F("Capture groups (null when a group did not take part)")
    named_groups: Optional[dict[str, Any]] = F("Named capture groups")


class RegexOut(_Out):
    pattern: Optional[str] = F("Pattern given")
    flags: Optional[str] = F("Flags used")
    valid: Optional[bool] = F("True when the pattern compiles")
    error: Optional[str] = F("Parser error when the pattern is invalid")
    match_count: Optional[int] = F("Number of matches")
    truncated: Optional[bool] = F("True when matches were cut at the limit")
    matches: Optional[list[RegexMatch]] = F("Matches in order")
    group_names: Optional[list[str]] = F("Named group names")
    replaced: Optional[str] = F("Text after replacement (when replacement given)")


class ColorOut(_Out):
    input: Optional[str] = F("Color given")
    hex: Optional[str] = F("Hex value, e.g. #ff6347")
    rgb: Optional[dict[str, Any]] = F("r, g, b")
    hsl: Optional[dict[str, Any]] = F("h, s, l")
    hsv: Optional[dict[str, Any]] = F("h, s, v")
    cmyk: Optional[dict[str, Any]] = F("c, m, y, k")
    css: Optional[dict[str, Any]] = F("CSS rgb() and hsl() strings")
    luminance: Optional[float] = F("Relative luminance 0-1")
    is_dark: Optional[bool] = F("True when the color is dark")
    contrast: Optional[dict[str, Any]] = F("Contrast vs white and black, and the best text color")
    nearest_css_name: Optional[str] = F("Nearest CSS color name")
    palettes: Optional[dict[str, Any]] = F("Complementary, analogous, triadic, tetradic, split-complementary and shades")


class ContrastOut(_Out):
    foreground: Optional[str] = F("Foreground hex")
    background: Optional[str] = F("Background hex")
    ratio: Optional[float] = F("Contrast ratio, 1-21")
    wcag: Optional[dict[str, Any]] = F("Pass/fail for AA and AAA normal and large text, and UI components")


class UnicodeChar(_Out):
    char: Optional[str] = F("The character")
    codepoint: Optional[str] = F("Code point, e.g. U+00E9")
    decimal: Optional[int] = F("Code point as a number")
    name: Optional[str] = F("Unicode name")
    category: Optional[str] = F("General category")
    utf8: Optional[str] = F("UTF-8 bytes in hex")
    html_entity: Optional[str] = F("HTML entity")
    combining: Optional[bool] = F("True for combining marks")


class UnicodeOut(_Out):
    text: Optional[str] = F("Text given")
    length: Optional[dict[str, Any]] = F("Code points, graphemes, UTF-8 bytes and UTF-16 units")
    normalization: Optional[dict[str, Any]] = F("NFC, NFD, NFKC and NFKD forms and whether the text is already in each")
    characters: Optional[list[UnicodeChar]] = F("Per-character details")
    truncated: Optional[bool] = F("True when the character list was cut at the limit")


class ZoneTime(_Out):
    timezone: Optional[str] = F("IANA time zone")
    datetime: Optional[str] = F("Local date-time (ISO 8601 with offset)")
    date: Optional[str] = F("Local date")
    time: Optional[str] = F("Local time")
    weekday: Optional[str] = F("Weekday")
    utc_offset: Optional[str] = F("UTC offset, e.g. +09:00")
    abbreviation: Optional[str] = F("Zone abbreviation, e.g. KST")
    dst: Optional[bool] = F("True when daylight saving is in effect")


class TimezoneConvertOut(_Out):
    source: Optional[ZoneTime] = F("The moment in the source zone")
    utc: Optional[str] = F("The moment in UTC")
    unix: Optional[int] = F("Unix time in seconds")
    conversions: Optional[list[ZoneTime]] = F("The moment in each target zone")


class TimezoneListOut(_Out):
    count: Optional[int] = F("Number of zones")
    timezones: Optional[list[str]] = F("Sorted IANA zone names")


# ── Hyperliquid ──
class Market(_Out):
    coin: Optional[str] = F("Coin symbol")
    mark_price: Optional[float] = F("Mark price")
    oracle_price: Optional[float] = F("Oracle price")
    mid_price: Optional[float] = F("Mid price")
    prev_day_price: Optional[float] = F("Price 24h ago")
    change_24h_pct: Optional[float] = F("24h change, %")
    funding_rate_hourly: Optional[float] = F("Current hourly funding rate")
    funding_rate_annualized_pct: Optional[float] = F("Funding annualized, %")
    premium: Optional[float] = F("Premium")
    open_interest: Optional[float] = F("Open interest in coins")
    open_interest_usd: Optional[float] = F("Open interest in USD")
    volume_24h_usd: Optional[float] = F("24h volume in USD")
    max_leverage: Optional[int] = F("Maximum leverage")
    size_decimals: Optional[int] = F("Size decimals")
    delisted: Optional[bool] = F("True when delisted")


class MarketsOut(_Out):
    venue: Optional[str] = F("Always hyperliquid")
    count: Optional[int] = F("Markets returned")
    total_markets: Optional[int] = F("Markets matching before the limit")
    timestamp: Optional[int] = F("Data time, Unix milliseconds")
    not_found: Optional[list[str]] = F("Requested coins that do not exist")
    markets: Optional[list[Market]] = F("Markets")


class FundingPoint(_Out):
    time: Optional[int] = F("Unix milliseconds")
    funding_rate: Optional[float] = F("Hourly funding rate")
    premium: Optional[float] = F("Premium")


class FundingOut(_Out):
    venue: Optional[str] = F("Always hyperliquid")
    coin: Optional[str] = F("Coin symbol")
    hours: Optional[int] = F("Hours requested")
    count: Optional[int] = F("Points returned")
    average_hourly_rate: Optional[float] = F("Average hourly funding rate")
    average_annualized_pct: Optional[float] = F("Average annualized, %")
    cumulative_rate: Optional[float] = F("Sum of hourly rates over the period")
    history: Optional[list[FundingPoint]] = F("Hourly points, oldest first")


class Candle(_Out):
    open_time: Optional[int] = F("Open time, Unix milliseconds")
    close_time: Optional[int] = F("Close time, Unix milliseconds")
    open: Optional[float] = F("Open price")
    high: Optional[float] = F("High price")
    low: Optional[float] = F("Low price")
    close: Optional[float] = F("Close price")
    volume: Optional[float] = F("Volume in coins")
    trades: Optional[int] = F("Number of trades")


class CandlesOut(_Out):
    venue: Optional[str] = F("Always hyperliquid")
    coin: Optional[str] = F("Coin symbol")
    interval: Optional[str] = F("Candle interval")
    count: Optional[int] = F("Candles returned")
    candles: Optional[list[Candle]] = F("Candles, oldest first")


#: 도구 이름 → 출력 모델. main.py 와 테스트가 같은 표를 쓴다.
OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "to_markdown": MarkdownOut,
    "get_metadata": MetadataOut,
    "extract_structure": StructureOut,
    "detect_technologies": TechOut,
    "audit_seo": SeoOut,
    "check_broken_links": BrokenLinksOut,
    "trace_redirects": RedirectsOut,
    "check_ssl": SslOut,
    "grade_security_headers": SecurityHeadersOut,
    "parse_robots": RobotsOut,
    "parse_sitemap": SitemapOut,
    "lookup_domain": DomainOut,
    "read_feed": FeedOut,
    "check_email_domain": EmailDomainOut,
    "analyze_saml_metadata": SamlOut,
    "check_oidc_provider": OidcOut,
    "parse_cron": CronOut,
    "test_regex": RegexOut,
    "convert_color": ColorOut,
    "check_color_contrast": ContrastOut,
    "inspect_unicode": UnicodeOut,
    "convert_timezone": TimezoneConvertOut,
    "list_timezones": TimezoneListOut,
    "hyperliquid_markets": MarketsOut,
    "hyperliquid_funding_history": FundingOut,
    "hyperliquid_candles": CandlesOut,
}
