#!/usr/bin/env python3
"""First production initialization; credentials stay in a root-only server file."""
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

ROOT = Path('/opt/sub2api')


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo')
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    env_file = ROOT / '.env'
    if env_file.exists():
        raise SystemExit('Existing .env preserved; initialization refused')
    for directory in ('data', 'postgres', 'redis'):
        path = ROOT / directory
        if path.exists() and any(path.iterdir()):
            raise SystemExit('Existing persistent data preserved; initialization refused')
        path.mkdir(mode=0o700, exist_ok=True)
    existing = docker('network', 'ls', '--filter', 'name=^sub2api-prod-backend$', '--format', '{{.Name}}').strip()
    if not existing:
        docker('network', 'create', 'sub2api-prod-backend')
    network = json.loads(docker('network', 'inspect', 'sub2api-prod-backend'))[0]
    gateway = str(ipaddress.IPv4Address(network['IPAM']['Config'][0]['Gateway'])) + '/32'
    images = {}
    for name, tag in [('POSTGRES_IMAGE', 'postgres:18-alpine'), ('REDIS_IMAGE', 'redis:8-alpine')]:
        subprocess.run(['docker', 'pull', tag], check=True)
        image = json.loads(docker('image', 'inspect', tag))[0]
        digest = image['RepoDigests'][0]
        if not re.fullmatch(r'(?:docker.io/library/)?(?:postgres|redis)@sha256:[0-9a-f]{64}', digest):
            raise SystemExit('Unexpected official image digest')
        images[name] = digest
    # PG18 drops to postgres at runtime; it must be able to traverse the bind parent.
    postgres_uid = int(docker('run', '--rm', '--entrypoint', 'id', images['POSTGRES_IMAGE'], '-u', 'postgres').strip())
    postgres_gid = int(docker('run', '--rm', '--entrypoint', 'id', images['POSTGRES_IMAGE'], '-g', 'postgres').strip())
    os.chown(ROOT / 'postgres', postgres_uid, postgres_gid)
    values = {key: secrets.token_hex(32) for key in (
        'POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'ADMIN_PASSWORD', 'JWT_SECRET', 'TOTP_ENCRYPTION_KEY')}
    values['TRUSTED_PROXY_CIDR'] = gateway
    values.update(images)
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        for key, value in values.items():
            stream.write(f'{key}={value}\n')
    print('Initialized root-only credentials; independent fixed JWT/TOTP; official image digests pinned.')
    print('Trusted Nginx source:', gateway)
    for key, image in images.items():
        print(key + '=' + image)


if __name__ == '__main__':
    main()
