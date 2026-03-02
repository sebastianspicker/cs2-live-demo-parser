# Security Policy

## Reporting a Vulnerability
Please use GitHub Security Advisories if available. If advisories are not enabled, open an issue with minimal detail and avoid posting sensitive exploit information or secrets.

## Scope
This project processes demo files and streams data over WebSocket. Treat demo content as untrusted input.

## API key authentication
When using API key authentication (`CS2_REQUIRE_AUTH=1`), prefer the `Authorization: Bearer <key>` header over the `?key=` query parameter so the key is not exposed in server logs, browser history, or Referer headers.
