"""MockAPI прототипа — FastAPI одним файлом, собран ./blueprint.py prototype build. Руками не правь.

Каждый контракт contracts/C-N.md — маршрут из его `op`. Ответ — «Пример ответа» контракта; ошибка —
заголовок `X-Mock-Error: КОД` или параметр `?_error=КОД` (коды — из «Ошибок» контракта). Обязательные
поля «Запроса» проверяются: нет поля — 422 со списком, как отказал бы настоящий сервис по контракту.
Данных нет и не будет: прототип показывает стыки, а не хранит записи.

    uvicorn main:app --port 8000        # список стыков — GET /__contracts, документация — /docs
"""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

SPEC = json.loads((Path(__file__).parent / "spec.json").read_text(encoding="utf-8"))
app = FastAPI(title=f"MockAPI — {SPEC['title']}", description="Ответы по контрактам стыков карты (Design First)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Contract"])


def _missing(c: dict, path: dict, query: dict, body: dict) -> list[str]:
    where = {"path": path, "query": query, "body": body}
    out = []
    for r in c["request"]:
        name, place = r.get("Поле", "").strip("` "), r.get("Где", "body")
        if r.get("Обяз.") == "да" and name.split(".")[0] not in where.get(place, body):
            out.append(f"{name} ({place})")
    return out


def _handler(c: dict):
    async def handle(request: Request):
        try:
            body = await request.json() if request.method in ("POST", "PUT", "PATCH") else {}
        except ValueError:
            body = {}
        query = {k: v for k, v in request.query_params.items() if not k.startswith("_")}
        code = request.headers.get("X-Mock-Error") or request.query_params.get("_error")
        head = {"X-Contract": c["id"]}
        if code:
            err = next((e for e in c["errors"] if e.get("Код", "").strip("` ") == code), None)
            if err is None:
                return JSONResponse({"code": "UNKNOWN_MOCK_ERROR", "message": f"в «Ошибках» {c['id']} нет {code}"}, 400, head)
            return JSONResponse({"code": code, "message": err.get("Когда", "")}, int(err.get("Статус", 400)), head)
        miss = _missing(c, dict(request.path_params), query, body if isinstance(body, dict) else {})
        if miss:
            return JSONResponse({"code": "CONTRACT_FIELDS_MISSING", "message": "нет обязательных полей контракта", "fields": miss}, 422, head)
        return JSONResponse(c["example"] if c["example"] is not None else {}, 200, head)
    return handle


for _c in SPEC["contracts"].values():
    if _c["boundary"] == "service-db" or not _c.get("op"):
        continue
    _method, _path = _c["op"].split(None, 1)
    app.add_api_route(_path, _handler(_c), methods=[_method], name=f"{_c['id']} · {_c['title']}",
                      summary=f"{_c['id']} · {_c['title']}", description=f"{_c['caller']} → {_c['callee']}")


@app.get("/__contracts", summary="Стыки прототипа: контракт, метод, кто кого вызывает")
def contracts():
    return [{"id": c["id"], "op": c["op"], "caller": c["caller"], "callee": c["callee"], "title": c["title"]}
            for c in SPEC["contracts"].values() if c.get("op")]
