# Web Content & URL Tools MCP Server

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI agents
**26 tools** for reading and checking the web — no browser, no setup, pay only for successful calls.

Read any page as clean Markdown, pull its metadata or structure, detect its tech stack, and check
redirects, TLS certificates, security headers, robots.txt, sitemaps, feeds, domains (WHOIS/DNS), SEO,
broken links, email authentication (SPF, DMARC, DKIM) and single sign-on (SAML, OpenID Connect).
It also includes everyday developer utilities (cron, regex, color, Unicode, time zones) and
Hyperliquid perpetuals market data.

- **Apify Store:** https://apify.com/avalonai/web-content-url-tools-mcp
- **Developer docs:** https://avaloncompany.ai/developers/
- **Transport:** Streamable HTTP (remote, hosted on Apify Standby)

## Connect

### Option 1 — Standby URL + Apify API token

Use your [Apify API token](https://console.apify.com/settings/integrations) as a Bearer token.
Works in Claude Desktop, Claude Code, Cursor, VS Code, Windsurf and any MCP client that supports
remote servers with headers.

```json
{
  "mcpServers": {
    "web-content-url-tools": {
      "url": "https://avalonai--web-content-url-tools-mcp.apify.actor/mcp",
      "headers": { "Authorization": "Bearer <YOUR_APIFY_TOKEN>" }
    }
  }
}
```

### Option 2 — OAuth via mcp.apify.com (no token to copy)

Clients that support MCP OAuth can connect through Apify's hosted MCP gateway and sign in with
their Apify account in the browser:

```
https://mcp.apify.com?tools=avalonai/web-content-url-tools-mcp
```

Claude Code example:

```bash
claude mcp add --transport http web-content-url-tools "https://mcp.apify.com?tools=avalonai/web-content-url-tools-mcp"
```

## Tools

### Web pages and URLs

| Tool | What it returns | Price per call |
|---|---|---|
| `to_markdown` | Clean, LLM-ready Markdown of the main content (menus, ads and footers removed), word/character counts, language | $0.003 |
| `get_metadata` | Title, description, preview image, site name, canonical URL, favicon, author, publish time, Open Graph / Twitter tags | $0.003 |
| `extract_structure` | Heading outline, internal/external links, images, tables and JSON-LD | $0.003 |
| `detect_technologies` | CMS, framework, e-commerce platform, CDN, analytics and payment tools, with evidence | $0.003 |
| `trace_redirects` | Every redirect hop (HTTP and meta refresh) to the final URL — expands short links | $0.001 |
| `check_ssl` | Certificate issuer, expiry, days remaining, SANs, and whether browsers trust it | $0.001 |
| `grade_security_headers` | A+ to F grade for security headers, information leaks and insecure cookies | $0.001 |
| `parse_robots` | robots.txt rules per user agent, sitemaps, and whether a path may be crawled | $0.001 |
| `parse_sitemap` | URLs from a sitemap or sitemap index (auto-discovered, gzip supported) | $0.001 |
| `read_feed` | RSS, Atom or RDF feed as JSON (auto-discovered from a website URL) | $0.001 |
| `lookup_domain` | WHOIS (RDAP) registrar, dates, domain age, nameservers, DNS records, MX/SPF/DMARC | $0.001 |
| `audit_seo` | On-page SEO score and grade with prioritised issues and fixes | $0.003 |
| `check_broken_links` | Up to 100 links checked: broken, redirected and bot-blocked reported separately | $0.003 |

### Email and identity diagnostics

| Tool | What it returns | Price per call |
|---|---|---|
| `check_email_domain` | MX, SPF (10-lookup limit), DMARC, DKIM, MTA-STS, TLS-RPT and BIMI graded pass/warn/fail with fixes and a 0-100 score | $0.003 |
| `analyze_saml_metadata` | SAML metadata (XML or URL): entity ID, endpoints and bindings, NameID formats, signing certificate expiry and issues | $0.001 |
| `check_oidc_provider` | OpenID Connect discovery and JWKS: issuer match, HTTPS, PKCE S256, ID token algorithms, key sizes, certificate expiry | $0.001 |

### Developer utilities

| Tool | What it returns | Price per call |
|---|---|---|
| `parse_cron` | Validity, plain-English explanation, previous and next run times in any time zone | $0.001 |
| `test_regex` | Every match with positions and groups, plus find-and-replace; runaway patterns stop in 0.1 s | $0.001 |
| `convert_color` | HEX, RGB, HSL, HSV, CMYK, best text color, contrast and palettes | $0.001 |
| `check_color_contrast` | WCAG 2 contrast ratio with AA/AAA pass/fail | $0.001 |
| `inspect_unicode` | Per-character code point, name and bytes; grapheme count; normalization forms | $0.001 |
| `convert_timezone` | One time in many IANA zones with offsets, abbreviations and DST | $0.001 |
| `list_timezones` | IANA time zone names, optionally by region | $0.001 |

### Hyperliquid perpetuals market data

| Tool | What it returns | Price per call |
|---|---|---|
| `hyperliquid_markets` | Mark/oracle price, 24h change, hourly and annualized funding, open interest, volume | $0.001 |
| `hyperliquid_funding_history` | Hourly funding history (up to 30 days) with average and annualized rate | $0.001 |
| `hyperliquid_candles` | OHLCV candles from 1 minute to 1 week | $0.001 |

Hyperliquid data comes from Hyperliquid's public market data. This server is not affiliated with
Hyperliquid, and nothing it returns is financial advice.

## Pricing

Pay per successful tool call through your Apify account: **$0.001** for check and utility tools,
**$0.003** for page tools. Failed calls (invalid URL, blocked site, timeout) are free and return a
clear error reason.

## Good to know

- Pages are read from the HTML the server sends; sites that render everything in the browser return
  little text and say so in a `warning` field.
- Some sites block automated access; those calls return `target_blocked` and are not charged.
- Only public `http`/`https` addresses are fetched; private and internal addresses are refused.

## This repository

This is the source of the Apify Actor that hosts the MCP server. It is a thin connector: each tool
forwards the request to the Web Content API and returns the JSON result.

```
.actor/        Apify Actor definition (Standby mode, MCP path /mcp, pay-per-event pricing)
src/main.py    MCP server (FastMCP, Streamable HTTP) and tool definitions
Dockerfile     Container image
```

You do not need to run it yourself — connect to the hosted endpoint above.

## License

[MIT](LICENSE) © Avalon Company
