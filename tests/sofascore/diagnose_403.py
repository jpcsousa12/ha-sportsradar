#!/usr/bin/env python3
"""Work out why SofaScore returns 403 on a particular host.

SofaScore's edge refuses some clients and not others from the same IP - on one
machine plain curl gets 403 while aiohttp gets 200 - so the block is not simply
about the network address. This tries several client configurations against the
same endpoint and reports which, if any, are allowed.

Run it ON the machine that is being refused:

    python tests/sofascore/diagnose_403.py

Send the output back. If every attempt returns 403, the host itself is blocked
and no change to this integration will help. If one of them returns 200, that
configuration can be adopted.
"""

import asyncio
import socket
import ssl
import sys

import aiohttp

PATH = "/api/v1/team/3002/events/last/0"
HOSTS = ("api.sofascore.com", "api.sofascore.app")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.sofascore.com",
    "Referer": "https://www.sofascore.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# Roughly the cipher order a desktop browser offers. Some edge filters
# classify on the TLS handshake, and the cipher list is the part we can
# influence from Python.
BROWSER_CIPHERS = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
    "ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:"
    "AES256-GCM-SHA384:AES128-SHA:AES256-SHA"
)


def _context(ciphers=None, max_version=None, alpn=None):
    ctx = ssl.create_default_context()
    if ciphers:
        try:
            ctx.set_ciphers(ciphers)
        except ssl.SSLError as error:
            print("      (cipher list rejected by this OpenSSL: %s)" % error)
            return None
    if max_version:
        ctx.maximum_version = max_version
    if alpn:
        try:
            ctx.set_alpn_protocols(alpn)
        except NotImplementedError:
            pass
    return ctx


async def attempt(label, host, headers, ssl_context):
    url = "https://%s%s" % (host, PATH)
    timeout = aiohttp.ClientTimeout(total=20)
    connector = aiohttp.TCPConnector(ssl=ssl_context) if ssl_context else None
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, headers=headers, timeout=timeout) as response:
                body = await response.read()
                mark = "OK  " if response.status == 200 else "FAIL"
                print("  %s %-42s %s  (%d bytes)" % (
                    mark, label, response.status, len(body)))
                return response.status == 200
    except Exception as error:  # noqa: BLE001 - diagnostics: report anything
        print("  FAIL %-42s %s: %s" % (label, type(error).__name__, error))
        return False


async def main():
    print("Environment")
    print("  python   %s" % sys.version.split()[0])
    print("  aiohttp  %s" % aiohttp.__version__)
    print("  openssl  %s" % ssl.OPENSSL_VERSION)
    try:
        print("  resolves %s -> %s" % (
            HOSTS[0], socket.gethostbyname(HOSTS[0])))
    except OSError as error:
        print("  resolves %s -> FAILED (%s)" % (HOSTS[0], error))
    print("")

    results = []
    for host in HOSTS:
        print("%s" % host)
        results.append(await attempt(
            "default TLS, browser headers", host, BROWSER_HEADERS, None))
        results.append(await attempt(
            "browser cipher order", host, BROWSER_HEADERS,
            _context(ciphers=BROWSER_CIPHERS)))
        results.append(await attempt(
            "TLS 1.2 max", host, BROWSER_HEADERS,
            _context(max_version=ssl.TLSVersion.TLSv1_2)))
        results.append(await attempt(
            "ALPN http/1.1 only", host, BROWSER_HEADERS,
            _context(alpn=["http/1.1"])))
        results.append(await attempt(
            "no custom headers at all", host, {}, None))
        print("")

    print("-" * 66)
    if any(results):
        print("At least one configuration was allowed - that one can be used.")
    else:
        print("Every configuration was refused from this host.")
        print("That points at the host or its network rather than the client")
        print("configuration, and no change to this integration will fix it.")
    return 0 if any(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
