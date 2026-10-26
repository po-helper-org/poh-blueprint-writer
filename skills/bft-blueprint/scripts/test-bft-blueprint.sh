#!/bin/bash
# Самотест bft-blueprint: линтер ловит каждый код на фикстурах, эталон проходит строго,
# рендерер не пишет файлов по сломанному документу, стрелки не пересекают чужие карточки.
# Вторая часть — история через экраны (bft-story-*), третья — карта инициативы в проекте Backlog.md
# (bft-backlog-*): коды BL и SN на сломанных копиях, страница эталона байт в байт, детерминированный
# автономный проект и zip (встроенный CLI, инструкции агенту), BPMN из «Процесса», новый проект из истории.
# Запуск из корня репозитория: bash skills/bft-blueprint/scripts/test-bft-blueprint.sh
set -u

DIR="skills/bft-blueprint"
LINT="$DIR/scripts/bft-blueprint-lint.py"
RENDER="$DIR/scripts/bft-blueprint-render.py"
FIX="$DIR/scripts/fixtures"
GOLD="$DIR/examples/golden_blueprint.md"
fails=0
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

ok()   { echo "ok    $1"; }
fail() { echo "FAIL  $1"; fails=$((fails + 1)); }

expect_codes() {  # <имя> <ожидаемый rc> <файл> <коды через пробел> [доп. аргументы линтера]
  local name="$1" rc_want="$2" file="$3" codes="$4"; shift 4
  local out rc
  out="$(python3 "$LINT" "$file" "$@" 2>&1)"; rc=$?
  [ "$rc" -eq "$rc_want" ] || { fail "$name: код выхода $rc, ожидался $rc_want"; return; }
  for c in $codes; do
    grep -q " $c " <<<"$out" || { fail "$name: нет $c в выводе"; return; }
  done
  ok "$name"
}

expect_codes "эталон проходит строго"        0 "$GOLD" "" --strict
expect_codes "эталон без сверки с БФТ"       0 "$GOLD" "" --no-source
expect_codes "структура: разделы и дорожки"  1 "$FIX/broken_structure.md" "BP002 BP006"
expect_codes "смысл: ошибки"                 1 "$FIX/broken_semantics.md" "BP011 BP012 BP013 BP014 BP016 BP017"
expect_codes "смысл: предупреждения"         1 "$FIX/broken_semantics.md" "BP018 BP020 BP021 BP022 BP023"
expect_codes "БФТ-источника нет"             1 "$GOLD" "BP015" --source "$tmp/нет-такого.md"
expect_codes "предупреждения печатаются вместе с ошибками" 1 "$FIX/broken_semantics.md" "BP020"

# предупреждения сами по себе валят только со --strict
sed 's/^source_rev: .*/source_rev: 000000000000/' "$GOLD" > "$tmp/stale.md"
python3 "$LINT" "$tmp/stale.md" --source "$DIR/scripts/fixtures/golden_deep_document.md" >/dev/null 2>&1 \
  && ok "устаревший source_rev — только предупреждение" || fail "устаревший source_rev не должен валить без --strict"
python3 "$LINT" "$tmp/stale.md" --source "$DIR/scripts/fixtures/golden_deep_document.md" --strict >/dev/null 2>&1 \
  && fail "--strict должен валить на предупреждении" || ok "--strict валит на предупреждении"

# латинские К/С вместо кириллических не рвут связи
sed 's/К\([0-9]\)/K\1/g; s/С\([0-9]\)/C\1/g' "$GOLD" > "$tmp/latin.md"
python3 "$LINT" "$tmp/latin.md" --source "$DIR/scripts/fixtures/golden_deep_document.md" >/dev/null 2>&1 \
  && ok "латинские двойники ID нормализуются" || fail "латинские К/С в ID сломали разбор"

