#!/usr/bin/env python3
"""Verify login and persistent identity without printing passwords or tokens."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path('/opt/sub2api')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--proxy', action='store_true')
    parser.add_argument('--record', type=Path)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Run with sudo')
    base = args.url.rstrip('/')
    if base not in ('http://127.0.0.1:8080', 'https://h6k.top'):
        raise ValueError('Unexpected verification target')
    env = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(path, payload=None, token=None):
        headers = {'Accept': 'application/json'}
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode()
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            with opener.open(req, timeout=30) as response:
                return response.status, response.read(), response.headers.get_content_type()
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers.get_content_type()

    def api(path, payload=None, token=None):
        status, body, _ = request(path, payload, token)
        if status != 200:
            raise ValueError('HTTP failure at ' + path)
        value = json.loads(body)
        if value.get('code') != 0:
            raise ValueError('API failure at ' + path)
        return value['data']

    status, body, _ = request('/health')
    if status != 200 or json.loads(body).get('status') != 'ok':
        raise ValueError('Health failed')
    if api('/setup/status').get('needs_setup') is not False:
        raise ValueError('Unexpected setup state')
    login = api('/api/v1/auth/login', {'email': 'admin@h6k.top', 'password': env['ADMIN_PASSWORD']})
    token = login['access_token']
    user = api('/api/v1/auth/me', token=token)
    if user.get('role') != 'admin' or user.get('email') != 'admin@h6k.top':
        raise ValueError('Unexpected administrator identity')
    api('/api/v1/admin/compliance', token=token)
    print('PASS health, setup locked, administrator login and admin permission')

    status, page, content_type = request('/')
    if status != 200 or content_type != 'text/html' or b'<html' not in page.lower():
        raise ValueError('Frontend page missing')
    scripts = re.findall(rb'<script[^>]+src="([^"]+)"', page)
    if not scripts:
        raise ValueError('Frontend JavaScript entry missing')
    script_path = scripts[0].decode()
    if not script_path.startswith('/') or script_path.startswith('//'):
        raise ValueError('Unexpected frontend asset origin')
    asset_status, asset, content_type = request(script_path)
    if (asset_status != 200 or content_type not in ('text/javascript', 'application/javascript')
            or len(asset) < 100 or b'<html' in asset[:256].lower()):
        raise ValueError('Frontend JavaScript failed')
    print('PASS frontend HTML and JavaScript asset')

    if args.proxy:
        for route in ('update', 'rollback'):
            for suffix in ('', '/'):
                status, _, _ = request('/api/v1/admin/system/' + route + suffix, {})
                if status != 403:
                    raise ValueError('In-place update guard failed')
        status, _, _ = request('/api/v1/admin/system/check-updates')
        if status != 401:
            raise ValueError('Version checking route was not forwarded')
        print('PASS Nginx update/rollback guards; version check reaches app authentication')

    snapshot = {
        'admin_id': user['id'],
        'config_sha256': hashlib.sha256((ROOT / 'data/config.yaml').read_bytes()).hexdigest(),
        'env_sha256': hashlib.sha256((ROOT / '.env').read_bytes()).hexdigest(),
        'installed': (ROOT / 'data/.installed').is_file(),
    }
    if not snapshot['installed']:
        raise ValueError('Installation lock missing')
    if args.record:
        fd = os.open(args.record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(snapshot, stream)
        print('PASS persistence baseline recorded without credentials')
    if args.compare:
        if snapshot != json.loads(args.compare.read_text()):
            raise ValueError('Persistent identity/config/keys changed')
        print('PASS same administrator, config, installation lock and fixed keys after restart')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Avoid printing API responses, tokens, passwords, or redirect headers.
        print('FAIL verification: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
