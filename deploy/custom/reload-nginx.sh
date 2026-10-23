#!/bin/sh
# Certbot invokes this only after a certificate has been renewed successfully.
set -eu
/usr/sbin/nginx -t
/usr/bin/systemctl reload nginx
