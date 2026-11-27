#!/bin/bash
# Установка сервиса Blueprint под пользователем сервера: тесты → настройки → токен MCP → юнит systemd.
# nginx (sudo) — отдельной строкой в конце: это шаг владельца.
#
#   BLUEPRINT_WORKSPACE=~/путь/к/воркспейсу bash service/deploy/install.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CONF_DIR="$HOME/.config/poh-blueprint"
CONF="$CONF_DIR/config.json"
WS="${BLUEPRINT_WORKSPACE:-}"

echo "▸ тесты"
(cd "$HERE/.." && python3 -m unittest discover -s service/tests -t service)

mkdir -p "$CONF_DIR" "$HOME/.local/state/poh-blueprint"
chmod 700 "$CONF_DIR"
if [ ! -f "$CONF" ]; then
  [ -n "$WS" ] || { echo "задайте BLUEPRINT_WORKSPACE — корень воркспейса с bft/documentation"; exit 1; }
  python3 - "$HERE/config.example.json" "$CONF" "$WS" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
cfg["workspace"] = sys.argv[3]
cfg["agent"] = None          # фоновый агент включается правкой настроек осознанно
cfg["public_url"] = ""
json.dump(cfg, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
  echo "▸ настройки: $CONF"
fi

TOK="$CONF_DIR/mcp-tokens"
if [ ! -f "$TOK" ]; then
  printf 'owner:bpmcp_%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > "$TOK"
  chmod 600 "$TOK"
  echo "▸ токен MCP выпущен: $TOK (строка «имя:токен»; значение не печатаем)"
fi

POH_BLUEPRINT_CONFIG="$CONF" python3 "$HERE/server.py" list

mkdir -p "$HOME/.config/systemd/user"
sed "s#%h/Projects/poh-blueprint-writer#$(cd "$HERE/.." && pwd)#g" "$HERE/deploy/poh-blueprint.service" > "$HOME/.config/systemd/user/poh-blueprint.service"
systemctl --user daemon-reload
systemctl --user enable --now poh-blueprint.service
sleep 1
systemctl --user is-active poh-blueprint.service
curl -fsS -o /dev/null -w "▸ /blueprint/ → %{http_code}\n" http://127.0.0.1:8662/blueprint/

echo
echo "Шаг владельца (sudo): sudo cp $HERE/deploy/poh-blueprint.nginx.conf /etc/nginx/snippets/poh-blueprint.conf,"
echo "строка «include /etc/nginx/snippets/poh-blueprint.conf;» в server{} корп-браузера, sudo nginx -t && sudo systemctl reload nginx"
