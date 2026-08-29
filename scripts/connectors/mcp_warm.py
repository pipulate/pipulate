#!/usr/bin/env python3
# scripts/connectors/mcp_warm.py
"""
mcp_warm.py — Mint an OAuth 2.1 (PKCE, S256) bearer token for a remote MCP
server and park it where scripts/connectors/mcp.py already looks.

THE PLUG FOR THE ALREADY-WIRED SOCKET: resolve_token() in mcp.py reads
~/.config/pipulate/mcp_botify_token.json before falling back to
BOTIFY_API_TOKEN. The 2026-07-29 flight-one FDR receipt proved that fallback
is the wrong KIND of credential for mcp.botify.com (HTTP 401 at initialize;
the server wants a bearer scoped mcp_read_write, per its RFC 9728 document).
This warmer is the one-shot browser dance that writes the right kind.
No new dependencies: httpx (declared) plus stdlib.

Golden path:

  python scripts/connectors/mcp_warm.py                      # https://mcp.botify.com/
  python scripts/connectors/mcp_warm.py https://mcp.example.com/

Interactive-only BY DESIGN: it opens a browser and blocks on the redirect,
so a `!` chisel-strike must never reach it. Non-TTY runs die at gate0.

Named gates (every discovery inference dies LOUD; nothing falls back silently):

  gate0  a real TTY
  gate1  RFC 9728  <resource>/.well-known/oauth-protected-resource
  gate2  RFC 8414  <as>/.well-known/oauth-authorization-server
         (fallback tried: OIDC /.well-known/openid-configuration)
  gate3  client_id: $MCP_OAUTH_CLIENT_ID if set; else RFC 7591 dynamic
         registration IFF registration_endpoint is advertised; else die
         naming the env var to export
  gate4  browser authorize + loopback catch on 127.0.0.1 (state checked,
         S256 PKCE, RFC 8707 resource indicator)
  gate5  token exchange -> write token file 0600

The token VALUE never prints. The receipt names the file, scope, and expiry.
"""

import os
import sys
import json
import time
import base64
import hashlib
import secrets
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs, quote

import httpx

DEFAULT_RESOURCE = "https://mcp.botify.com/"
DEFAULT_OUT = Path.home() / ".config" / "pipulate" / "mcp_botify_token.json"
AUTH_TIMEOUT = 300  # seconds to wait for the browser redirect


def die(msg, code=1):
    sys.stderr.write(msg.rstrip("\n") + "\n")
    sys.exit(code)


def fetch_json(client, url, gate):
    try:
        resp = client.get(url)
    except httpx.HTTPError as e:
        die(f"mcp_warm RED {gate}: transport failure at {url}: {e}")
    if resp.status_code != 200:
        die(f"mcp_warm RED {gate}: {url} -> HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError:
        die(f"mcp_warm RED {gate}: {url} returned non-JSON")


def discover(client, resource):
    """RFC 9728 then RFC 8414 (OIDC fallback). Returns (as_metadata, scopes)."""
    pr_url = resource.rstrip("/") + "/.well-known/oauth-protected-resource"
    pr = fetch_json(client, pr_url, "gate1")
    servers = pr.get("authorization_servers") or []
    if not servers:
        die(f"mcp_warm RED gate1: {pr_url} names no authorization_servers")
    as_base = servers[0].rstrip("/")
    scopes = pr.get("scopes_supported") or []
    for path, label in (
        ("/.well-known/oauth-authorization-server", "RFC 8414"),
        ("/.well-known/openid-configuration", "OIDC discovery"),
    ):
        url = as_base + path
        try:
            resp = client.get(url)
        except httpx.HTTPError as e:
            die(f"mcp_warm RED gate2: transport failure at {url}: {e}")
        if resp.status_code != 200:
            continue
        try:
            meta = resp.json()
        except ValueError:
            continue
        if meta.get("authorization_endpoint") and meta.get("token_endpoint"):
            print(f"# gate2 GREEN via {label}: {url}")
            return meta, scopes
    die(f"mcp_warm RED gate2: no usable AS metadata under {as_base} "
        "(tried RFC 8414 and OIDC paths). The resource names an "
        "authorization server that publishes no discovery document this "
        "client can read. Next-cheapest probe: fetch both URLs by hand and "
        "read the bodies before changing any code.")


def obtain_client_id(client, meta, redirect_uri):
    env_id = os.environ.get("MCP_OAUTH_CLIENT_ID")
    if env_id:
        print("# gate3 GREEN: client_id from $MCP_OAUTH_CLIENT_ID")
        return env_id
    reg = meta.get("registration_endpoint")
    if not reg:
        die("mcp_warm RED gate3: no $MCP_OAUTH_CLIENT_ID set and the AS "
            "advertises no registration_endpoint (RFC 7591). Obtain a "
            "public-client id registered for redirect URI "
            f"{redirect_uri} and export MCP_OAUTH_CLIENT_ID.")
    try:
        resp = client.post(reg, json={
            "client_name": "pipulate-mcp-warm",
            "redirect_uris": [redirect_uri],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        })
    except httpx.HTTPError as e:
        die(f"mcp_warm RED gate3: registration transport failure: {e}")
    if resp.status_code not in (200, 201):
        die(f"mcp_warm RED gate3: dynamic registration -> HTTP "
            f"{resp.status_code}\n{resp.text[:300]}")
    try:
        body = resp.json()
    except ValueError:
        die("mcp_warm RED gate3: registration response is not JSON")
    cid = body.get("client_id")
    if not cid:
        die("mcp_warm RED gate3: registration response carries no client_id")
    print("# gate3 GREEN: client_id minted via RFC 7591 dynamic registration")
    return cid


class _Catch(BaseHTTPRequestHandler):
    """One-shot loopback catcher. Ignores favicon and other stray GETs:
    only a query carrying code or error counts as the redirect."""
    result = None

    def do_GET(self):
        q = {k: v[0] for k, v in
             parse_qs(urlparse(self.path).query).items()}
        if "code" not in q and "error" not in q:
            self.send_response(404)
            self.end_headers()
            return
        _Catch.result = q
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Pipulate: authorization received."
                         b" You can close this tab.</h1>")

    def log_message(self, *args):
        pass


