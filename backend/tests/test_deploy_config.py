"""Amendment 55 (Section 59): HTTPS on a real domain -- the parts that live in the repository.

There is no nginx in CI, so these are text checks, not a syntax check: they pin the directives that
matter so a later edit cannot silently drop the redirect, a security header, the proxy header the
backend needs, or the upload limit. `sudo nginx -t` on the server remains the real gate."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FINAL = (REPO / "deploy" / "nginx" / "nestaprime.conf").read_text(encoding="utf-8")
BOOTSTRAP = (REPO / "deploy" / "nginx" / "nestaprime-bootstrap.conf").read_text(encoding="utf-8")
DOCKERFILE = (REPO / "Dockerfile").read_text(encoding="utf-8")
README = (REPO / "deploy" / "README.md").read_text(encoding="utf-8")
SERVER_IP = "65.1.234.78"


def _servers(conf: str) -> list[str]:
    """The text of each top-level `server { ... }` block (the config has no nested braces beyond
    `location`, so brace counting is enough)."""
    blocks, depth, start = [], 0, None
    for i, ch in enumerate(conf):
        if ch == "{":
            if depth == 0 and conf[:i].rstrip().endswith("server"):
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocks.append(conf[start : i + 1])
                start = None
    return blocks


def _uncommented(conf: str) -> str:
    return "\n".join(line for line in conf.splitlines() if not line.strip().startswith("#"))


def test_the_final_config_uses_a_domain_placeholder_never_a_real_name():
    assert "__DOMAIN__" in FINAL and "__DOMAIN__" in BOOTSTRAP
    # the install line in each file's header comment shows the sed replacement
    assert 'sed "s/__DOMAIN__/' in FINAL and 'sed "s/__DOMAIN__/' in BOOTSTRAP


def test_plain_http_only_redirects_and_answers_the_acme_challenge():
    conf = _uncommented(FINAL)
    http_blocks = [b for b in _servers(conf) if re.search(r"listen\s+80\b", b)]
    assert len(http_blocks) == 2  # the domain, and the bare IP
    for block in http_blocks:
        assert "proxy_pass" not in block and "root /var/www/nestaprime" not in block  # no app over HTTP
    domain_block = next(b for b in http_blocks if "server_name __DOMAIN__" in b)
    assert "location /.well-known/acme-challenge/" in domain_block  # renewal keeps working
    assert "return 301 https://$host$request_uri;" in domain_block
    ip_block = next(b for b in http_blocks if f"server_name {SERVER_IP}" in b)
    assert "return 301 https://__DOMAIN__$request_uri;" in ip_block  # old bookmarks move to the domain
    assert "default_server" in ip_block


def test_the_https_server_has_tls_the_headers_and_the_proxy_settings():
    conf = _uncommented(FINAL)
    https = next(b for b in _servers(conf) if re.search(r"listen\s+443\s+ssl", b))
    assert "ssl_certificate     /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;" in https
    assert "ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;" in https
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in https  # nothing older
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Strict-Transport-Security"):
        assert re.search(rf'add_header {header} "[^"]+" always;', https), header
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in https  # the backend must learn it was HTTPS
    assert "proxy_pass http://127.0.0.1:8000/;" in https
    assert "client_max_body_size 100M;" in https  # the upload limit found live on 12 Sep 2026
    assert "try_files $uri $uri/ /index.html;" in https  # SPA fallback


def test_hsts_is_staged_and_commits_to_no_more_than_this_host():
    hsts = re.search(r'add_header Strict-Transport-Security "([^"]+)" always;', _uncommented(FINAL)).group(1)
    max_age = int(re.search(r"max-age=(\d+)", hsts).group(1))
    assert max_age in (300, 15552000)  # five minutes first; 180 days after a clean week -- nothing in between
    assert "includeSubDomains" not in hsts and "preload" not in hsts


def test_the_bootstrap_config_keeps_the_app_on_http_and_never_redirects():
    conf = _uncommented(BOOTSTRAP)
    assert "return 301" not in conf and "listen 443" not in conf
    assert "location /.well-known/acme-challenge/" in conf  # certbot's challenge needs this
    assert "proxy_pass http://127.0.0.1:8000/;" in conf and "try_files $uri $uri/ /index.html;" in conf
    assert f"server_name __DOMAIN__ {SERVER_IP};" in conf  # certbot reaches it by the domain; users still by IP
    assert "client_max_body_size 100M;" in conf


def test_gunicorn_trusts_the_proxys_forwarded_headers():
    cmd = next(line for line in DOCKERFILE.splitlines() if line.startswith("CMD"))
    assert "--forwarded-allow-ips='*'" in cmd
    assert "exec gunicorn app.main:app" in cmd and "uvicorn_worker.UvicornWorker" in cmd


def test_the_readme_describes_the_https_address_and_no_http_build_or_cors_line():
    assert "## Cutover to HTTPS" in README
    assert "CORS_ORIGINS=https://your.domain.example" in README
    assert "VITE_API_URL=https://your.domain.example/api" in README
    # the only remaining mentions of the plain-HTTP API address are the rollback instructions
    for match in re.finditer(r"VITE_API_URL=http://" + re.escape(SERVER_IP), README):
        window = README[max(0, match.start() - 400) : match.start()]
        assert "Rollback" in window or "rebuild the frontend with" in window
    assert "nestaprime.pre-https" in README  # the way back is kept before anything changes
