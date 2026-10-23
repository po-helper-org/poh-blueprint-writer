#!/bin/bash
# Ставит навык /bft-blueprint в воркспейс: skills/bft-blueprint и commands/bft-blueprint.md.
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
echo "  6) pi.dev        (.pi/)"
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
  6) ROOT=".pi";         CMD_DIR="prompts" ;;
  *) echo "Неизвестный выбор"; exit 1 ;;
esac

mkdir -p "$ROOT/$CMD_DIR" "$ROOT/skills/bft-blueprint"
cp "$SRC/commands/bft-blueprint.md" "$ROOT/$CMD_DIR/bft-blueprint.md"
cp -R "$SRC/skills/bft-blueprint"/. "$ROOT/skills/bft-blueprint"/

# Харнессы без слэш-команд читают AGENTS.md: без записи там агент не знает про маршрут и рисует HTML сам
case "$choice" in 2|5|6)
  if ! grep -q "bft-blueprint-rule" AGENTS.md 2>/dev/null; then
    cat >> AGENTS.md <<RULE

<!-- bft-blueprint-rule -->
## Service Blueprint по БФТ
Запрос «blueprint», «карта инициативы», «/bft-blueprint»: прочитай $ROOT/skills/bft-blueprint/SKILL.md и иди по $ROOT/skills/bft-blueprint/resources/autopilot.md.
HTML руками не пиши — страницы дают только скрипты навыка. Задачи — проект Backlog.md (\`./backlog.py\`). Не отдавай результат, пока \`python3 $ROOT/skills/bft-blueprint/scripts/bft-blueprint-verify.py <docs_path>/<epic>\` не вернул 0.
RULE
    echo -e "${GREEN}✔ правило записано в AGENTS.md${NC}"
  fi ;;
esac

[ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"
echo -e "${GREEN}✔ /bft-blueprint установлен в $ROOT/${NC}"
[ -d "$ROOT/skills/bft-writer" ] || echo "Совет: БФТ для карты пишет poh-bft-writer — https://github.com/po-helper-org/poh-bft-writer"
