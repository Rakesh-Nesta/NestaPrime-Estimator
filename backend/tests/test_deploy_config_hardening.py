"""Amendment 58 (Section 61): web-server hardening -- the parts that live in the repository.

Text checks on deploy/nginx/nestaprime.conf (there is no nginx in CI): they pin the Content-Security-Policy,
the throttles, the closed docs pages and the per-route upload limits so a later edit cannot silently drop
one. `sudo nginx -t` on the server, and the from-outside checks after each deploy, remain the real gate."""

import re

from tests.test_deploy_config import FINAL, _servers, _uncommented


def _https_block() -> str:
    return next(b for b in _servers(_uncommented(FINAL)) if re.search(r"listen\s+443\s+ssl", b))


def test_the_https_server_sends_a_content_security_policy_that_allows_only_this_site():
    https = _https_block()
    csp = re.search(r'add_header Content-Security-Policy "([^"]+)" always;', https).group(1)
    directives = {d.split()[0]: d.split()[1:] for d in (x.strip() for x in csp.split(";")) if d}
    assert directives["default-src"] == ["'self'"]
    assert directives["script-src"] == ["'self'"]  # no inline or eval scripts, no other hosts
    assert directives["connect-src"] == ["'self'"]  # the API is same-origin (/api)
    assert directives["object-src"] == ["'none'"] and directives["frame-ancestors"] == ["'none'"]
    assert directives["base-uri"] == ["'self'"] and directives["form-action"] == ["'self'"]
    assert set(directives["style-src"]) == {"'self'", "'unsafe-inline'", "https://fonts.googleapis.com"}
    assert set(directives["font-src"]) == {"'self'", "https://fonts.gstatic.com"}
    assert "camera=()" in re.search(r'add_header Permissions-Policy "([^"]+)" always;', https).group(1)
    assert "server_tokens off;" in https  # the nginx version is not announced


def test_the_api_is_throttled_and_the_signin_more_tightly():
    conf = _uncommented(FINAL)
    assert re.search(r"limit_req_zone \$nestaprime_login_key\s+zone=nestaprime_login:\w+ rate=10r/m;", conf)
    assert re.search(r"limit_req_zone \$binary_remote_addr\s+zone=nestaprime_api:\w+\s+rate=20r/s;", conf)
    assert "limit_req_status 429;" in conf
    assert re.search(r"/api/auth/login\s+\$binary_remote_addr;", conf)  # only the sign-in path is keyed
    api_block = _https_block().split("location /api/ {", 1)[1].split("proxy_pass", 1)[0]
    assert "limit_req zone=nestaprime_login" in api_block and "limit_req zone=nestaprime_api" in api_block


def test_the_api_docs_pages_are_closed_but_the_schema_is_not():
    https = _https_block()
    assert re.search(r"location ~ \^/api/\(docs\|redoc\)\(/\|\$\) \{\s*return 404;", https)
    assert "openapi" not in https  # /api/openapi.json is deliberately still proxied (spec, decision 2)


def test_the_upload_routes_have_their_own_limits_and_the_client_cannot_choose_its_address():
    https = _https_block()
    assert "client_max_body_size 2M;" in https  # everything else
    for path, limit in (
        ("/api/attachments", "100M"),
        ("= /api/company/logo", "6M"),
        ("= /api/rate-items/import", "10M"),
        ("= /api/settings/import", "10M"),
    ):
        assert re.search(rf"location {re.escape(path)} \{{\s*client_max_body_size {limit};", https), path
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in https
    assert "$proxy_add_x_forwarded_for" not in https  # a client-sent X-Forwarded-For is never passed on