def refresh(out_path):
    """THE CINDERELLA RUNG, WRITE HALF. Spend the stored refresh_token for a
    fresh access_token without opening a browser.

    ONE CAR, NOT TWO: discover() above already performs gate1 (RFC 9728) and
    gate2 (RFC 8414 / OIDC fallback) and hands back the AS metadata carrying
    token_endpoint. This path adds a GRANT TYPE, not a mechanism -- which is
    precisely why the discovery round-trip does not split it in half.

    UNWITNESSED UNTIL GREEN: no refresh has ever been POSTed to this vendor.
    Public-client refusal, single-use rotation, and refresh_token expiry are
    all live possibilities. Every one of them dies LOUD at gate6 rather than
    leaving a half-written token file behind.

    No TTY required and none requested -- there is no browser in this path.
    """
    out = Path(os.path.expanduser(out_path))
    if not out.is_file():
        die(f"mcp_warm RED gate6: no token file at {out} -- run the full "
            "browser warm first; there is nothing to refresh.")
    try:
        record = json.loads(out.read_text(encoding="utf-8"))
    except ValueError:
        die(f"mcp_warm RED gate6: {out} is not JSON")
    refresh_token = record.get("refresh_token")
    if not refresh_token:
        die("mcp_warm RED gate6: token file carries no refresh_token. Rung 4 "
            "is UNREACHABLE for this credential -- re-run the full browser "
            "warm and check whether the vendor issues one at all.")
    client_id = record.get("client_id")
    if not client_id:
        die("mcp_warm RED gate6: token file carries no client_id")
    resource = record.get("resource") or DEFAULT_RESOURCE

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        meta, scopes = discover(client, resource)
        try:
            resp = client.post(meta["token_endpoint"], data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "resource": resource,
            })
        except httpx.HTTPError as e:
            die(f"mcp_warm RED gate6: refresh transport failure: {e}")
    if resp.status_code != 200:
        die(f"mcp_warm RED gate6: token endpoint -> HTTP {resp.status_code}\n"
            f"{resp.text[:300]}")
    try:
        tok = resp.json()
    except ValueError:
        die("mcp_warm RED gate6: refresh response is not JSON")
    if not tok.get("access_token"):
        die("mcp_warm RED gate6: refresh response carries no access_token")

    record["obtained_at"] = datetime.now(timezone.utc).isoformat()
    record["access_token"] = tok["access_token"]
    record["expires_in"] = tok.get("expires_in", record.get("expires_in"))
    record["token_type"] = tok.get("token_type", record.get("token_type"))
    record["scope"] = tok.get("scope") or record.get("scope") or " ".join(scopes)
    # ROTATION-SAFE: keep the existing refresh_token unless the AS hands back
    # a new one. An AS that rotates on every use supplies one; an AS that does
    # not must never have its only refresh credential overwritten with None.
    if tok.get("refresh_token"):
        record["refresh_token"] = tok["refresh_token"]

    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.chmod(out, 0o600)

    print(f"# gate6 GREEN: refreshed in place -> {out} (0600)")
    print(f"#   scope: {record.get('scope') or '(none reported)'} | "
          f"expires_in: {record.get('expires_in')}")
    print("# Next: python scripts/connectors/mcp.py "
          f"{resource.rstrip('/')} --check")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="One-shot OAuth 2.1 PKCE warmer for remote MCP servers.")
    parser.add_argument("resource", nargs="?", default=DEFAULT_RESOURCE,
                        help=f"MCP server URL (default: {DEFAULT_RESOURCE})")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help=f"Token file to write (default: {DEFAULT_OUT})")
    parser.add_argument("--refresh", action="store_true",
                        help="Spend the stored refresh_token instead of "
                             "opening a browser. No TTY required.")
    args = parser.parse_args()

    # Branch ABOVE gate0: the refresh path opens no browser and blocks on
    # nothing, so the TTY requirement that guards the interactive dance must
    # not be inherited by a flow that has no interaction in it.
    if args.refresh:
        sys.exit(refresh(args.out))

    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        die("mcp_warm RED gate0: not a TTY. This opens a browser and blocks "
            "on the redirect; run it in a real terminal, never as a `!` probe.")

    resource = args.resource
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        meta, scopes = discover(client, resource)

        # Bind the loopback catcher FIRST so registration (and the authorize
        # request) carry the real port. MCP_OAUTH_REDIRECT_PORT pins a fixed
        # port for pre-registered clients; the DCR path takes an ephemeral one.
        port_env = os.environ.get("MCP_OAUTH_REDIRECT_PORT")
        server = HTTPServer(("127.0.0.1", int(port_env) if port_env else 0),
                            _Catch)
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        client_id = obtain_client_id(client, meta, redirect_uri)

        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(16)
        scope = os.environ.get("MCP_OAUTH_SCOPE") or " ".join(scopes)

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,  # RFC 8707; required by the MCP auth spec
        }
        if scope:
            params["scope"] = scope
        auth_url = meta["authorization_endpoint"] + "?" + urlencode(params)

        print(f"# gate4: opening browser (redirect catch on {redirect_uri})")
        print("#        if no browser appears, open this URL yourself:")
        print(auth_url)
        webbrowser.open(auth_url)

        server.timeout = 1
        deadline = time.monotonic() + AUTH_TIMEOUT
        while _Catch.result is None and time.monotonic() < deadline:
            server.handle_request()
        server.server_close()

        got = _Catch.result
        if not got:
            die(f"mcp_warm RED gate4: no redirect within {AUTH_TIMEOUT}s")
        if got.get("error"):
            die(f"mcp_warm RED gate4: authorization error: "
                f"{got.get('error')} {got.get('error_description', '')}")
        if got.get("state") != state:
            die("mcp_warm RED gate4: state mismatch -- refusing the code")
        code = got.get("code")
        if not code:
            die("mcp_warm RED gate4: redirect carried no code")

        try:
            resp = client.post(meta["token_endpoint"], data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": resource,
            })
        except httpx.HTTPError as e:
            die(f"mcp_warm RED gate5: token exchange transport failure: {e}")
        if resp.status_code != 200:
            die(f"mcp_warm RED gate5: token endpoint -> HTTP "
                f"{resp.status_code}\n{resp.text[:300]}")
        try:
            tok = resp.json()
        except ValueError:
            die("mcp_warm RED gate5: token response is not JSON")
        if not tok.get("access_token"):
            die("mcp_warm RED gate5: token response carries no access_token")

    out = Path(os.path.expanduser(args.out))
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        out.touch(mode=0o600)
    os.chmod(out, 0o600)
    record = {
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "resource": resource,
        "authorization_server": meta.get("issuer") or "",
        "client_id": client_id,
        "token_type": tok.get("token_type"),
        "scope": tok.get("scope") or scope,
        "expires_in": tok.get("expires_in"),
        "access_token": tok["access_token"],
    }
    if tok.get("refresh_token"):
        record["refresh_token"] = tok["refresh_token"]
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"# gate5 GREEN: token written to {out} (0600)")
    print(f"#   scope: {record['scope'] or '(none reported)'} | "
          f"expires_in: {record['expires_in']}")
    print("# Next: python scripts/connectors/mcp.py "
          f"{resource.rstrip('/')} --check")


if __name__ == "__main__":
    main()
