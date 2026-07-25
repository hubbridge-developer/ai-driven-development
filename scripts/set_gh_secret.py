#!/usr/bin/env python3
"""Set a GitHub Actions secret on this repo, encrypted with its public key.

Usage:  python scripts/set_gh_secret.py NAME VALUE
Reads GITHUB_PAT from ../.env (PAT needs `repo` scope). Requires pynacl.
"""
import sys, base64, json, urllib.request, urllib.error, pathlib
from nacl import encoding, public

if len(sys.argv) != 3:
    sys.exit("usage: set_gh_secret.py NAME VALUE")
name, value = sys.argv[1], sys.argv[2]

OWNER, REPO = "hubbridge-developer", "ai-driven-development"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
env = pathlib.Path(__file__).resolve().parent.parent / ".env"
pat = next(l.strip().split("=", 1)[1] for l in env.read_text().splitlines()
           if l.startswith("GITHUB_PAT="))


def req(method, url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


st, body = req("GET", f"{API}/actions/secrets/public-key")
pk = json.loads(body)
sealed = public.SealedBox(
    public.PublicKey(pk["key"].encode(), encoding.Base64Encoder())
).encrypt(value.encode())
st, _ = req("PUT", f"{API}/actions/secrets/{name}", {
    "encrypted_value": base64.b64encode(sealed).decode(), "key_id": pk["key_id"]})
print(f"{name}: HTTP {st}")
