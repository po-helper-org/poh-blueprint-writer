#!/bin/bash
# Установка сервиса Blueprint под пользователем сервера: тесты → настройки → токен MCP → юнит systemd. Идемпотентно.
# Воркспейс — BLUEPRINT_WORKSPACE при первой установке, иначе ~/.local/share/poh-blueprint/workspace.
# nginx — не здесь: сниппет deploy/poh-blueprint.nginx.conf ставит poh-nginx-sync (или вручную, см. README).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
CONF_DIR="$HOME/.config/poh-blueprint"
CONF="$CONF_DIR/config.json"
WS="${BLUEPRINT_WORKSPACE:-$HOME/.local/share/poh-blueprint/workspace}"

if [ -z "${POH_BLUEPRINT_SKIP_TESTS:-}" ]; then
  echo "▸ тесты"
  (cd "$REPO" && python3 -m unittest discover -s service/tests -t service)
fi

mkdir -p "$CONF_DIR" "$HOME/.local/state/poh-blueprint"
chmod 700 "$CONF_DIR"
if [ ! -f "$CONF" ]; then
  mkdir -p "$WS/bft/documentation"
  python3 - "$HERE/config.example.json" "$CONF" "$WS" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
cfg.update(workspace=sys.argv[3], docs_path="bft/documentation", agent=None, public_url="")
json.dump(cfg, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
  echo "▸ настройки: $CONF (воркспейс $WS)"
fi

TOK="$CONF_DIR/mcp-tokens"
if [ ! -f "$TOK" ]; then
  ( umask 077; printf 'owner:bpmcp_%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > "$TOK" )
  echo "▸ токен MCP выпущен: $TOK (значение не печатаем)"
fi

UNIT="$HOME/.config/systemd/user/poh-blueprint.service"
mkdir -p "$(dirname "$UNIT")"
NEW="$(sed "s#%h/Projects/poh-blueprint-writer#$REPO#g" "$HERE/deploy/poh-blueprint.service")"
if [ ! -f "$UNIT" ] || [ "$NEW" != "$(cat "$UNIT")" ]; then
  printf '%s\n' "$NEW" > "$UNIT"
  systemctl --user daemon-reload
  echo "▸ юнит обновлён"
fi
systemctl --user enable poh-blueprint.service >/dev/null 2>&1 || true
systemctl --user restart poh-blueprint.service
sleep 1
systemctl --user is-active poh-blueprint.service
POH_BLUEPRINT_CONFIG="$CONF" python3 "$HERE/server.py" list | head -5
