#!/usr/bin/env python3
"""Карта этого проекта: ./blueprint.py lint | build | check   (build пишет страницу и архив в папку проекта)"""
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
scripts = os.path.join(here, ".blueprint", "scripts")
cmd, rest = (sys.argv[1] if len(sys.argv) > 1 else "help"), sys.argv[2:]
if cmd == "lint":
    run = ["bft-backlog-lint.py", here, "--hints"]
elif cmd == "build":
    run = ["bft-backlog-build.py", here, "--out-dir", here]
elif cmd == "check":
    run = ["bft-backlog-build.py", here, "--check"]
elif cmd in ("apply", "export", "next"):
    run = ["bft-plan.py", cmd, here]
elif cmd == "reqs":
    run = ["bft-reqs.py", "--project", here]
elif cmd == "skeleton":
    run = ["bft-skeleton.py", here]
elif cmd == "groom":
    run = ["bft-groom.py", rest.pop(0) if rest else "help", here]
elif cmd == "contracts":
    run = ["bft-contracts.py", "skeleton", here] if rest[:1] == ["skeleton"] else ["bft-contracts.py", "lint", here, "--hints"]
    rest = rest[1:] if rest[:1] == ["skeleton"] else rest
else:
    print("./blueprint.py reqs   — инвентарь БФТ: требования, акторы, сценарий, зависимости и куда они ложатся на карте")
    print("./blueprint.py skeleton — каркас plan/map.md из БФТ: каждое требование, параметр и критерий уже на месте, текст — {{…}}")
    print("./blueprint.py apply  — план plan/map.md и plan/screens/*.md → задачи, карточки, документы; затем проверка")
    print("./blueprint.py next   — что исправить дальше: ошибки по строкам плана и как их исправить")
    print("./blueprint.py export — план из бэклога (правки одним файлом)")
    print("./blueprint.py groom fill|audit|refine — пакеты роя; groom merge fill|refine — ответы в план (.blueprint/rules/grooming.md)")
    print("./blueprint.py lint   — проверить карту (коды BL, SN; правила — .blueprint/rules/backlog_rules.md)")
    print("./blueprint.py contracts skeleton — каркас contracts/C-N.md на каждый стык карты без контракта")
    print("./blueprint.py contracts — проверить контракты стыков contracts/C-N.md (коды CT; правила — .blueprint/rules/contracts.md)")
    print("./blueprint.py build  — схемы BPMN из «Процесса», страница <epic>-map.html и архив <epic>-blueprint.zip")
    print("./blueprint.py check  — проверка без записи: схемы и скрипты проекта актуальны")
    print("доп. ключи: --source БФТ.md — сверка с БФТ, --strict — предупреждения тоже ошибки")
    sys.exit(0 if cmd in ("help", "-h", "--help") else 2)
sys.exit(subprocess.call([sys.executable, os.path.join(scripts, run[0]), *run[1:], *rest]))
