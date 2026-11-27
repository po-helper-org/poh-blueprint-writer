#!/usr/bin/env bash
# Шаг автодеплоя (server-infra ADR 0010): после обновления main, до рестарта poh-blueprint.service. Идемпотентно, без sudo.
#   1. тесты сервиса (упали — шаг упал, автодеплой откатывает выкладку);
#   2. install.sh: настройки (один раз), токен MCP (один раз), юнит.
# nginx-сниппет deploy/poh-blueprint.nginx.conf ставит root-агент poh-nginx-sync по записи в server-infra snippets.conf.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
echo "== тесты"
PYTHONDONTWRITEBYTECODE=1 timeout 600 python3 -m unittest discover -s service/tests -t service 2>&1 | tail -3
echo "== установка"
POH_BLUEPRINT_SKIP_TESTS=1 bash service/deploy/install.sh
