#!/usr/bin/env bash
# Install runtime packages from the official Docker apt repository on Ubuntu.
set -euo pipefail
test "$(id -u)" -eq 0
. /etc/os-release
test "$ID" = ubuntu
test "${VERSION_ID}" = 24.04
test "$(dpkg --print-architecture)" = amd64
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=l
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl --fail --silent --show-error --location https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin nginx certbot
systemctl enable --now docker nginx
docker version --format 'Docker server {{.Server.Version}}'
docker compose version
nginx -v
certbot --version