# рендер: эталон собирается, битый документ — нет
python3 "$RENDER" "$GOLD" --out-dir "$tmp/out" >/dev/null 2>&1 && ok "эталон отрендерен" || fail "эталон не отрендерился"
svg="$tmp/out/golden_blueprint.svg"; page="$tmp/out/golden_blueprint.html"
[ "$(head -c 5 "$svg" 2>/dev/null)" = "<?xml" ] && ok "svg: корректный заголовок" || fail "svg: нет XML-заголовка"
[ "$(grep -o 'class="card ' "$svg" | wc -l)" -eq 19 ] && ok "svg: 19 карточек" || fail "svg: число карточек не 19"
[ "$(grep -o 'class="link ' "$svg" | wc -l)" -ge 21 ] && ok "svg: стрелки на месте" || fail "svg: стрелок меньше 21 (+ легенда)"
grep -q "Покрытие требований БФТ" "$page" && grep -q "Что реализовать на каждом слое" "$page" \
  && ok "html: разделы страницы" || fail "html: нет разделов страницы"
if grep -Eq 'src="https?://|href="https?://' "$page"; then fail "html: внешние ресурсы (страница должна быть автономной)"; else ok "html: без внешних ресурсов"; fi
cmp -s "$svg" "$DIR/examples/golden_blueprint.svg" \
  && ok "svg: совпадает с examples/golden_blueprint.svg" \
  || fail "svg: разошёлся с examples/golden_blueprint.svg — пересобери эталон: python3 $RENDER $GOLD --out-dir <каталог> и скопируй .svg"
python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" "$svg" 2>/dev/null \
  && ok "svg: well-formed XML" || fail "svg: не well-formed XML"

python3 "$RENDER" "$FIX/broken_semantics.md" --out-dir "$tmp/bad" >/dev/null 2>&1; rc=$?
{ [ "$rc" -eq 1 ] && [ ! -e "$tmp/bad" ]; } && ok "битый документ: код 1, файлов нет" || fail "битый документ отрендерился или код не 1"

# стрелки не пересекают чужие карточки
python3 - "$RENDER" "$GOLD" <<'PY' && ok "маршруты: ни одна стрелка не задевает чужую карточку" || fail "маршруты: стрелка пересекает карточку"
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("r", sys.argv[1]); r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
bp = r.lint.run(Path(sys.argv[2]), None, False)
lanes, boxes, x0, width, hdr_h, lane_geo, bnd, y_end = r.layout(bp)
bad = []
for lk in bp.links:
    s, d = boxes[lk.src], boxes[lk.dst]
    pts = r.route(s, d, boxes, x0, lane_geo)
    others = [b.rect for b in boxes.values() if b is not s and b is not d]
    if r._cost(pts, others):
        bad.append(f"{lk.src}->{lk.dst}")
if bad:
    print("пересекают:", ", ".join(bad), file=sys.stderr); sys.exit(1)
PY

# --- история через экраны -------------------------------------------------------------
SLINT="$DIR/scripts/bft-story-lint.py"
SRENDER="$DIR/scripts/bft-story-render.py"
SGOLD="$DIR/examples/golden_story.md"

expect_story() {  # <имя> <ожидаемый rc> <файл> <коды через пробел> [доп. аргументы линтера]
  local name="$1" rc_want="$2" file="$3" codes="$4"; shift 4
  local out rc
  out="$(python3 "$SLINT" "$file" "$@" 2>&1)"; rc=$?
  [ "$rc" -eq "$rc_want" ] || { fail "история · $name: код выхода $rc, ожидался $rc_want"; return; }
  for c in $codes; do
    grep -q " $c " <<<"$out" || { fail "история · $name: нет $c в выводе"; return; }
  done
  ok "история · $name"
}

# БФТ эталона (перезапуск акции DineClub) в репозиторий не входит — сверка с источником на фикстуре
expect_story "эталон проходит строго"     0 "$SGOLD" "" --no-source --strict
expect_story "эталон без БФТ рядом"       1 "$SGOLD" "ST013"
expect_story "структура"                  1 "$FIX/broken_story_structure.md" "ST001 ST002 ST003"
expect_story "экраны и ссылки"            1 "$FIX/broken_story_screens.md" "ST006 ST008 ST009 ST010 ST015"
expect_story "смысл: ошибки"              1 "$FIX/broken_story_semantics.md" "ST007 ST008 ST010 ST011 ST012 ST014 ST016"
expect_story "смысл: предупреждения"      1 "$FIX/broken_story_semantics.md" "ST017 ST018 ST020 ST022 ST023"
out="$(python3 "$SLINT" "$FIX/broken_story_semantics.md" 2>&1)"
grep -q "ПТ-3 не отражено" <<<"$out" && fail "история · ПТ от лица команды не должно требовать шага" || ok "история · ПТ команды не персонаж"

sed 's/^| A | Подготовка/| 1 | Подготовка/' "$SGOLD" > "$tmp/stage.md"
expect_story "этапы: ID — латинская буква" 1 "$tmp/stage.md" "ST004" --no-source
sed 's/^| Ш12 | rest | B–E |/| Ш12 | rest | B–F |/' "$SGOLD" > "$tmp/band.md"
expect_story "полоса ожидания не накрывает шаги" 1 "$tmp/band.md" "ST011" --no-source
sed 's/^| Ш4 | guest | D |/| Ш4 | guest | F |/' "$SGOLD" > "$tmp/order.md"
expect_story "шаги идут слева направо" 1 "$tmp/order.md" "ST007" --no-source
sed 's/| E1 | — |$/| E1 | ответ: письмо (PO, 2026-10-17) |/' "$SGOLD" > "$tmp/answered.md"
sed -i 's/^| E1 | Оповещение | уведомление | основной |/| E1 | Оповещение | уведомление | неизвестен |/' "$tmp/answered.md"
expect_story "неизвестный экран без открытого вопроса" 1 "$tmp/answered.md" "ST010" --no-source
sed 's/| Купил билет — и сразу вижу скидку |/| Купил билет — и сразу вижу скидку (ПТ-2) |/' "$SGOLD" > "$tmp/req.md"
expect_story "ID требования в заголовке" 1 "$tmp/req.md" "ST012" --no-source

python3 "$SRENDER" "$SGOLD" --out-dir "$tmp/sout" >/dev/null 2>&1 && ok "история · эталон отрендерен" || fail "история · эталон не отрендерился"
spage="$tmp/sout/golden_story.html"
if grep -Eq 'src="https?://|href="https?://|@import' "$spage"; then fail "история · html: внешние ресурсы"; else ok "история · html: без внешних ресурсов"; fi
python3 - "$spage" <<'PY' && ok "история · html: данные разбираются, 17 карточек, 13 экранов" || fail "история · html: данные страницы не те"
import json, re, sys
page = open(sys.argv[1], encoding="utf-8").read()
data = json.loads(re.search(r'<script type="application/json" id="story-data">(.*?)</script>', page, re.S).group(1))
assert len(data["steps"]) == 17 and len(data["screens"]) == 13, (len(data["steps"]), len(data["screens"]))
assert sum(q["open"] for q in data["questions"]) == 8
assert [s["n"] for s in data["steps"] if s["persona"] == "rest" and s["n"]] == [1, 2, 3, 4, 5, 6]
PY
cmp -s "$spage" "$DIR/examples/golden_story.html" \
  && ok "история · html: совпадает с examples/golden_story.html" \
  || fail "история · html: разошёлся с examples/golden_story.html — пересобери: python3 $SRENDER $SGOLD --out-dir $DIR/examples"
python3 "$SRENDER" "$FIX/broken_story_screens.md" --out-dir "$tmp/sbad" >/dev/null 2>&1; rc=$?
{ [ "$rc" -eq 1 ] && [ ! -e "$tmp/sbad" ]; } && ok "история · битый документ: код 1, файлов нет" || fail "история · битый документ отрендерился или код не 1"

# --- карта инициативы: проект Backlog.md -------------------------------------------------
BLINT="$DIR/scripts/bft-backlog-lint.py"
BBUILD="$DIR/scripts/bft-backlog-build.py"
BGOLD="$DIR/examples/dineclub-restart-blueprint"
BOK="$FIX/backlog_ok"

expect_bl() {  # <имя> <ожидаемый rc> <проект> <коды через пробел> [доп. аргументы линтера]
  local name="$1" rc_want="$2" proj="$3" codes="$4"; shift 4
  local out rc
  out="$(python3 "$BLINT" "$proj" "$@" 2>&1)"; rc=$?
  [ "$rc" -eq "$rc_want" ] || { fail "карта · $name: код выхода $rc, ожидался $rc_want"; return; }
  for c in $codes; do
    grep -q " $c " <<<"$out" || { fail "карта · $name: нет $c в выводе"; return; }
  done
  ok "карта · $name"
}

expect_bl "эталон проходит строго"        0 "$BGOLD" "" --no-source --strict
expect_bl "эталон без БФТ рядом"          0 "$BGOLD" "BL015"
expect_bl "явный --source не найден"      1 "$BGOLD" "BL015" --source "$tmp/нет.md"
expect_bl "вторая инициатива сверена с БФТ" 0 "$BOK" ""

# сломанные копии второй инициативы: каждая правка — свой код
python3 - "$BOK" "$tmp/bad" "$FIX/screens_bad" <<'PY'
import re, shutil, sys
from pathlib import Path
src, out, sbad = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
def copy(name):
    d = out / name; shutil.copytree(src, d); return d
def edit(d, glob, a, b, count=1):
    f = next(d.glob(glob)); t = f.read_text(encoding="utf-8")
    assert a in t, (glob, a); f.write_text(t.replace(a, b, count), encoding="utf-8")
T1, T2 = "backlog/tasks/bp-1 - *.md", "backlog/tasks/bp-2 - *.md"
C1, C21, C22 = "backlog/tasks/bp-1.1 - *.md", "backlog/tasks/bp-2.1 - *.md", "backlog/tasks/bp-2.2 - *.md"
MAP, STORY = "backlog/docs/doc-1 - *.md", "backlog/docs/doc-2 - *.md"

d = copy("noproject"); (d / "backlog/config.yml").unlink()
d = copy("structure")
edit(d, MAP, "<!-- bft-map\nepic_slug: demo-story\n", "<!-- bft-map\n")
edit(d, MAP, "| ID | Команда |", "| ID | Команда | Лишняя |")
edit(d, STORY, "## Этапы", "## Этапы и ещё")
(d / "backlog/tasks/bp-9 - Мусор.md").write_text("просто текст\n", encoding="utf-8")
d = copy("refs")
edit(d, T1, "  - 'stage:A'\n  - создать", "  - 'stage:Z'")
edit(d, T2, "  - '@rest'", "  - '@nobody'")
edit(d, T2, "### ASIS\nСкидка по брони.\n\n", "")
edit(d, T2, "1. Официант сканирует билет\n2.", "Официант сканирует билет.")
edit(d, T2, "- [ ] #1 Скидка 10% по предъявлению билета\n- [ ] #2 Отказ — с причиной\n", "")
edit(d, C1, "parent_task_id: BP-1", "parent_task_id: BP-77")
edit(d, C21, "layer:employee", "layer:frontstage")
edit(d, C22, "- **Выход:** Ответ проверки (BP-2.1)", "- **Результат:** Ответ проверки (BP-9.9)")
edit(d, MAP, "| BP-2.1 | вопрос |", "| BP-99 | разговор |")
edit(d, C21, "  - нет → Официант: Объясняет отказ [УТОЧНИТЬ у PO]\n", "")
edit(d, C22, "- Сканер: Передаёт штрихкод", "- Сканер передаёт штрихкод")
edit(d, C1, "### UserStory\nКак гость, я хочу сразу после покупки увидеть скидку, чтобы спланировать вечер.\n\n", "")
edit(d, T1, "dependencies: []", "dependencies: []\ndocumentation:\n  - doc-42")
d = copy("semantics")
edit(d, T1, "title: Блок акции на странице после покупки", "title: Блок акции на странице после покупки с очень длинным названием, которое не читается за секунду")
edit(d, T2, "Скидка выдаётся по билету", "Скидка выдаётся по билету через REST API")
edit(d, T1, "Требования БФТ: ПТ-2, ИТ-1", "Требования БФТ: ПТ-2, ФТ-77")
edit(d, C1, "Один офер (ИТ-1)", "Один офер")
d = copy("warnings")
edit(d, T2, "  - 'stage:B'", "  - 'stage:A'")
for g in (C21, C22):
    next(d.glob(g)).unlink()
edit(d, C1, "- **Управление:** Один офер (ИТ-1)\n", "")
edit(d, C1, "Как гость, я хочу сразу после покупки увидеть скидку", "Гость хочет сразу после покупки увидеть скидку")
edit(d, C1, "Гость выбрал ресторан (BP-2.1)", "Скидка через 99 минут")
edit(d, C1, 'N2["Показывает блок «скидка 10%»"]', 'N2["Старое"]')
edit(d, MAP, "| В1 | PO | Что видит официант при отказе? | BP-2.1 |", "| В1 | PO | Что видит официант при отказе? | BP-2 |")
d = copy("screens")
for f in sorted(sbad.glob("*.md")):
    t = f.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", t, re.M)
    hdr = f"{f.stem} · {title.group(1) if title else 'без заголовка'}"
    (d / "backlog/docs/screens").mkdir(parents=True, exist_ok=True)
    (d / f"backlog/docs/screens/doc-{30 + len(list((d / 'backlog/docs/screens').glob('*')))} - {f.stem}.md").write_text(
        f"---\nid: doc-{30 + len(list((d / 'backlog/docs/screens').glob('*')))}\ntitle: {hdr}\ntype: specification\ncreated_date: '2026-10-19 10:00'\n---\n{t}", encoding="utf-8")
(d / "backlog/docs/screens/doc-40 - Без-ID.md").write_text("---\nid: doc-40\ntitle: Просто экран\ntype: specification\n---\n# Экран\n", encoding="utf-8")
PY
expect_bl "не проект Backlog.md"          1 "$tmp/bad/noproject" "BL001"
expect_bl "структура"                     1 "$tmp/bad/structure" "BL002 BL003 BL004 BL005" --no-source
expect_bl "задачи и карточки"             1 "$tmp/bad/refs" "BL006 BL007 BL008 BL009 BL010 BL011" --no-source
expect_bl "смысл: ошибки"                 1 "$tmp/bad/semantics" "BL014 BL016 BL017 BL018" --source "$FIX/story_source.md"
expect_bl "смысл: предупреждения"         1 "$tmp/bad/warnings" "BL020 BL021 BL022 BL023 BL026 BL027 BL028 BL030" --strict --source "$FIX/story_source.md"
expect_bl "экраны · битые заметки"        1 "$tmp/bad/screens" "SN001 SN002 SN003 SN004 SN005 SN006 SN020 SN021 SN022 SN023" --no-source

# сборка: эталон совпадает со страницей в examples, архив — тот же байт в байт и автономный
python3 "$BBUILD" "$BGOLD" --no-source --check >/dev/null 2>&1 \
  && ok "карта · эталон: схемы BPMN, скрипты и инструкции проекта актуальны" || fail "карта · эталон устарел (BL022/BL029) — python3 $BBUILD $BGOLD --no-source --out-dir $DIR/examples --no-zip"
GOLD="$tmp/bout/dineclub-restart-blueprint"; mkdir -p "$tmp/bout" && cp -r "$BGOLD" "$GOLD" && python3 "$BBUILD" "$GOLD" --out-dir "$tmp/bout" >/dev/null 2>&1 \
  && cmp -s "$tmp/bout/dineclub-restart-map.html" "$DIR/examples/dineclub-restart-map.html" \
  && ok "карта · html: совпадает с examples/dineclub-restart-map.html" \
  || fail "карта · html разошёлся с эталоном — пересобери: python3 $BBUILD $BGOLD --out-dir $DIR/examples --no-zip"
python3 - "$tmp/bout" <<'PY' && ok "карта · страница: 19 задач, 20 карточек в четырёх слоях, стрелки, заметки экранов" || fail "карта · данные страницы не те"
import json, re, sys
from pathlib import Path
d = json.loads(re.search(r'id="map-data">(.*?)</script>', (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8"), re.S).group(1))
assert len(d["tasks"]) == 19 and len(d["cards"]) == 20, (len(d["tasks"]), len(d["cards"]))
assert {c["layer"] for c in d["cards"]} == {"employee", "technology", "backstage", "support"}
assert all(c["params"].get("out") and c["demo"] and c["us"] and c["js"] and c["bpmn"].startswith("flowchart LR") for c in d["cards"])
assert all(t["brief"].get("ASIS") and t["ac"] for t in d["tasks"])
assert len(d["links"]) >= 20 and len(d["notes"]) == 12
PY
# «Исполнение»: у каждого экрана с требованиями — задача, чей documentation (или её карточки) ведёт на документ экрана
python3 - "$tmp/bout" <<'PY' && ok "карта · исполнение: у каждого экрана есть задачи, F1 → BP-16, панель #exec, HowToDemo раскадровкой" || fail "карта · связь экран → задачи исполнения не та"
import json, re, sys
from pathlib import Path
page = (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
scr = {k: v["screen"] for k, v in d["docs"].items() if v["screen"]}
of = {}
for t in d["tasks"]:
    for x in t["docs"]: of.setdefault(scr.get(x.split()[0].lower()), set()).add(t["id"])
for c in d["cards"]:
    for x in c["docs"]: of.setdefault(scr.get(x.split()[0].lower()), set()).add(c["task"])
assert all(of.get(s) for s in d["notes"]), [s for s in d["notes"] if not of.get(s)]
assert of["F1"] == {"BP-16"} and of["F2"] == {"BP-15"}, of
assert 'id="exec"' in page and "data-extask" in page
# HowToDemo раскадровкой: шаг с ID экрана «(F3)» — кадр этого экрана, даже если он не в documentation задачи
T = {t["id"]: t for t in d["tasks"]}
assert T["BP-16"]["brief"]["HowToDemo"].count("(F3)") == 3 and "(F1)" in T["BP-15"]["brief"]["HowToDemo"]
assert 'class="demo"' in page and "function demoHTML" in page and "function howShow" in page
PY
EX="$tmp/bad/exec" && cp -r "$BGOLD" "$EX" && python3 - "$EX" <<'PY'
import re, sys
from pathlib import Path
for f in Path(sys.argv[1], "backlog/tasks").glob("bp-17*.md"):
    f.write_text(re.sub(r"documentation:\n  - doc-13\n", "", f.read_text(encoding="utf-8")), encoding="utf-8")
PY
expect_bl "экран без задачи исполнения"   1 "$EX" "BL042" --no-source --strict
# эпик → история → подзадачи по зонам: у BP-5 четыре подзадачи (Design, FE, BE, QA), остальные истории — без подзадач
python3 - "$tmp/bout" <<'PY' && ok "карта · подзадачи по зонам: BP-5 — Design, FE, BE, QA; остальные истории двухуровневые" || fail "карта · подзадачи по зонам не дошли до страницы"
import json, re, sys
from pathlib import Path
page = (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
assert [(z["id"], z["task"], z["zone"], z["team"]) for z in d["subs"]] == [("BP-5.2", "BP-5", "Design", "des"), ("BP-5.3", "BP-5", "FE", "?"), ("BP-5.4", "BP-5", "BE", "unitb"), ("BP-5.5", "BP-5", "QA", "?")], d["subs"]
assert next(z for z in d["subs"] if z["id"] == "BP-5.3")["cand"] == "Витрина или TeamA"
assert len(d["tasks"]) == 19 and "function openSub" in page and "data-teams" in page
PY
# MoSCoW: приоритет у каждой истории, Would — за линией Out of scope; без приоритета — BL046, чужое значение — BL006
python3 - "$tmp/bout" <<'PY' && ok "карта · MoSCoW: 9 Must, 8 Should, 2 Would за линией Out of scope" || fail "карта · приоритеты MoSCoW не дошли до страницы"
import json, re, sys
from collections import Counter
from pathlib import Path
page = (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
assert Counter(t["prio"] for t in d["tasks"]) == {"must": 9, "should": 8, "would": 2}
assert {t["id"] for t in d["tasks"] if t["prio"] == "would"} == {"BP-11", "BP-14"}
assert all(z["prio"] == "must" for z in d["subs"]) and 'class="oosl do"' in page
PY
MB="$tmp/bad/moscow" && cp -r "$BGOLD" "$MB" && python3 - "$MB" <<'PY'
import sys
from pathlib import Path
t = Path(sys.argv[1], "backlog/tasks")
f = next(t.glob("bp-14 *")); f.write_text(f.read_text(encoding="utf-8").replace("  - moscow:would\n", ""), encoding="utf-8")
PY
out="$(python3 "$BLINT" "$MB" --no-source --strict 2>&1)"; rc=$?
sed -i 's/^  - moscow:would$/  - moscow:could/' "$MB/backlog/tasks/"bp-11\ *
out2="$(python3 "$BLINT" "$MB" --no-source 2>&1)"; rc2=$?
[ "$rc" -eq 1 ] && grep -q "BL046 BP-14: нет приоритета" <<<"$out" && [ "$rc2" -eq 1 ] && grep -q "BL006 BP-11: приоритет — одна метка moscow:" <<<"$out2" \
  && ok "карта · MoSCoW: без приоритета — BL046, чужое значение — BL006" || fail "карта · MoSCoW не проверяется — $out $out2"
# BL043: подзадача — зона из списка, родитель — история
ZB="$tmp/bad/zone" && cp -r "$BGOLD" "$ZB" && python3 - "$ZB" <<'PY'
import sys
from pathlib import Path
t = Path(sys.argv[1], "backlog/tasks")
f = next(t.glob("bp-5.3 *")); f.write_text(f.read_text(encoding="utf-8").replace("  - zone:FE\n", "  - zone:Frontend\n"), encoding="utf-8")
f = next(t.glob("bp-5.4 *")); f.write_text(f.read_text(encoding="utf-8").replace("parent_task_id: BP-5\n", "parent_task_id: BP-77\n"), encoding="utf-8")
PY
expect_bl "подзадача по зоне: форма"      1 "$ZB" "BL043" --no-source
# BL044: в работе истории две команды, подзадач нет; BL045: один экран делают истории разных команд
ZW="$tmp/bad/zonew" && cp -r "$BGOLD" "$ZW" && python3 - "$ZW" <<'PY'
import sys
from pathlib import Path
t = Path(sys.argv[1], "backlog/tasks")
f = next(t.glob("bp-6.1 *")); f.write_text(f.read_text(encoding="utf-8").replace("assignee: []\n", "assignee:\n  - '@vit'\n", 1), encoding="utf-8")
f = next(t.glob("bp-9 *")); f.write_text(f.read_text(encoding="utf-8").replace("dependencies: []\n", "dependencies: []\ndocumentation:\n  - doc-6\n", 1), encoding="utf-8")
PY
out="$(python3 "$BLINT" "$ZW" --no-source --strict 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "BL044 BP-6: в работе 2 команды (UnitB, Витрина)" <<<"$out" && grep -q "BL045 экран D1 делают BP-8, BP-9" <<<"$out" \
  && ok "карта · кроссфункциональная история без подзадач: BL044; один экран у двух команд: BL045" || fail "карта · BL044/BL045 не пойманы — $out"
# картинки и mermaid — файлы проекта: страница ссылается на них, а не несёт в себе
python3 - "$tmp/bout" <<'PY' && ok "карта · картинки экранов и mermaid — файлы проекта, схема BPMN — текст карточки" || fail "карта · страница несёт картинки или mermaid в себе"
import json, re, sys
from pathlib import Path
out = Path(sys.argv[1]); page = (out / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
root = out / d["base"]
assert d["base"] == "dineclub-restart-blueprint/" and "data:image" not in page and "mermaid.initialize" not in page.split("map-data")[0]
assert all((root / s["img"]).is_file() and s["img"].startswith("backlog/assets/screens/") for s in d["screens"].values())
assert (root / d["mermaid"]).is_file() and len(page) < 300_000
for sid, md in d["notes"].items():
    for src in re.findall(r"!\[.*?\]\((.+?)\)", md):
        assert (root / src).is_file(), src
for c in d["cards"]:
    text = (root / c["file"]).read_text(encoding="utf-8")
    assert "```mermaid\n" + c["bpmn"] + "\n```" in text, c["id"]
PY
# BL032: строка, которой нет в проекте, не попадает на страницу; BL031: картинка экрана расходится с «Историей»
python3 - "$DIR/scripts" "$GOLD" <<'PY' && ok "карта · BL032: на странице только текст проекта" || fail "карта · BL032 не ловит выдуманный текст"
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("b", Path(sys.argv[1]) / "bft-backlog-build.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
pr = b.lint.run(Path(sys.argv[2]).resolve(), None, True)
m = b.model(pr)
assert b.provenance(m, pr) == []
m["cards"][0]["us"] = "Как гость, я хочу то, чего в бэклоге нет"
m["tasks"][0]["brief"]["ASIS"] = "Выдуманная строка"
miss = b.provenance(m, pr)
assert len(miss) == 2, miss
PY
cp "$GOLD/backlog/assets/screens/F3.svg" "$tmp/F3.svg" && echo '<!-- правка -->' >> "$GOLD/backlog/assets/screens/F3.svg"
out="$(python3 "$BBUILD" "$GOLD" --check 2>&1)"; rc=$?
cp "$tmp/F3.svg" "$GOLD/backlog/assets/screens/F3.svg"
[ "$rc" -eq 1 ] && grep -q "BL031 картинка экрана F3" <<<"$out" && ok "карта · BL031: картинка экрана расходится с «Историей»" || fail "карта · BL031 не сработал"
cp "$tmp/bout/dineclub-restart-blueprint.zip" "$tmp/first.zip"
python3 "$BBUILD" "$GOLD" --out-dir "$tmp/bout" >/dev/null 2>&1 && cmp -s "$tmp/bout/dineclub-restart-blueprint.zip" "$tmp/first.zip" \
  && ok "карта · zip: та же карта — тот же архив байт в байт" || fail "карта · zip: архив не детерминирован"
python3 - "$tmp/first.zip" "$tmp/unz" <<'PY' || fail "карта · zip: распаковка не удалась"
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); z.extractall(sys.argv[2])
assert all(z.getinfo(f"dineclub-restart-blueprint/{n}").external_attr >> 16 == 0o755 for n in ("backlog.py", "blueprint.py"))
PY
# распакованный проект в чистом окружении: только python3, без навыка и без npm
( cd "$tmp/unz/dineclub-restart-blueprint" && E="env -i PATH=/usr/bin:/bin HOME=$tmp" \
  && $E python3 blueprint.py build >/dev/null 2>&1 && cmp -s blueprint.html dineclub-restart-map.html \
  && $E python3 backlog.py task list -l stage:F --plain | grep -q "BP-16 - " \
  && $E python3 backlog.py task create "Учесть часовой пояс площадки" -p BP-16 -a "" -l "stage:F,layer:backstage" --no-dod-defaults \
       -d $'TeamA учитывает часовой пояс.\n\n### UserStory\nКак официант, я хочу верную проверку в полночь, чтобы не спорить с гостем.\n\n### JobStory\n- Когда гость пришёл в последний день, хочу верный ответ, чтобы дать скидку.\n\n### Параметры\n- **Вход:** Штрихкод (BP-16.1)\n- **Управление:** Окно 7 дней (ФТ-1)\n- **Выход:** Ответ (BP-15.1)\n- **Механизм:** TeamA\n\n### Процесс\n- TeamA: Берёт часовой пояс площадки\n- TeamA: Считает окно\n\n### HowToDemo\n1. Сканирую в 23:59\n2. Проверка проходит' >/dev/null \
  && $E python3 backlog.py task edit BP-16 --check-ac 1 --add-ref https://jira.example.com/browse/DEMO-16 >/dev/null \
  && $E python3 blueprint.py build >/dev/null 2>&1 && $E python3 blueprint.py check >/dev/null 2>&1 \
  && grep -q "Берёт часовой пояс площадки" "$(ls backlog/tasks/bp-16.2*)" && grep -q 'N1\["Берёт часовой пояс площадки"\]' "$(ls backlog/tasks/bp-16.2*)" \
  && grep -q "./backlog.py" CLAUDE.md AGENTS.md GEMINI.md && grep -q "Bash(./backlog.py:\*)" .claude/settings.json \
  && ! grep -q "skills_path>/bft-blueprint/scripts/bft-backlog-lint" CLAUDE.md ) \
  && ok "карта · zip: автономный проект — ./backlog.py и ./blueprint.py без установки, инструкции агенту" || fail "карта · zip: распакованный проект не автономен"

# BPMN собирается из «Процесса»: правка процесса → сборка переписывает блок mermaid
python3 - "$GOLD" <<'PY'
import sys
from pathlib import Path
f = next(Path(sys.argv[1]).glob("backlog/tasks/bp-16.1 - *.md")); t = f.read_text(encoding="utf-8")
f.write_text(t.replace("- Приложение-сканер: Показывает ответ официанту", "- Приложение-сканер: Показывает ответ официанту\n- TeamA: Пишет журнал проверок"), encoding="utf-8")
PY
python3 "$BBUILD" "$GOLD" --check >/dev/null 2>&1; rc=$?
python3 "$BBUILD" "$GOLD" --out-dir "$tmp/bout2" --no-zip >/dev/null 2>&1 \
  && [ "$rc" -eq 1 ] && grep -q '\["Пишет журнал проверок"\]' "$GOLD/backlog/tasks/bp-16.1 - "*.md \
  && python3 "$BBUILD" "$GOLD" --check >/dev/null 2>&1 \
  && ok "карта · BPMN: --check ловит устаревшую схему, сборка переписывает mermaid" || fail "карта · BPMN не пересобрался из процесса"
python3 "$BBUILD" "$tmp/bad/refs" --out-dir "$tmp/bbad" --no-source >/dev/null 2>&1; rc=$?
{ [ "$rc" -eq 1 ] && [ ! -e "$tmp/bbad" ]; } && ok "карта · сломанный проект — код 1, файлов нет" || fail "карта · сборка по сломанному проекту (rc=$rc)"

# новый проект из согласованной истории: сразу автономный
python3 "$DIR/scripts/bft-backlog-init.py" "$FIX/story_ok.md" --dir "$tmp/init" >/dev/null 2>&1 \
  && python3 "$BLINT" "$tmp/init" --no-source >/dev/null 2>&1 \
  && grep -q "BFT-BLUEPRINT START" "$tmp/init/CLAUDE.md" "$tmp/init/AGENTS.md" "$tmp/init/GEMINI.md" \
  && ( cd "$tmp/init" && python3 backlog.py doc list | grep -q "doc-2 - История" ) \
  && ok "карта · init: проект из истории, «Карта» и «История», инструкции агенту" || fail "карта · bft-backlog-init.py не собрал проект"
python3 "$DIR/scripts/bft-backlog-init.py" "$DIR/scripts/fixtures/broken_story_semantics.md" --dir "$tmp/init2" >/dev/null 2>&1; rc=$?
{ [ "$rc" -eq 1 ] && [ ! -e "$tmp/init2" ]; } && ok "карта · init: история с ошибками — проект не создаётся" || fail "карта · init по сломанной истории (rc=$rc)"

# автопилот: без --auto непросмотренная история не превращается в проект, с --auto — превращается
sed 's/^status: Согласован/status: Черновик/' "$FIX/story_ok.md" > "$tmp/draft-story.md"
python3 "$DIR/scripts/bft-backlog-init.py" "$tmp/draft-story.md" --dir "$tmp/auto0" >/dev/null 2>&1; rc=$?
python3 "$DIR/scripts/bft-backlog-init.py" "$tmp/draft-story.md" --dir "$tmp/auto1" --auto >/dev/null 2>&1 \
  && [ "$rc" -eq 1 ] && [ ! -e "$tmp/auto0" ] && [ -f "$tmp/auto1/.blueprint/templates/map.md" ] && [ -f "$tmp/auto1/.blueprint/rules/autopilot.md" ] \
  && ok "автопилот · init --auto: проект из черновика истории, шаблоны и маршрут внутри" || fail "автопилот · init --auto"
python3 "$DIR/scripts/bft-story-lint.py" "$DIR/templates/story.md" --no-source 2>&1 | grep -q " ST024 " \
  && ok "автопилот · ST024: незаполненный шаблон истории" || fail "автопилот · ST024 не ловит шаблон"

# инвентарь БФТ: все требования и разделы на месте
python3 "$DIR/scripts/bft-reqs.py" "$FIX/golden_deep_document.md" > "$tmp/reqs.md" \
  && ( for id in БТ-1 ПТ-1 ПТ-2 ИТ-1 ИТ-2 ФТ-1 ФТ-2 ФТ-3 ФТ-4 НФТ-1; do grep -q "^| $id |" "$tmp/reqs.md" || exit 1; done ) \
  && grep -q "Контент-менеджер Direct" "$tmp/reqs.md" && grep -q "Контент-менеджер → Карточка в Direct" "$tmp/reqs.md" \
  && ok "автопилот · bft-reqs: 10 требований, акторы, сценарий с участниками" || fail "автопилот · bft-reqs"
# БФТ из Word (pandoc): шапка таблицы пустая, ID с буквой группы; латинская A вместо кириллической — BL016 с подсказкой
{ cat "$FIX/golden_deep_document.md"; printf '\n|  |  |\n|---|---|\n| Идентификатор | Наименование требования |\n| ПТ-А1 | Роль А: найти договор |\n| ПТ-B2 | Роль B: сверить акт |\n'; } > "$tmp/word.md"
python3 "$DIR/scripts/bft-reqs.py" "$tmp/word.md" > "$tmp/word-reqs.md" \
  && grep -q "^| ПТ-А1 | Роль А: найти договор |" "$tmp/word-reqs.md" && grep -q "^| ПТ-B2 | Роль B: сверить акт |" "$tmp/word-reqs.md" \
  && ok "автопилот · bft-reqs: таблица из Word, ID ПТ-А1 и ПТ-B2" || fail "автопилот · bft-reqs: таблица из Word"
cp -r "$BGOLD" "$tmp/homo" && sed -i '0,/^Требования БФТ: ПТ-1, /s//Требования БФТ: ПТ-1, ПТ-A1, /' "$tmp/homo/backlog/tasks/"*.md
python3 "$DIR/scripts/bft-backlog-lint.py" "$tmp/homo" --source "$tmp/word.md" 2>&1 | grep -q "BL016.*ПТ-A1 нет в БФТ.*пишется ПТ-А1" \
  && ok "автопилот · BL016: латинская буква в ID — подсказка, как пишется в БФТ" || fail "автопилот · BL016 не видит латиницу в ID"

# план карты: экспорт эталона = образец в examples; apply того же плана ничего не меняет; с нуля — та же карта
PL="$tmp/plan"; mkdir -p "$PL" && cp -r "$BGOLD" "$PL/g" && rm -rf "$PL/g/plan"
python3 "$DIR/scripts/bft-plan.py" export "$PL/g" >/dev/null 2>&1 && diff -r "$PL/g/plan" "$DIR/examples/dineclub-restart-plan" >/dev/null \
  && ok "автопилот · export: план эталона совпадает с examples/dineclub-restart-plan" \
  || fail "автопилот · план эталона разошёлся — пересобери: bft-plan.py export (examples/dineclub-restart-plan)"
cp -r "$PL/g" "$PL/same" && python3 "$DIR/scripts/bft-plan.py" apply "$PL/same" >/dev/null 2>&1 && diff -r -x plan.applied "$PL/g" "$PL/same" >/dev/null \
  && ok "автопилот · apply того же плана — файлы не меняются" || fail "автопилот · apply не идемпотентен"
python3 "$DIR/scripts/bft-plan.py" next "$PL/same" 2>&1 | grep -q "ещё не применён" && fail "автопилот · next после apply считает план неприменённым" \
  || { sed -i '0,/^| В1 |/s/^| В1 | \([^|]*\)| \([^|]*\)|/| В1 | \1| \2(правка) |/' "$PL/same/plan/map.md"
       python3 "$DIR/scripts/bft-plan.py" next "$PL/same" 2>&1 | grep -q "ещё не применён" \
       && ok "автопилот · next: план после apply — применён; правка плана без apply — «ещё не применён»" || fail "автопилот · next не видит правку плана"; }
cp -r "$PL/g" "$PL/new" && rm -f "$PL/new/backlog/tasks/"*.md "$PL/new/backlog/docs/screens/"*.md
python3 "$DIR/scripts/bft-plan.py" apply "$PL/new" >/dev/null 2>&1; rc=$?
python3 - "$DIR/scripts" "$PL/g" "$PL/new" <<'PY' && [ "$rc" -eq 0 ] && ok "автопилот · apply с нуля: та же карта, что у эталона" || fail "автопилот · apply с нуля дал другую карту (rc=$rc)"
import importlib.util, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("b", Path(sys.argv[1]) / "bft-backlog-build.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
def m(p):
    d = b.model(b.lint.run(Path(p).resolve(), None, True))
    for x in d["tasks"] + d["cards"]:
        x.pop("file")
    for k in ("docs", "noteFiles"):
        d.pop(k)
    return d
a, c = m(sys.argv[2]), m(sys.argv[3])
assert a == c, [k for k in a if a[k] != c[k]]
PY
# ошибки формы плана: в бэклог ничего не пишется
cp -r "$PL/g" "$PL/bad" && python3 - "$PL/bad/plan/map.md" <<'PY'
import sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
t = t.replace("## BP-1 · ", "## Задача BP-1 ", 1).replace("слой: backstage", "слой: бэкенд", 1).replace("вид: создать", "вид: создать\nсрок: завтра", 1)
t += "\n## BP-77.1 · Карточка без задачи\nэтап: A\nслой: support\n\n{{суть}}\n"
open(p, "w", encoding="utf-8").write(t)
PY
before="$(cd "$PL/bad/backlog" && find . -type f -exec md5sum {} + | sort | md5sum)"
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$PL/bad" 2>&1)"; rc=$?
after="$(cd "$PL/bad/backlog" && find . -type f -exec md5sum {} + | sort | md5sum)"
( [ "$rc" -eq 1 ] && [ "$before" = "$after" ] && for c in PL002 PL003 PL004 PL007; do grep -q " $c " <<<"$out" || exit 1; done ) \
  && ok "автопилот · ошибки плана PL002 PL003 PL004 PL007 — бэклог не тронут" || fail "автопилот · ошибки плана"
# кандидаты вместо команды: страница пишет «X или Y» — это не выдумка (BL032), сборка проходит
cp -r "$PL/g" "$PL/cand" && sed -i '0,/^команда: vit$/s//кандидаты: vit, unitb/' "$PL/cand/plan/map.md" \
  && python3 "$DIR/scripts/bft-plan.py" apply "$PL/cand" >/dev/null 2>&1 \
  && python3 "$BBUILD" "$PL/cand" --no-source --no-zip --out-dir "$PL/cand-out" >/dev/null 2>&1 \
  && grep -q "Витрина или UnitB" "$PL/cand-out/dineclub-restart-map.html" \
  && ok "автопилот · кандидаты «Витрина или UnitB» — сборка проходит (BL032 не ложный)" || fail "автопилот · кандидаты валят сборку"
# ссылка на карточку посреди значения «Параметров» — страница показывает значение без неё, это не выдумка
cp -r "$PL/g" "$PL/mid" && sed -i 's/^- \*\*Выход:\*\* Частота и каналы касаний (BP-12.2)$/- **Выход:** Частота (BP-12.2) и каналы касаний/' "$PL/mid/plan/map.md" \
  && grep -q "Частота (BP-12.2) и каналы касаний" "$PL/mid/plan/map.md" \
  && python3 "$DIR/scripts/bft-plan.py" apply "$PL/mid" >/dev/null 2>&1 \
  && python3 "$BBUILD" "$PL/mid" --no-source --no-zip --out-dir "$PL/mid-out" >/dev/null 2>&1 \
  && ok "автопилот · ссылка (BP-x.y) посреди значения — сборка проходит" || fail "автопилот · ссылка посреди значения валит сборку (BL032)"
# BL033: история от лица команды-исполнителя
cp -r "$PL/g" "$PL/role" && sed -i '0,/^Как официант, я хочу получать ответ/s//Как команда TeamA, я хочу получать ответ/' "$PL/role/plan/map.md" \
  && python3 "$DIR/scripts/bft-plan.py" apply "$PL/role" 2>&1 | grep -q " BL033 BP-16.1" \
  && ok "автопилот · BL033: UserStory от лица исполнителя, адрес — строка плана" || fail "автопилот · BL033"

# стыки: документ «Стыки» в эталоне проходит строго; поломанные копии дают SM001/SM003/SM005; без стыков этап не включается
expect_bl "стыки · эталон со «Стыками» проходит строго" 0 "$BGOLD" "" --no-source --strict
SE="$tmp/seams" && mkdir -p "$SE" && cp -r "$BGOLD" "$SE/p"
python3 - "$SE/p" <<'PY'
import re, sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
t = d.read_text(encoding="utf-8")
# смысл: обязательство от команды, которой нет ни в одном стыке; контракт на несуществующий стык
t = t.replace("| D2 | teama |", "| D2 | nonexistent |", 1)
t = t.replace("| S2 | Результаты проверок за день |", "| S99 | Результаты проверок за день |", 1)
d.write_text(t, encoding="utf-8")
PY
expect_bl "стыки · смысл: обязательство мимо стыка, контракт без стыка" 1 "$SE/p" "SM003" --no-source
python3 - "$SE/p" <<'PY'
import sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
t = d.read_text(encoding="utf-8")
# форма: не тот заголовок таблицы участников
t = t.replace("| ID | Стык | Поставщик | Потребитель | Ответственный за контракт |", "| ID | Тип стыка | Кто | Кому | Владелец |", 1)
d.write_text(t, encoding="utf-8")
PY
expect_bl "стыки · форма: не тот заголовок" 1 "$SE/p" "SM001" --no-source
cp -r "$BGOLD" "$SE/w" && python3 - "$SE/w" <<'PY'
import sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
t = d.read_text(encoding="utf-8")
# стык без обязательств: убираем D4 (единственное для S3)
lines = [ln for ln in t.split("\n") if not ln.startswith("| D4 |")]
d.write_text("\n".join(lines), encoding="utf-8")
PY
expect_bl "стыки · предупреждения SM005" 1 "$SE/w" "SM005" --no-source --strict
cp -r "$BGOLD" "$SE/none" && python3 - "$SE/none" <<'PY'
import sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
d.unlink()
PY
expect_bl "стыки · без документа — предупреждение включения" 1 "$SE/none" "SM005" --no-source --strict
# одна команда без стыков: этап не включается, предупреждения нет (фикстура backlog_ok — 2 команды, там SM005 не должен мешать)
cp -r "$BOK" "$SE/one" && python3 - "$SE/one" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
for f in (p / "backlog/tasks").glob("bp-2*.md"):
    t = f.read_text(encoding="utf-8").replace("'@rest'", "'@web'")
    f.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$SE/one" --no-source 2>&1)"; rc=$?
{ [ "$rc" -eq 0 ] && ! grep -q "SM005" <<<"$out"; } && ok "стыки · одна команда — этап не включается, тишина" || fail "стыки · одна команда даёт SM005"
# apply с планом со «Стыками» восстанавливает удалённый документ — включение этапа идёт через план
cp -r "$BGOLD" "$SE/restore" && python3 - "$SE/restore" <<'PY'
import sys
from pathlib import Path
next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md")).unlink()
PY
python3 "$DIR/scripts/bft-plan.py" apply "$SE/restore" >/dev/null 2>&1 \
  && python3 "$BLINT" "$SE/restore" --no-source --strict >/dev/null 2>&1 \
  && grep -q "| S1 | fe-be | teama | vit |" "$SE/restore"/backlog/docs/doc-17*.md \
  && ok "стыки · apply восстанавливает удалённый документ" || fail "стыки · apply не вернул документ «Стыки»"
# все типы стыков: FE↔BE, BE↔BE, BE↔Infra, внешний — эталон с be-infra проходит строго
cp -r "$BGOLD" "$SE/infra" && python3 - "$SE/infra" <<'PY'
import sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
d.write_text(d.read_text(encoding="utf-8").replace("| S2 | be-be |", "| S2 | be-infra |", 1), encoding="utf-8")
PY
expect_bl "стыки · типы fe-be/be-infra/be-be/внешний" 0 "$SE/infra" "" --no-source --strict
# нет раздела — не та структура: без «Контрольных точек» документ не проходит
cp -r "$BGOLD" "$SE/nosec" && python3 - "$SE/nosec" <<'PY'
import re, sys
from pathlib import Path
d = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
d.write_text(re.sub(r"^## Контрольные точки\n.*?(?=^## )", "", d.read_text(encoding="utf-8"),
                    count=1, flags=re.S | re.M), encoding="utf-8")
PY
expect_bl "стыки · нет раздела «Контрольные точки»" 1 "$SE/nosec" "SM001" --no-source
# второй документ «Стыки» в проекте — SM002
cp -r "$BGOLD" "$SE/dup" && python3 - "$SE/dup" <<'PY'
import sys
from pathlib import Path
src = next(Path(sys.argv[1]).glob("backlog/docs/doc-* - Стыки.md"))
(src.parent / "doc-60 - Стыки.md").write_text(
    src.read_text(encoding="utf-8").replace("id: doc-17", "id: doc-60", 1), encoding="utf-8")
PY
expect_bl "стыки · второй документ «Стыки»" 1 "$SE/dup" "SM002" --no-source
# открытые вопросы этапа: «Где» = ID стыка — валидно и доходит до страницы; несуществующий стык — BL010
cp -r "$BGOLD" "$SE/q" && python3 - "$SE/q" <<'PY'
import sys
from pathlib import Path
m = next(Path(sys.argv[1]).glob("backlog/docs/doc-1 - Карта.md"))
lines = m.read_text(encoding="utf-8").split("\n")
last = max(i for i, ln in enumerate(lines) if ln.startswith("| В") and " | " in ln)
lines.insert(last + 1, "| В33 | PO | Кто отвечает за контракт стыка S1 | S1 | вопрос | — |")
m.write_text("\n".join(lines), encoding="utf-8")
PY
expect_bl "стыки · вопрос со «Где» = стык проходит строго" 0 "$SE/q" "" --no-source --strict
cp -r "$SE/q" "$SE/qbad" && sed -i 's/| S1 | вопрос | — |/| S99 | вопрос | — |/' "$SE/qbad"/backlog/docs/doc-1*.md
expect_bl "стыки · «Где» = несуществующий стык" 1 "$SE/qbad" "BL010" --no-source
# структура вывода: панель «Стыки» на странице — участники, обязательства, контракты, точки, риски и вопрос стыка
python3 "$BBUILD" "$SE/q" --no-source --no-zip --out-dir "$SE/q-out" >/dev/null 2>&1 \
  && python3 - "$SE/q-out/dineclub-restart-map.html" <<'PY' && ok "стыки · страница: панель со всеми таблицами и вопросом стыка" || fail "стыки · панель «Стыки» на странице не та"
import json, re, sys
page = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
s = d["seams"]
assert [i["id"] for i in s["items"]] == ["S1", "S2", "S3", "S4"], s["items"]
assert {i["kind"] for i in s["items"]} <= {"fe-be", "be-be", "be-infra", "внешний"}
assert len(s["deliveries"]) == 4 and len(s["contracts"]) == 5, (len(s["deliveries"]), len(s["contracts"]))
assert len(s["checkpoints"]) == 2 and len(s["risks"]) == 2
assert s["status"] == "Черновик" and s["file"].endswith("Стыки.md")
q = [x for x in d["questions"] if x["id"] == "В33"]
assert q and q[0]["where"] == "S1" and q[0]["open"], q
PY
# без стыков страница не получает панель: этап не включился — на выходе его нет
python3 "$BBUILD" "$SE/one" --no-source --no-zip --out-dir "$SE/one-out" >/dev/null 2>&1 \
  && python3 - "$SE/one-out/demo-story-map.html" <<'PY' && ok "стыки · без стыков панели на странице нет" || fail "стыки · панель без стыков не спрятана"
import json, re, sys
page = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
assert not (d.get("seams") or {}).get("items"), d.get("seams")
PY

# качество: процесс о работе над проектом (BL034), один кандидат (BL035), «Когда» с заглавной (BL030)
cp -r "$PL/g" "$PL/qual" && python3 - "$PL/qual/plan/map.md" <<'PY'
import sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
t = t.replace("- TeamA: Проверяет: активен, не использован, ≤7 дней", "- СА: Проверяет: активен, не использован, ≤7 дней", 1)
t = t.replace("команда: vit", "кандидаты: vit", 1)
t = t.replace("- Когда приходит штрихкод", "- Когда Приходит штрихкод", 1)
open(p, "w", encoding="utf-8").write(t)
PY
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$PL/qual" 2>&1)"
( for c in "BL034 BP-16.1" "BL035" "BL030 BP-16.1"; do grep -q " $c" <<<"$out" || exit 1; done ) \
  && ok "автопилот · BL034 СА в процессе, BL035 один кандидат, BL030 «Когда» с заглавной" || fail "автопилот · проверки качества карты"
sed 's/^| guest | Гость Acme Tickets |/| guest | Гость, кассир и администратор |/' "$DIR/examples/golden_story.md" > "$tmp/merged-story.md"
python3 "$DIR/scripts/bft-story-lint.py" "$tmp/merged-story.md" --no-source 2>&1 | grep -q " ST025 " \
  && ok "автопилот · ST025: персонаж из нескольких ролей" || fail "автопилот · ST025"

# граф требований и каркас: роли, буквенные ID, параметры матрицы, инварианты, разрывы, критерии приёмки
RF="$FIX/roles_deep_document.md"; SK="$tmp/sk" && mkdir -p "$SK" && cp "$RF" "$SK/" && cp "$FIX/roles_story.md" "$SK/club-partners-story.md"
python3 "$DIR/scripts/bft-reqs.py" "$RF" --json > "$tmp/graph.json" && python3 - "$tmp/graph.json" <<'PY' \
  && ok "каркас · граф БФТ: 22 требования, роли A–C, P1–P8, I1–I4, G1–G3, матрица к ФТ-2" || fail "каркас · граф БФТ"
import json, sys
g = json.load(open(sys.argv[1], encoding="utf-8"))
ids = {a["id"]: a for a in g["atoms"]}
assert len(ids) == 22 and ids["ПТ-B1"]["role"] == "Бухгалтер сети" and ids["ФТ-3"]["ac"].startswith("Повторная передача")
assert {k: len(v) for k, v in g["families"].items()} == {"P": 8, "I": 4, "G": 3}
assert g["matrices"][0]["applies"][0] == "ФТ-2" and len(g["matrices"][0]["columns"]) == 3
PY
python3 "$DIR/scripts/bft-story-lint.py" "$FIX/roles_story.md" --source "$RF" >/dev/null 2>&1 \
  && ok "каркас · история фикстуры без ошибок" || fail "каркас · история фикстуры с ошибками"
python3 "$DIR/scripts/bft-backlog-init.py" "$SK/club-partners-story.md" --dir "$SK/p" --auto >/dev/null 2>&1
python3 "$DIR/scripts/bft-skeleton.py" "$SK/p" >/dev/null 2>&1; M="$SK/p/plan/map.md"
( for x in БТ-1 ПТ-А1 ПТ-А3 ПТ-B1 ПТ-B2 ПТ-C2 ИТ-3 ФТ-1 ФТ-6 НФТ-1 НФТ-3 P1 P3 P8 I1 I4 G1 G3; do grep -q "$x" "$M" || exit 1; done ) \
  && grep -q "^- Повторная передача чека не создаёт вторую продажу (ФТ-3)" "$M" \
  && grep -q "^- Когда месяц закончился, хочу сформировать акты всем партнёрам одной операцией, чтобы не сводить таблицы. (ПТ-B1)" "$M" \
  && grep -q "P3 цена закупки: не применяется: агентская, комиссионная; обязателен: перепродажа" "$M" \
  && grep -qF "Управление:** Список партнёров периода, статус акта, расхождения сверки (ИТ-3)" "$M" \
  && [ -f "$SK/p/plan/screens/A1.md" ] && grep -q "^Источник: ИТ-" "$SK/p/plan/screens/A1.md" \
  && [ -z "$(python3 "$DIR/scripts/bft-plan.py" apply "$SK/p" 2>&1 | grep ERROR | grep -v PL007 | grep -v 'вид «{{')" ] \
  && ok "каркас · каждый атом и ID семейства на месте; критерии, JobStory, матрица — дословно; ошибки только {{…}}" || fail "каркас · раскладка"
cp -r "$SK/p" "$SK/f" && rm -f "$SK/f/plan/screens/"*.md && python3 - "$SK/f/plan/map.md" <<'PY'
import re, sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
t = re.sub(r"^вид: \{\{.*\}\}$", "вид: создать", t, flags=re.M)
t = re.sub(r"^этап: \{\{.*\}\}$", "этап: D", t, flags=re.M)
t = re.sub(r"^- \{\{4–10 шагов.*\}\}$", "- Менеджер партнёров: Открывает профиль\n- ? Данные полные\n  - да → Система продаж: Сохраняет профиль\n  - нет → конец\n- Менеджер партнёров: Видит результат", t, flags=re.M)
t = re.sub(r"^- \{\{исключение.*\}\}\n", "", t, flags=re.M)
# план релиза: перечисления (тип, статус) — допустимыми значениями, остальное — как обычно
t = t.replace("{{согласование / задача devops / предоставление доступа или данных / утверждение / проверка}}", "проверка")
t = re.sub(r"\{\{тип шага\}\}", "проверка", t)
t = t.replace("{{не начат / в работе / готово / требует ответа}}", "не начат")
t = re.sub(r"\{\{статус\}\}", "не начат", t)
t = re.sub(r"\{\{[^}]*\}\}", "работа сервиса", t)
open(p, "w", encoding="utf-8").write(t)
PY
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$SK/f" 2>&1)"
! grep -q " ERROR " <<<"$out" && ! grep -qE "BL03[678]" <<<"$out" \
  && ok "каркас · заполненный каркас проходит apply: готовое из БФТ не ломает правил" || fail "каркас · заполненный каркас с ошибками"
cp -r "$SK/f" "$SK/gate" && sed -i 's/, ПТ-C2//g; s/ (ПТ-C2)//g; s/P3 цена закупки[^;]*;//; s/^- Повторная передача чека не создаёт вторую продажу (ФТ-3)$/- Повтор не создаёт продажу (ФТ-3)/' "$SK/gate/plan/map.md"
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$SK/gate" 2>&1)"
grep -q "BL036 .*ПТ-C2" <<<"$out" && grep -q "BL037 .*P3" <<<"$out" && grep -q "WARN BL038 .*ФТ-3" <<<"$out" \
  && ok "каркас · BL036 роль без истории, BL037 параметр не на карте, BL038 критерий не перенесён" || fail "каркас · гейты BL036–BL038"
# пакеты заполнения: по блоку с {{…}}; слияние берёт заполненный блок и отклоняет потерю параметра
python3 "$DIR/scripts/bft-groom.py" fill "$SK/p" >/dev/null 2>&1; FO="$SK/p/groom/0-fill/out"
n_pk=$(ls "$SK/p/groom/0-fill"/f-*.md | wc -l); n_bl=$(grep -c "^## BP-" "$M")
fblk() { awk -v h="^## $1 " '$0 ~ h {f=1; print; next} f && /^## / {exit} f' "$SK/f/plan/map.md"; }
{ printf '## Замены\n'; fblk BP-1.1; } > "$FO/f-BP-1.1.md"
{ printf '## Вопросы\n| Кому | Вопрос | Где | Тип |\n| --- | --- | --- | --- |\n| PO | Кто подтверждает договор партнёра перед активацией? | BP-2.1 | вопрос |\n| PO | Кто подтверждает договор партнёра до активации профиля? | BP-2.1 | вопрос |\n\n## Замены\n'; fblk BP-2.1; } > "$FO/f-BP-2.1.md"
{ printf '## Замены\n'; fblk BP-5.1 | sed 's/P3 цена закупки[^;]*;//'; } > "$FO/f-BP-5.1.md"
{ printf '## Замены\n'; fblk BP-6.1; } > "$FO/f-BP-6.1.md"   # ответ без «Вопросов»: заготовка вопроса G2 не теряется
python3 "$DIR/scripts/bft-groom.py" merge "$SK/p" fill >/dev/null 2>&1
[ "$n_pk" -eq "$n_bl" ] && grep -q "^- BP-1.1 ← f-BP-1.1.md" "$SK/p/groom/report.md" && grep -q "^- BP-2.1 ← f-BP-2.1.md" "$SK/p/groom/report.md" && grep -q "BP-5.1 из f-BP-5.1.md: теряет P3" "$SK/p/groom/report.md" \
  && grep -q "Осталось незаполненным" "$SK/p/groom/report.md" && ! awk '/^## BP-1.1 /{f=1;next} f&&/^## /{exit} f' "$M" | grep -q "{{" \
  && [ "$(grep -c 'Кто подтверждает договор партнёра' "$M")" -eq 1 ] \
  && grep -q "^| В[0-9]* | PO | Уточнить: Партнёры-банки передают продажи раз в сутки пакетом.*| BP-6.1 |" "$M" && grep -q "Вопросы-заготовки без ответа" "$SK/p/groom/report.md" \
  && ok "каркас · groom fill: пакет на блок; merge fill берёт заполненный блок, потерю P3 отклоняет, повтор вопроса — одной строкой, вопрос без ответа сохраняет" || fail "каркас · groom fill/merge fill"
cp -r "$SK/f" "$SK/cand" && sed -i '0,/^команда: sales$/s//команда: кандидаты: sales, cat/' "$SK/cand/plan/map.md"
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$SK/cand" 2>&1)"
! grep -qE "PL003|BL006" <<<"$out" && grep -rq "кандидат:cat" "$SK/cand/backlog/tasks" \
  && ok "план · «команда: кандидаты: a, b» читается как кандидаты" || fail "план · «команда: кандидаты:»"

# план релиза: round-trip — разделы «Релиз» и «Ворота релиза» через apply/export, идемпотентность, гейты RL
RP="$tmp/release" && cp -r "$BOK" "$RP"
python3 "$DIR/scripts/bft-plan.py" export "$RP" --force >/dev/null 2>&1
cat >> "$RP/plan/map.md" <<'RL'

## Релиз

| ID | Стенд | Что сделать | Ответственный | Тип | Зависимости | Статус | Критерий готовности |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | dev | Собрать ветку и прогнать юнит-тесты | Команда разработки | проверка | — | готово | Тесты зелёные, сборка без ошибок |
| R2 | dev | Поднять стенд DEV с новой версией | DevOps | задача devops | R1 | в работе | Сервис отвечает на health-check |
| R3 | stage | Выдать тестовые данные и доступы тестировщикам | DevOps | предоставление доступа или данных | R2 | не начат | Тестировщик вошёл и видит данные |
| R4 | stage | Прогнать регресс на STAGE | QA | проверка | R3 | не начат | Регресс пройден, дефектов P0-P1 нет |
| R5 | prod | Согласовать окно релиза с бизнесом | PO | согласование | R4 | требует ответа | Окно утверждено, уведомления отправлены |
| R6 | prod | Выложить релиз в PROD | DevOps | задача devops | R5 | не начат | Версия в PROD, метрики в норме |

## Ворота релиза

| Ворота | Кто утверждает | Критерий перехода |
| --- | --- | --- |
| dev | Тимлид разработки | Тесты зелёные, стенд DEV стабилен |
| stage | Руководитель QA | Регресс пройден, остаточных дефектов нет |
RL
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$RP" 2>&1)"; rc=$?
rdoc="$(ls "$RP"/backlog/docs/doc-*План-релиза.md 2>/dev/null | head -1)"
[ "$rc" -eq 0 ] && [ -n "$rdoc" ] && grep -q "bft-release" "$rdoc" && grep -q "Тимлид разработки" "$rdoc" \
  && ok "план · релиз: apply создаёт документ «План релиза» (DEV/STAGE/PROD, ворота)" || fail "план · релиз: apply ($rc)"
python3 "$DIR/scripts/bft-plan.py" export "$RP" --force >/dev/null 2>&1
grep -q "^## Релиз$" "$RP/plan/map.md" && grep -q "^## Ворота релиза$" "$RP/plan/map.md" && grep -q "^| R6 | prod |" "$RP/plan/map.md" \
  && ok "план · релиз: export возвращает разделы в план" || fail "план · релиз: export потерял разделы"
before="$(cd "$RP" && find . -type f -name '*.md' -exec md5sum {} + | sort | md5sum)"
python3 "$DIR/scripts/bft-plan.py" apply "$RP" >/dev/null 2>&1
after="$(cd "$RP" && find . -type f -name '*.md' -exec md5sum {} + | sort | md5sum)"
[ "$before" = "$after" ] && ok "план · релиз: повторный apply идемпотентен" || fail "план · релиз: apply не идемпотентен"
python3 - "$rdoc" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text(encoding="utf-8")
t = t.replace("задача devops | R1 | в работе", "задача devops | R77 | в работе")
t = t.replace("| stage | Руководитель QA | Регресс пройден, остаточных дефектов нет |",
              "| stage | Руководитель QA | Регресс пройден |\n| stage | PO | Ещё одни ворота |")
p.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$RP" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "RL003.*R77" <<<"$out" && grep -q "RL003.*ворот после STAGE" <<<"$out" \
  && ok "план · релиз: RL003 — битая зависимость и дубль ворот" || fail "план · релиз: гейты RL003 ($rc)"

# экран «Релиз» в меню карты: страница с планом релиза — слой с дорожками, шагами и воротами
# (документ $RP сломан проверкой RL003 выше — пересобираем чистый план из демо)
RP="$tmp/release-ui" && cp -r "$BOK" "$RP"
python3 "$DIR/scripts/bft-plan.py" export "$RP" --force >/dev/null 2>&1
cat >> "$RP/plan/map.md" <<'RL'

## Релиз

| ID | Стенд | Что сделать | Ответственный | Тип | Зависимости | Статус | Критерий готовности |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | dev | Собрать ветку и прогнать юнит-тесты | Команда разработки | проверка | — | готово | Тесты зелёные, сборка без ошибок |
| R2 | dev | Поднять стенд DEV с новой версией | DevOps | задача devops | R1 | в работе | Сервис отвечает на health-check |
| R3 | stage | Выдать тестовые данные и доступы тестировщикам | DevOps | предоставление доступа или данных | R2 | не начат | Тестировщик вошёл и видит данные |
| R4 | stage | Прогнать регресс на STAGE | QA | проверка | R3 | не начат | Регресс пройден, дефектов P0-P1 нет |
| R5 | prod | Согласовать окно релиза с бизнесом | PO | согласование | R4 | требует ответа | Окно утверждено, уведомления отправлены |
| R6 | prod | Выложить релиз в PROD | DevOps | задача devops | R5 | не начат | Версия в PROD, метрики в норме |

## Ворота релиза

| Ворота | Кто утверждает | Критерий перехода |
| --- | --- | --- |
| dev | Тимлид разработки | Тесты зелёные, стенд DEV стабилен |
| stage | Руководитель QA | Регресс пройден, остаточных дефектов нет |
RL
python3 "$DIR/scripts/bft-plan.py" apply "$RP" >/dev/null 2>&1
python3 "$BBUILD" "$RP" --no-source --no-zip --out-dir "$tmp/rlout" >/dev/null 2>&1
python3 - "$tmp/rlout/demo-story-map.html" <<'PY' && ok "экран · релиз: слой в меню, дорожки DEV/STAGE/PROD, шаги и ворота на демо-данных" || fail "экран · релиз: страница не собрана или данных нет"
import json, re, sys
page = open(sys.argv[1], encoding="utf-8").read()
assert '<button data-view="rel">Релиз</button>' in page and 'data-rlmenu' in page and 'id="rel"' in page
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
r = d["release"]
assert r["doc"] and [t["id"] for t in r["tracks"]] == ["dev", "stage", "prod"]
assert len(r["steps"]) == 6 and r["steps"][0]["id"] == "R1" and r["steps"][-1]["track"] == "prod"
assert {s["kind"] for s in r["steps"]} >= {"проверка", "задача devops", "согласование"}
assert r["steps"][4]["status"] == "требует ответа"
assert [g["frm"] for g in r["gates"]] == ["dev", "stage"] and r["gates"][1]["who"] == "Руководитель QA"
PY
python3 - "$DIR/scripts" "$RP" "$tmp/rlout/demo-story-map.html" <<'PY' && ok "экран · релиз: текст слоя — только из проекта (BL032)" || fail "экран · релиз: BL032 не проходит"
import importlib.util, json, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("b", Path(sys.argv[1]) / "bft-backlog-build.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
pr = b.lint.run(Path(sys.argv[2]).resolve(), None, True)
assert b.provenance(b.model(pr), pr) == []
PY
# без документа «План релиза» кнопки и слоя на странице нет — эталон без релиза не меняется
python3 - "$DIR/scripts" "$BGOLD" <<'PY' && ok "экран · релиз: без плана релиза слой не появляется" || fail "экран · релиз: слой протекает без документа"
import importlib.util, json, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
spec = importlib.util.spec_from_file_location("b", Path(sys.argv[1]) / "bft-backlog-build.py"); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
pr = b.lint.run(Path(sys.argv[2]).resolve(), None, True)
page = b.render(pr, "")
# литералы кнопок порождает сборка; в тексте map_page.js селекторы есть всегда
assert 'data-view="rel">Релиз' not in page and 'class="mi" data-rlmenu' not in page
m = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
assert "release" not in m
PY

# навык · release-plan: эталоны примеров — разделы эталона проходят apply/lint схемы Delivery,
# известное взято из входа, неизвестное — [УТОЧНИТЬ] + «требует ответа» + вопрос; вход без данных — только вопросы
RLS="$tmp/release-plan-skill" && rm -rf "$RLS"
cp -r "$BOK" "$RLS"
python3 "$DIR/scripts/bft-plan.py" export "$RLS" --force >/dev/null 2>&1
# вырезаем из экспорта старые разделы релиза и вставляем разделы эталона навыка
python3 - "$RLS/plan/map.md" "$DIR/../release-plan/examples/release-plan-output.md" <<'PY'
import re, sys
plan, golden = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
rel = re.search(r"## Релиз\n.*?\n(?=^## |\Z)", golden, re.S | re.M).group(0)
gates = re.search(r"## Ворота релиза\n.*?\n(?=^## |\Z)", golden, re.S | re.M).group(0)
plan = re.sub(r"\n## Релиз\n.*?(?=^## |\Z)", "\n", plan, flags=re.S | re.M)
plan = re.sub(r"\n## Ворота релиза\n.*?(?=^## |\Z)", "\n", plan, flags=re.S | re.M)
plan = plan.rstrip("\n") + "\n\n" + rel.rstrip("\n") + "\n\n" + gates.strip() + "\n"
open(sys.argv[1], "w", encoding="utf-8").write(plan)
PY
out="$(python3 "$DIR/scripts/bft-plan.py" apply "$RLS" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && ! grep -qE " ERROR " <<<"$out" \
  && ok "навык · release-plan: эталон валиден схемой (apply без ошибок)" || fail "навык · release-plan: apply эталона ($rc)"
rdoc="$(ls "$RLS"/backlog/docs/doc-*План-релиза.md 2>/dev/null | head -1)"
out="$(python3 "$BLINT" "$RLS" --no-source 2>&1)"; rc=$?
n_rl="$(grep -c "RL00" <<<"$out" || true)"
[ "$rc" -eq 0 ] && [ -n "$rdoc" ] && [ "$n_rl" -eq 0 ] \
  && ok "навык · release-plan: линтер схемы — 0 ошибок RL по эталону" || fail "навык · release-plan: линтер RL по эталону ($rc, RL=$n_rl)"
python3 - "$DIR/../release-plan/examples/release-plan-output.md" <<'PY' && ok "навык · release-plan: честность — известное из входа, неизвестное «требует ответа» с вопросом" || fail "навык · release-plan: контракт честности нарушен"
import re, sys
g = open(sys.argv[1], encoding="utf-8").read()
rows = re.findall(r"^\| R\d+ \|.*\|$", g, re.M)
assert rows, "нет шагов"
for r in rows:
    c = [x.strip() for x in r.strip("|").split("|")]
    owner, status = c[3], c[6]
    if "[УТОЧНИТЬ" in owner:
        assert status == "требует ответа", f"{c[0]}: пометка без статуса"
    assert status in ("не начат", "в работе", "готово", "требует ответа"), f"{c[0]}: статус {status}"
qs = re.findall(r"^\d+\. (.*?) \(.*(R\d+|ворота.*?)\)$", g.split("## Вопросы")[1], re.M)
assert qs, "нет вопросов"
ids = {m.group(1) for m in (re.match(r"^\| (R\d+) \|", r) for r in rows) if m}
for q, ref in qs:
    assert ref == "ворота stage" or ref in ids, f"вопрос ведёт в никуда: {ref}"
gates = re.search(r"## Ворота релиза.*", g, re.S).group(0)
assert "[УТОЧНИТЬ" in gates, "ворота без пометки при неизвестном утверждающем"
for m in re.finditer(r"\[УТОЧНИТЬ[^\]]*\]", g):
    assert "Вопросы" in g, "нет блока вопросов"
# каждый «требует ответа» покрыт вопросом с тем же R-ID
for r in rows:
    c = [x.strip() for x in r.strip("|").split("|")]
    if c[6] == "требует ответа":
        assert f"({c[0]})" in g.split("## Вопросы")[1], f"{c[0]}: статус без вопроса"
PY
sparse="$DIR/../release-plan/examples/release-plan-sparse-output.md"
! grep -q "^## Релиз" "$sparse" && ! grep -q "^## Ворота релиза" "$sparse" && grep -q "^## Вопросы" "$sparse" && grep -cq "^[0-9]\+\. " "$sparse" \
  && ok "навык · release-plan: вход без данных — только вопросы, плана нет" || fail "навык · release-plan: разреженный вход собрал план"
# регистрация: команда и скилл ставятся установщиком
[ -f "$DIR/../release-plan/SKILL.md" ] && [ -f "$DIR/../../commands/release-plan.md" ] && grep -q "release-plan" install.sh \
  && ok "навык · release-plan: скилл, команда и install.sh на месте" || fail "навык · release-plan: регистрация неполна"

# груминг роем: пакеты обеих волн; слияние берёт годную замену, а ломающую карту и теряющую требование — отклоняет
GR="$tmp/groom" && cp -r "$BGOLD" "$GR" && rm -rf "$GR/plan"
python3 "$DIR/scripts/bft-groom.py" audit "$GR" >/dev/null 2>&1 && python3 "$DIR/scripts/bft-groom.py" refine "$GR" >/dev/null 2>&1
O="$GR/groom/2-refine/out" && mkdir -p "$O"
blk() { awk -v h="^## $1 " '$0 ~ h {f=1; print; next} f && /^## / {exit} f' "$GR/plan/map.md"; }
{ printf '## Вопросы\n| Кому | Вопрос | Где | Тип |\n| --- | --- | --- | --- |\n| PO | Кто проверяет заявку ресторана? | BP-1.1 | вопрос |\n\n## Замены\n'
  blk BP-1.1 | sed '1s/.*/## BP-1.1 · Ресторан подаёт заявку и попадает в каталог/'; } > "$O/r-BP-1.1.md"
{ printf '## Замены\n'; blk BP-2 | sed 's/^Требования БФТ: ФТ-3, ФТ-4, НФТ-2/Требования БФТ: ФТ-3/'; } > "$O/r-BP-2.md"
{ printf '## Замены\n'; blk BP-2.1 | sed '/^### Процесс/,/^### HowToDemo/{/^- /d}'; } > "$O/r-BP-2.1.md"
python3 "$DIR/scripts/bft-groom.py" merge "$GR" >/dev/null 2>&1
R="$GR/groom/report.md"
[ -f "$GR/groom/1-audit/a-coverage.md" ] && ls "$GR/groom/2-refine/r-BP-1.1.md" >/dev/null \
  && grep -q "^## BP-1.1 · Ресторан подаёт заявку и попадает в каталог" "$GR/plan/map.md" && grep -q "Кто проверяет заявку ресторана?" "$GR/plan/map.md" \
  && grep -q "BP-2 из r-BP-2.md: теряет НФТ-2 — " "$R" && grep -q "BP-2.1 из r-BP-2.1.md: .*BL" "$R" \
  && ok "груминг · audit → refine → merge: годная замена и вопрос — в план, ломающие — в отчёт" || fail "груминг · audit/refine/merge"
# ID переезжает в блок, который сливается позже (r-BP-3 после r-BP-2): второй круг слияния принимает обе замены
GD="$tmp/groom2" && cp -r "$BGOLD" "$GD" && rm -rf "$GD/plan"
python3 "$DIR/scripts/bft-groom.py" audit "$GD" >/dev/null 2>&1 && python3 "$DIR/scripts/bft-groom.py" refine "$GD" >/dev/null 2>&1
OD="$GD/groom/2-refine/out" && mkdir -p "$OD"
blk2() { awk -v h="^## $1 " '$0 ~ h {f=1; print; next} f && /^## / {exit} f' "$GD/plan/map.md"; }
{ printf '## Замены\n'; blk2 BP-2 | sed 's/^Требования БФТ: ФТ-3, ФТ-4, НФТ-2/Требования БФТ: ФТ-3, ФТ-4/'; } > "$OD/r-BP-2.md"
{ printf '## Замены\n'; blk2 BP-3 | sed 's/^\(Требования БФТ: .*\)$/\1, НФТ-2/'; } > "$OD/r-BP-3.md"
python3 "$DIR/scripts/bft-groom.py" merge "$GD" >/dev/null 2>&1
grep -q "^- BP-2 ← r-BP-2.md" "$GD/groom/report.md" && grep -q "^- BP-3 ← r-BP-3.md" "$GD/groom/report.md" \
  && ok "груминг · ID переехал в блок, слитый позже, — второй круг принимает замену" || fail "груминг · отложенная замена"
( cd "$GD" && ./backlog.py task archive BP-19.1 >/dev/null && [ -f backlog/archive/tasks/bp-19.1*.md ] && ! ./backlog.py task list --plain | grep -q "BP-19.1" ) \
  && ok "CLI · task archive убирает карточку в backlog/archive/tasks" || fail "CLI · task archive"

# слой employee: официант на виду у гостя в слое technology — BL041
EM="$tmp/emp" && cp -r "$BGOLD" "$EM" && sed -i 's/^  - layer:employee$/  - layer:technology/' "$EM/backlog/tasks/bp-15.1 "*.md
python3 "$DIR/scripts/bft-backlog-lint.py" "$EM" --no-source 2>&1 | grep -q "WARN BL041 BP-15.1" \
  && ! python3 "$DIR/scripts/bft-backlog-lint.py" "$BGOLD" --no-source 2>&1 | grep -q BL041 \
  && ok "карта · BL041: сотрудник на виду у клиента в technology — подсказка employee" || fail "карта · BL041"

# каркас на других БФТ: экран другого этапа — своя задача; сотрудник на виду у клиента — employee
LY="$tmp/ly" && mkdir -p "$LY/faq" "$LY/car"
cp "$FIX/golden_deep_document.md" "$LY/faq/direct-faq.md" && cp "$FIX/faq_story.md" "$LY/faq/direct-faq-story.md"
cp "$FIX/car_deep_document.md" "$LY/car/car-service-booking.md" && cp "$FIX/car_story.md" "$LY/car/car-service-booking-story.md"
for x in faq/direct-faq car/car-service-booking; do
  python3 "$DIR/scripts/bft-backlog-init.py" "$LY/$x-story.md" --dir "$LY/$x-p" --auto >/dev/null 2>&1; python3 "$DIR/scripts/bft-skeleton.py" "$LY/$x-p" >/dev/null 2>&1
done
FM="$LY/faq/direct-faq-p/plan/map.md"; CM="$LY/car/car-service-booking-p/plan/map.md"
! grep "^Требования БФТ:" "$FM" | grep -q "ИТ-1.*ИТ-2\|ИТ-2.*ИТ-1" \
  && [ "$(grep -c '^слой: employee' "$CM")" -eq 1 ] && grep -A1 "^слой: employee" "$CM" | grep -q "^экраны: D1" \
  && ! grep -B3 "^слой: employee" "$FM" | grep -q employee \
  && grep -A1 "^## BP-[0-9]* · Задержка публикации изменений" "$FM" | grep -q "^этап: B" \
  && ok "каркас · экраны разных этапов — в разных задачах; этап без задачи получает задачу своего требования; мастер-приёмщик при клиенте — employee, экран клиента — technology" || fail "каркас · раскладка по этапам и employee"
tm() { awk -v h="^## $1 " '$0 ~ h {f=1; next} f && /^команда: / {print $2; exit} f && /^## / {exit}' "$CM"; }
[ "$(tm BP-2)" = int ] && [ "$(tm BP-3)" = int ] && [ "$(tm BP-10)" = pay ] && [ "$(tm BP-13)" = loy ] && [ "$(tm BP-1)" = loy ] \
  && [ "$(grep -c '^кандидаты:' "$SK/p/plan/map.md")" -eq 0 ] \
  && ok "каркас · команда по «Зависимостям»: редкое слово весит больше общего, окончания не мешают" || fail "каркас · подбор команды"

# контракты стыков (Design First): эталон строго чист, на сломанной копии — каждый код CT
CTL="$DIR/scripts/bft-contracts.py"
python3 "$CTL" lint "$BGOLD" --strict >/dev/null 2>&1 \
  && ok "контракты · эталон DineClub: 7 контрактов, 0 ошибок и предупреждений" || fail "контракты · эталон не проходит --strict"
( cd "$BGOLD" && ./blueprint.py contracts >/dev/null 2>&1 ) && ok "контракты · ./blueprint.py contracts" || fail "контракты · ./blueprint.py contracts"
CB="$tmp/ct" && cp -r "$BGOLD" "$CB" && C="$CB/contracts"
sed -i 's/^boundary: external/boundary: outer/; s/| barcode | string | да | path | ФТ-1, извне: штрихкод с билета Acme Tickets |/| bar code | string | да | path | |/; s/"discount": 10, //; /TeamA --> Приложение-сканер/d; s/| 1 | Acme Tickets | barcode |/| 1 | Acme Tickets | ticket_no |/' "$C/C-3.md"
sed -i 's/штрихкод, ресторан/PRIMARY KEY штрихкод, ресторан/; s/^cards: .*/cards: BP-99.1/' "$C/C-5.md"
sed -i 's|^op: .*|op: GET /v1/restaurants/{rid}|; s/"walk_minutes": 6/"walk_minutes": "шесть минут пешком от площадки (ИТ-4)"/; s/^caller: Витрина$/caller: Каталог UnitB/; s/^callee: Каталог UnitB$/callee: Витрина/' "$C/C-2.md"
sed -i 's/ФТ-19, извне: ID партнёра в DineClub/ФТ-19/' "$C/C-6.md"
sed -i '/^## Цепочка/,$d; s/^cards: .*/cards: BP-17.1/' "$C/C-4.md"
sed -i '/^## Ошибки/,/^## Sequence/{/^| 4/d}' "$C/C-2.md"
sed -i 's/^| Хранилище | Какие данные нужны | Источник |/| Хранилище | Данные | Источник |/' "$C/C-5.md"
cp "$C/C-1.md" "$C/C-7.md"
out="$(python3 "$CTL" lint "$CB" --source "$FIX/golden_deep_document.md" 2>&1)"; rc=$?
miss=""; for c in CT001 CT002 CT003 CT004 CT005 CT006 CT007 CT008 CT009 CT010 CT012 CT014 CT015 CT020 CT021 CT022; do grep -q " $c " <<<"$out" || miss="$miss $c"; done
[ "$rc" -eq 1 ] && [ -z "$miss" ] && ok "контракты · сломанная копия: CT001–CT015, CT020–CT022" || fail "контракты · нет в выводе:$miss (rc=$rc)"
# каркас: стык без контракта (C-6 убран) → CT020; skeleton заводит C-8 на ту же пару карточек, незаполненный — только CT011
CS="$tmp/cts" && cp -r "$BGOLD" "$CS" && rm "$CS/contracts/C-6.md"
out1="$(python3 "$CTL" lint "$CS" 2>&1)"; python3 "$CTL" skeleton "$CS" >/dev/null 2>&1; out2="$(python3 "$CTL" lint "$CS" 2>&1)"
grep -q "WARN CT020 BP-1.1 → BP-2.1" <<<"$out1" && grep -q "^cards: BP-1.1, BP-2.1" "$CS/contracts/C-8.md" && grep -q "ERROR CT011 C-8" <<<"$out2" \
  && [ "$(grep -c " ERROR " <<<"$out2")" -eq 1 ] && ! grep -q CT020 <<<"$out2" && [ "$(ls "$CS/contracts" | wc -l)" -eq 8 ] \
  && ok "контракты · skeleton: стык без контракта → каркас C-8 с картой в шапке, незаполненный — только CT011" || fail "контракты · skeleton"
# внешний стык текстом («из внешней системы»), без карточки на той стороне: CT020 и external-каркас на эту карточку
CX="$tmp/ctx" && cp -r "$BGOLD" "$CX" && sed -i '0,/^- \*\*Вход:\*\* /s//- **Вход:** Рейтинги из внешней системы; /' "$CX/backlog/tasks/bp-9.1 "*.md
out1="$(python3 "$CTL" lint "$CX" 2>&1)"; python3 "$CTL" skeleton "$CX" >/dev/null 2>&1
grep -q "WARN CT020 BP-9.1 «Рейтинги из внешней системы»: внешний стык" <<<"$out1" && grep -q "^boundary: external" "$CX/contracts/C-8.md" && grep -q "^cards: BP-9.1$" "$CX/contracts/C-8.md" \
  && ok "контракты · внешняя система текстом во «Входе» — внешний стык и external-каркас" || fail "контракты · внешний стык текстом"
# not-seams.md: связь с причиной — не стык (CT020 молчит), строка без причины или не про стык — CT013
CW="$tmp/ctw" && cp -r "$BGOLD" "$CW" && rm "$CW/contracts/C-6.md"
printf '| Откуда | Куда | Почему не обмен данными |\n| --- | --- | --- |\n| BP-1.1 | BP-2.1 | список ресторанов DineClub передаёт UnitB вручную раз в неделю |\n| BP-4.1 | BP-7.1 | — |\n' > "$CW/contracts/not-seams.md"
out="$(python3 "$CTL" lint "$CW" 2>&1)"
! grep -q "CT020 BP-1.1 → BP-2.1" <<<"$out" && grep -q "ERROR CT013 BP-4.1 → BP-7.1" <<<"$out" \
  && ok "контракты · not-seams.md: связь с причиной — не стык, строка не про стык — CT013" || fail "контракты · not-seams.md"

# прототип по контрактам: каркас раскладывает вызовы, коды PT, сборка байт в байт, замечания → вопросы карты
PTL="$DIR/scripts/bft-proto.py"
python3 "$PTL" lint "$BGOLD" --strict >/dev/null 2>&1 && ok "прототип · эталон DineClub: план показа без ошибок и предупреждений" || fail "прототип · эталон не проходит --strict"
PB="$tmp/proto" && cp -r "$BGOLD" "$PB" && python3 "$PTL" build "$PB" >/dev/null 2>&1 \
  && diff -r "$PB/prototype" "$BGOLD/prototype" >/dev/null && [ -z "$(python3 "$PTL" build "$PB" 2>&1 | grep -v 'обновлено файлов 0' | grep 'обновлено')" ] \
  && python3 -m py_compile "$PB/prototype/api/main.py" && node --check "$PB/prototype/web/runtime.js" 2>/dev/null \
  && grep -q '"C-3"' "$PB/prototype/api/spec.json" && grep -q "image: python:3.12-slim" "$PB/prototype/docker-compose.yml" \
  && ok "прототип · сборка: web, api, docker-compose — совпадает с эталоном, повтор ничего не меняет, main.py и runtime.js компилируются" || fail "прототип · сборка"
pblk() { awk -v h="^## $1 " '$0 ~ h {f=1; print; next} f && /^## / {exit} f' "$PB/prototype/spec.md"; }
python3 "$PTL" skeleton "$PB" --force >/dev/null 2>&1
pblk Ш13 | grep -q "^вызов: C-3$" && pblk Ш13 | grep -q "^экраны: F2$" && pblk Ш13 | grep -q "^успех: F3$" && pblk Ш13 | grep -q "^отказ: F4 = TICKET_NOT_FOUND$" \
  && pblk Ш4 | grep -q "^вызов: C-1, C-2$" && pblk Ш5 | grep -q "^вызов: —$" && pblk Ш14 | grep -q "^вызов: —$" \
  && pblk C-7 | grep -q "^приложение: backend$" && [ "$(grep -n '^## C-7 ' "$PB/prototype/spec.md" | cut -d: -f1)" -lt "$(grep -n '^## Ш5 ' "$PB/prototype/spec.md" | cut -d: -f1)" ] \
  && pblk Ш15 | grep -q "^вызов: C-4$" && pblk Ш15 | grep -q "^успех: F5$" \
  && [ -z "$(grep '{{' "$PB/prototype/spec.md" | grep -v '^ввод: ')" ] \
  && ok "прототип · каркас: сканер запускает C-3 (успех F3, отказ F4), фото чека — на своём шаге, GET — на экранах данных, триггер — шаг за кадром перед результатом; модели — только значения" || fail "прототип · каркас"
cp "$BGOLD/prototype/spec.md" "$PB/prototype/spec.md"
sed -i '0,/^приложение: staff$/s//приложение: officiant/; s/^экраны: D1, D2$/экраны: D1, X9/; s/^вызов: C-4$/вызов: C-4, C-99/; s/^ввод: barcode = 4600123456789; restaurant_id = r-12; photo/ввод: barcode = 4600123456789; restaurant_id = r-12; color = red; photo/; s/^показать: receipt_id, compensation$/показать: receipt_id, compensation, price/; s/^отказ: — = RECEIPT_EXISTS$/отказ: — = NOPE/; s/^вызов: C-6$/вызов: —/' "$PB/prototype/spec.md"
printf '\n## Ш99 · Лишний шаг\nприложение: client\nприложение: client\nэкраны: —\nвызов: {{C-1 или —}}\n' >> "$PB/prototype/spec.md"
out="$(python3 "$PTL" lint "$PB" 2>&1)"; miss=""
for c in PT001 PT002 PT003 PT004 PT005 PT006 PT007 PT008 PT009 PT020; do grep -q " $c " <<<"$out" || miss="$miss $c"; done
[ -z "$miss" ] && ok "прототип · сломанный план показа: PT001–PT009, PT020" || fail "прототип · нет в выводе:$miss"
python3 - "$DIR/scripts" <<'PY' && ok "прототип · глагол шага ↔ вид операции: «Добавляю» — POST, «Переношу» — cancel, «Оплачиваю» — платёж, «запись» — не глагол" || fail "прототип · глагол шага ↔ операция"
import sys; sys.path.insert(0, sys.argv[1])
import bft_proto as b
assert b.op_kind("POST /v1/questions") == "create" and b.op_kind("PATCH /v1/questions/{id}") == "update"
assert b.op_kind("POST /v1/bookings/{ref}/cancel") == "cancel" and b.op_kind("POST /v1/invoices/{id}/payments") == "pay"
assert b.step_kinds("Добавляю вопрос на карточку") == {"create"} and "cancel" in b.step_kinds("Передумал — переношу запись")
assert "create" not in b.step_kinds("Передумал — переношу запись") and b.step_kinds("Оплачиваю счёт") == {"pay"}
PY
PR="$tmp/proto-review" && cp -r "$BGOLD" "$PR" && python3 "$DIR/scripts/bft-plan.py" export "$PR" >/dev/null 2>&1
printf '{"pins": [{"step": "Ш13", "screen": "F2", "block": "Сканировать", "text": "Кнопка мелкая для официанта", "x": 50, "y": 80}]}' > "$tmp/review.json"
python3 "$PTL" review "$PR" "$tmp/review.json" >/dev/null 2>&1 \
  && grep -q "^| В[0-9]* | PO | Кнопка мелкая для официанта (прототип Ш13, экран F2, «Сканировать») | BP-15.1 | вопрос | — |" "$PR/plan/map.md" \
  && ok "прототип · замечание по точке экрана → вопрос карты на карточке экрана" || fail "прототип · review"

# приёмка комплекта: страницы со штампом скрипта, проект с задачами, zip; рукописный HTML не принимается
VD="$tmp/verify/dineclub-restart" && mkdir -p "$VD" && cp "$SGOLD" "$VD/dineclub-restart-story.md" && cp -r "$BGOLD" "$VD/dineclub-restart-blueprint"
VF="$DIR/scripts/bft-blueprint-verify.py"
python3 "$VF" "$VD" >/dev/null 2>&1; rc1=$?
python3 "$SRENDER" "$VD/dineclub-restart-story.md" >/dev/null 2>&1 && python3 "$BBUILD" "$VD/dineclub-restart-blueprint" --no-source >/dev/null 2>&1
python3 "$VF" "$VD" >/dev/null 2>&1; rc2=$?
echo "<html>рукописная</html>" > "$VD/dineclub-restart-map.html"; python3 "$VF" "$VD" 2>&1 | grep -q "собрана не скриптом"; rc3=$?
[ "$rc1" -eq 1 ] && [ "$rc2" -eq 0 ] && [ "$rc3" -eq 0 ] \
  && ok "приёмка · без страниц и zip — отказ; собранное скриптами — принято; рукописная карта — отказ" || fail "приёмка · verify ($rc1/$rc2/$rc3)"

# встроенный CLI и настоящий Backlog.md читают файлы друг друга — если npm-пакет установлен
if command -v backlog >/dev/null 2>&1; then
  ( cd "$tmp/unz/dineclub-restart-blueprint" && [ "$(backlog task list --plain 2>/dev/null | grep -c 'BP-')" -eq 40 ] \
    && backlog task view BP-16.2 --plain 2>/dev/null | grep -q "Parent: BP-16" \
    && backlog task view BP-16 --plain 2>/dev/null | grep -q "jira.example.com" \
    && backlog task edit BP-16.2 --ac "Граница 23:59 по площадке" --check-ac 1 >/dev/null 2>&1 \
    && python3 backlog.py task view BP-16.2 --plain | grep -q "\[x\] #1 Граница 23:59" ) \
    && ok "карта · встроенный CLI и npm-пакет backlog.md читают и правят одни файлы" || fail "карта · встроенный CLI разошёлся с Backlog.md"
fi

# --- этап «ADR и Системные требования»: форма, смысл, условие включения, план, страница ------
# форма (AR001): битый паспорт, ID не V1…, пустые компромиссы — parse ловит без смысла
cp -r "$BGOLD" "$tmp/adr-bad"
python3 - "$tmp/adr-bad/backlog/docs/doc-15 - ADR.md" << 'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
t = t.replace("revised: 2026-10-22", "")                                   # AR001: нет ключа паспорта
t = t.replace("| V1 | Полка ресторанов", "| X9 | Полка ресторанов")        # AR001: ID не V1…
p.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$tmp/adr-bad" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q " AR001 " <<<"$out" \
  && ok "ADR · битая форма: AR001" || fail "ADR · битая форма не поймана"
# смысл (AR003): решение мимо вариантов, пустое «Почему нет» — check ловит на целой форме
cp -r "$BGOLD" "$tmp/adr-sense"
python3 - "$tmp/adr-sense/backlog/docs/doc-15 - ADR.md" << 'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
t = t.replace("| V1 | restaurant-shelf |", "| V7 | restaurant-shelf |")    # AR003: решение мимо вариантов
t = t.replace("| сервис не оправдан объёмом акции, к запуску не успеть |", "| — |")  # AR003: пустое «Почему нет»
p.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$tmp/adr-sense" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q " AR003 " <<<"$out" \
  && ok "ADR · смысл: AR003 (выбор мимо вариантов, пустое «Почему нет»)" || fail "ADR · смысл не пойман"
# C4 L3 (AR006): контур не из «Команд», задачи нет на карте, поток мимо компонентов, контракт не из решения
cp -r "$BGOLD" "$tmp/adr-c4"
python3 - "$tmp/adr-c4/backlog/docs/doc-15 - ADR.md" << 'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
for a, b in [("| Платформа TeamA | teama | сервис | новый | BP-16 |", "| Платформа TeamA | nobody | сервис | новый | BP-99 |"),
             ("| M8 | M9 | Отметка «использован» | запись | ticket-validation |", "| M8 | M99 | Отметка «использован» | запись | ticket-checks |")]:
    assert a in t, a; t = t.replace(a, b)
p.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$tmp/adr-c4" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && [ "$(grep -c " AR006 " <<<"$out")" -eq 4 ] \
  && ok "ADR · C4 L3: AR006 (контур, задача, поток, контракт)" || fail "ADR · C4 L3: AR006 не пойман — $out"
# C4 L3 (AR007): меняемый компонент без задачи, компонент без потока, контракт TO-BE без потока
cp -r "$BGOLD" "$tmp/adr-c4w"
python3 - "$tmp/adr-c4w/backlog/docs/doc-15 - ADR.md" << 'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
t = p.read_text(encoding="utf-8")
t = t.replace("| Каталог UnitB | unitb | хранилище | новый | BP-6 |", "| Каталог UnitB | unitb | хранилище | новый | — |")
t = re.sub(r"^\| M8 \| M9 \|.*\n", "", t, flags=re.M)
t = re.sub(r"^\| (M3|M4|M7) \| M[67] \|.*\n", "", t, flags=re.M)
p.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$tmp/adr-c4w" --no-source --strict 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "AR007 M7 «Кеш каталога 10 минут»: новый, а задачи нет" <<<"$out" && grep -q "AR007 M9 «Реестр использований»: ни одного потока" <<<"$out" \
  && grep -q "AR007 контракт «restaurant-shelf» решён, но ни один поток" <<<"$out" \
  && ok "ADR · C4 L3: AR007 (без задачи, без потока, контракт без потока)" || fail "ADR · C4 L3: AR007 не пойман — $out"
# C4 L3 на странице: таблицы ADR — в данных, схему рисует страница
python3 - "$tmp/bout" <<'PY' && ok "ADR · C4 L3 на странице: 14 компонентов, 15 потоков, схема и панель компонента" || fail "ADR · C4 L3 не дошёл до страницы"
import json, re, sys
from pathlib import Path
page = (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
c, f = d["adr"]["components"], d["adr"]["flows"]
assert len(c) == 14 and len(f) == 15, (len(c), len(f))
assert {x["team"] for x in c} >= {"vit", "unitb", "teama", "dine", "ext", "?", "—"}
assert next(x for x in c if x["id"] == "M8")["tasks"] == ["BP-16"]
assert {x["contract"] for x in f} == {"—", "restaurant-shelf", "ticket-validation"}
assert "function c4Code" in page and "function openC4" in page and "data-c4team" in page
PY
# Roadmap: форма (RM001), строки мимо карты (RM003), полнота и порядок (RM005), слой страницы
python3 - "$tmp/bout" <<'PY' && ok "Roadmap · на странице: 22 работы за 6 недель, у BP-5 — подзадачи" || fail "Roadmap · не дошёл до страницы"
import json, re, sys
from pathlib import Path
page = (Path(sys.argv[1]) / "dineclub-restart-map.html").read_text(encoding="utf-8")
d = json.loads(re.search(r'id="map-data">(.*?)</script>', page, re.S).group(1))
r = d["roadmap"]
assert r["start"] == "2026-11-02" and r["sprintWeeks"] == 1 and r["weeks"] == 6 and len(r["items"]) == 22, r
ids = {i["id"] for i in r["items"]}
assert "BP-5" not in ids and {"BP-5.2", "BP-5.3", "BP-5.4", "BP-5.5"} <= ids
assert 'data-view="road">Roadmap' in page and "function rmBoard" in page
PY
cp -r "$BGOLD" "$tmp/rm-bad"
python3 - "$tmp/rm-bad" << 'PY'
import sys
from pathlib import Path
f = next(Path(sys.argv[1], "backlog/docs").glob("doc-* - Roadmap.md"))
t = f.read_text(encoding="utf-8")
for a, b in [("start: 2026-11-02", "start: 2026-11-04"), ("| BP-18 | 5 | 6 |", "| BP-18 | 5 | 9 |")]:
    assert a in t, a; t = t.replace(a, b)
f.write_text(t, encoding="utf-8")
PY
out="$(python3 "$BLINT" "$tmp/rm-bad" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "RM001 start 2026-11-04 — понедельник" <<<"$out" && grep -q "RM001 BP-18: неделя 9 за горизонтом" <<<"$out" \
  && ok "Roadmap · форма: RM001 (не понедельник, за горизонтом)" || fail "Roadmap · RM001 не пойман — $out"
cp -r "$BGOLD" "$tmp/rm-ref" && sed -i 's/^| BP-19 | 5 | 6 |$/| BP-99 | 5 | 6 |/' "$tmp/rm-ref/backlog/docs/"*Roadmap.md
out="$(python3 "$BLINT" "$tmp/rm-ref" --no-source 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "RM003 BP-99: в Roadmap — история или подзадача карты" <<<"$out" \
  && ok "Roadmap · строка мимо карты: RM003" || fail "Roadmap · RM003 не пойман — $out"
cp -r "$BGOLD" "$tmp/rm-warn"
python3 - "$tmp/rm-warn" << 'PY'
import re, sys
from pathlib import Path
root = Path(sys.argv[1])
f = next(Path(root, "backlog/docs").glob("doc-* - Roadmap.md"))
t = f.read_text(encoding="utf-8")
t = re.sub(r"^\| BP-13 \|.*\n", "", t, flags=re.M)                     # история вне плана (Would вне плана — не ошибка)
t = re.sub(r"^\| BP-5\.5 \|.*\n", "| BP-5 | 2 | 5 |\n", t, flags=re.M)  # история с подзадачами — сама в плане
f.write_text(t, encoding="utf-8")
g = next(Path(root, "backlog/tasks").glob("bp-17 *"))                    # BP-17 зависит от BP-16, а начинается раньше её конца
g.write_text(g.read_text(encoding="utf-8").replace("dependencies: []", "dependencies:\n  - BP-16\n", 1).replace("  - BP-16\n\n", "  - BP-16\n", 1), encoding="utf-8")
PY
sed -i 's/^| BP-17 | 4 | 5 |$/| BP-17 | 3 | 5 |/' "$tmp/rm-warn/backlog/docs/"*Roadmap.md
out="$(python3 "$BLINT" "$tmp/rm-warn" --no-source --strict 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && grep -q "RM005 BP-13 «Напоминание в окне 7 дней: письмо или SMS» не в Roadmap" <<<"$out" && ! grep -q "RM005 BP-14" <<<"$out" && grep -q "RM005 BP-5: у истории подзадачи по зонам" <<<"$out" \
  && grep -q "RM005 BP-5.5 (QA) не в Roadmap" <<<"$out" && grep -q "RM005 BP-17 начинается на неделе 3, а его зависимость BP-16 кончается на неделе 3" <<<"$out" \
  && ok "Roadmap · полнота и порядок: RM005" || fail "Roadmap · RM005 не пойман — $out"
# AR002: второй ADR в проекте
cp -r "$BGOLD" "$tmp/adr-dup"
cp "$BGOLD/backlog/docs/doc-15 - ADR.md" "$tmp/adr-dup/backlog/docs/doc-50 - второй ADR.md"
sed -i 's/^id: doc-15$/id: doc-50/' "$tmp/adr-dup/backlog/docs/doc-50 - второй ADR.md"
python3 "$BLINT" "$tmp/adr-dup" --no-source 2>&1 | grep -q " AR002 " \
  && ok "ADR · второй документ: AR002" || fail "ADR · второй документ не пойман"
# AR005: слой Technology без документов этапа — этап включён не был
cp -r "$BGOLD" "$tmp/adr-none"
find "$tmp/adr-none/backlog/docs" -maxdepth 1 -name "doc-15*" -delete
find "$tmp/adr-none/backlog/docs" -maxdepth 1 -name "doc-16*" -delete
python3 "$BLINT" "$tmp/adr-none" --no-source 2>&1 | grep -q " AR005 " \
  && ok "ADR · Technology без документов: AR005" || fail "ADR · условие включения не поймано"
python3 "$BLINT" "$tmp/adr-none" --no-source >/dev/null 2>&1 && [ $? -eq 0 ] \
  && ok "ADR · без документов этапа не Strict-ошибка" || fail "ADR · AR005 не должен валить без --strict"
# AR005 звучит и при ошибках разбора в другом месте проекта (раньше глох вместе со всеми проверками)
cp -r "$tmp/adr-none" "$tmp/adr-none-err"
python3 -I - "$tmp/adr-none-err" <<'PY'
import sys, glob
f = sorted(glob.glob(sys.argv[1] + "/backlog/tasks/*.md"))[0]
open(f, "w", encoding="utf-8").write(open(f, encoding="utf-8").read().replace("\nid: ", "\nxid: ", 1))
PY
python3 "$BLINT" "$tmp/adr-none-err" --no-source 2>&1 | grep -q " AR005 " \
  && ok "ADR · AR005 слышно и при ошибках разбора" || fail "ADR · AR005 заглох из-за ошибок разбора"
# doc update --content не стирает паспорт <!-- bft-adr -->: документ этапа остаётся документом
cp -r "$BGOLD" "$tmp/adr-upd"
(cd "$tmp/adr-upd" && python3 "$OLDPWD/$DIR/scripts/backlog_cli.py" doc update doc-15 --content "## Контекст

новый текст" >/dev/null 2>&1)
grep -q "^<!-- bft-adr" "$tmp/adr-upd/backlog/docs/doc-15 - ADR.md" \
  && ! python3 "$BLINT" "$tmp/adr-upd" --no-source 2>&1 | grep -q "а документов «ADR»" \
  && ok "ADR · doc update --content сохраняет паспорт" || fail "ADR · doc update стёр паспорт этапа"
# план: секции этапа → apply создаёт документы; рукописные разделы не переписываются
cp -r "$PL/g" "$tmp/adr-plan" 2>/dev/null || { cp -r "$BGOLD" "$tmp/adr-plan"; }
python3 - "$tmp/adr-plan" << 'PY'
import sys, re
from pathlib import Path
p = Path(sys.argv[1]) / "plan" / "map.md"
t = p.read_text(encoding="utf-8")
find = re.search(r"^## BP-1 ", t, re.M)
block = """## Решение TO-BE

| ID | Контракт | Суть решения | Обоснование |
| --- | --- | --- | --- |
| V1 | test-shelf | Полка на лету из каталога с кешем | Быстрее к запуску, пик покрывает кеш |

## Варианты

| ID | Вариант | Надёжность | Скорость реализации | Соответствие требованиям | Почему нет |
| --- | --- | --- | --- | --- | --- |
| V1 | Полка на лету с кешем | средняя | быстро | частичное | выбран |
| V2 | Ночная сборка | высокая | долго | полное | не успеть к запуску |

## Контракты

| ID | Контракт | Потребитель | Данные контракту | Источник параметров | Преобразования |
| --- | --- | --- | --- | --- | --- |
| K1 | test-shelf | Витрина | Рестораны, рейтинг | Каталог: restaurants | Ранжирование по рейтингу |

"""
# план эталона уже несёт секции этапа — заменим их на тестовые (одна секция каждого вида)
t = re.sub(r"^## (?:Решение TO-BE|Варианты|Узкие места|Компромиссы|Компоненты|Потоки|Контракты)\n.*?(?=^## )", "", t, flags=re.S | re.M)
find = re.search(r"^## BP-1 ", t, re.M)   # позиция заново: секции выше уже вырезаны
t = t[:find.start()] + block + t[find.start():]
p.write_text(t, encoding="utf-8")
PY
rm -f "$tmp/adr-plan/backlog/docs/doc-15 - ADR.md" "$tmp/adr-plan/backlog/docs/doc-16 - Системные требования.md"
find "$tmp/adr-plan/backlog/docs" -maxdepth 1 -name "*- ADR.md" -delete
find "$tmp/adr-plan/backlog/docs" -maxdepth 1 -name "*- Системные*.md" -delete
python3 "$DIR/scripts/bft-plan.py" apply "$tmp/adr-plan" >/dev/null 2>&1
ADRDOC=$(ls "$tmp/adr-plan/backlog/docs" | grep " - ADR" | head -1)
SYSDOC=$(ls "$tmp/adr-plan/backlog/docs" | grep "Системные" | head -1)
[ -n "$ADRDOC" ] && [ -n "$SYSDOC" ] && grep -q "test-shelf" "$tmp/adr-plan/backlog/docs/$ADRDOC" \
  && grep -q "restaurants" "$tmp/adr-plan/backlog/docs/$SYSDOC" \
  && ok "ADR · apply создаёт документы из секций плана" || fail "ADR · apply не создал документы"
python3 "$BLINT" "$tmp/adr-plan" --no-source >/dev/null 2>&1 \
  && ok "ADR · после apply линтер даёт 0" || python3 "$BLINT" "$tmp/adr-plan" --no-source 2>&1 | grep -E " AR00[13] " | fail "ADR · apply дал документ с ошибками AR"
# страница: слой «Архитектура» есть с документами и нет без них
python3 "$BBUILD" "$tmp/adr-plan" --out-dir "$tmp/adr-out" --no-zip >/dev/null 2>&1
PAGE=$(ls "$tmp/adr-out"/*-map.html | head -1)
grep -q '<button data-view="adr">' "$PAGE" && grep -q 'data-adrmenu' "$PAGE" && grep -q '"adr":{' "$PAGE" && grep -q '"sysreq":{' "$PAGE" \
  && ok "ADR · страница: слой «Архитектура», данные adr и sysreq" || fail "ADR · на странице нет слоя архитектуры"
python3 "$BBUILD" "$tmp/adr-none" --out-dir "$tmp/adr-out2" --no-zip >/dev/null 2>&1
PAGE2=$(ls "$tmp/adr-out2"/*-map.html | head -1)
grep -q '<button data-view="adr">' "$PAGE2" || grep -q '"adr":{' "$PAGE2" \
  && fail "ADR · слой появился без документов" || ok "ADR · без документов слоя нет"

echo
[ "$fails" -eq 0 ] && echo "bft-blueprint: все проверки пройдены" || echo "bft-blueprint: провалено проверок — $fails"
exit "$fails"
