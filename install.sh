#!/bin/bash
# Ставит навыки /bft-blueprint, /system-requirements, /adr и /release-plan в воркспейс: skills/ и commands/ (промпт-команды).
# Рядом обычно стоит poh-bft-writer — он пишет БФТ, который читает этот навык.
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
REPO_URL="https://github.com/po-helper-org/poh-blueprint-writer.git"

TEMP_DIR=""
if [ -n "${BLUEPRINT_WRITER_SRC:-}" ] && [ -d "$BLUEPRINT_WRITER_SRC/skills/bft-blueprint" ]; then
  SRC="$BLUEPRINT_WRITER_SRC"
elif [ -d "./skills/bft-blueprint" ] && [ -f "./commands/bft-blueprint.md" ]; then
  SRC="."
else
  echo -e "${BLUE}Клонирую poh-blueprint-writer…${NC}"
  TEMP_DIR="$(mktemp -d)"
  git clone --depth 1 "$REPO_URL" "$TEMP_DIR"
  SRC="$TEMP_DIR"
fi

# Тот же выбор агента, что у poh-bft-writer: BLUEPRINT_WRITER_AGENT (или BFT_WRITER_AGENT) — без вопроса
echo -e "${BLUE}Какой IDE-агент?${NC}"
echo "  1) Claude Code   (.claude/)"
echo "  2) Codex         (.agents/)"
echo "  3) Cline         (.clinerules/)"
echo "  4) DevX          (.clinerules/)"
echo "  5) Universal     (.agents/)"
choice="${BLUEPRINT_WRITER_AGENT:-${BFT_WRITER_AGENT:-}}"
if [ -z "$choice" ] && [ -r /dev/tty ]; then
  read -rp "Выбор [1]: " choice < /dev/tty 2>/dev/null || choice=""
fi
choice="${choice:-1}"
case "$choice" in
  1) ROOT=".claude";     CMD_DIR="commands" ;;
  2) ROOT=".agents";     CMD_DIR="prompts" ;;
  3) ROOT=".clinerules"; CMD_DIR="workflows" ;;
  4) ROOT=".clinerules"; CMD_DIR="workflows" ;;
  5) ROOT=".agents";     CMD_DIR="commands" ;;
  *) echo "Неизвестный выбор"; exit 1 ;;
esac

mkdir -p "$ROOT/$CMD_DIR" "$ROOT/skills/bft-blueprint" "$ROOT/skills/system-requirements" "$ROOT/skills/adr" "$ROOT/skills/release-plan"
cp "$SRC/commands/bft-blueprint.md" "$ROOT/$CMD_DIR/bft-blueprint.md"
cp -R "$SRC/skills/bft-blueprint"/. "$ROOT/skills/bft-blueprint"/
cp "$SRC/commands/system-requirements.md" "$ROOT/$CMD_DIR/system-requirements.md"
cp -R "$SRC/skills/system-requirements"/. "$ROOT/skills/system-requirements"/
cp "$SRC/commands/adr.md" "$ROOT/$CMD_DIR/adr.md"
cp -R "$SRC/skills/adr"/. "$ROOT/skills/adr"/
cp "$SRC/commands/release-plan.md" "$ROOT/$CMD_DIR/release-plan.md"
cp -R "$SRC/skills/release-plan"/. "$ROOT/skills/release-plan"/

[ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
echo -e "${GREEN}✔ /bft-blueprint, /system-requirements, /adr и /release-plan установлены в $ROOT/${NC}"
[ -d "$ROOT/skills/bft-writer" ] || echo "Совет: БФТ для карты пишет poh-bft-writer — https://github.com/po-helper-org/poh-bft-writer"
