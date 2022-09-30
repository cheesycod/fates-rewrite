from fates import models, consts
from fates.decorators import nop
from . import tables
import inspect
import piccolo
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse, HTMLResponse
from starlette.routing import Mount
from piccolo_admin.endpoints import create_admin
from piccolo.engine import engine_finder

from mapleshade import Mapleshade

mapleshade = Mapleshade()


_tables = []

tables_dict = vars(tables)

for obj in tables_dict.values():
    if obj == tables.Table:
        continue
    if inspect.isclass(obj) and isinstance(obj, piccolo.table.TableMetaclass):
        _tables.append(obj)

# Load all docs
docs = []
with open("docs/meta.yaml") as meta_f:
    meta: list[str] = mapleshade.yaml.load(meta_f)

for file_name in meta:
    with open(f"docs/{file_name}") as doc:
        docs.append(
            doc.read()
            .replace("{%static%}", mapleshade.config["static"])
            .replace("{%sunbeam%}", mapleshade.config["sunbeam"])
        )

with open("docs/__docs_page.html") as dp:
    docs_page = dp.read()

app = FastAPI(
    title="Fates List",
    default_response_class=ORJSONResponse,
    routes=[
        Mount(
            "/admin/",
            create_admin(
                tables=_tables,
                site_name="Fates Admin",
                production=True,
                # Required when running under HTTPS, change when done
                allowed_hosts=["rewrite.fateslist.xyz"],
            ),
        ),
    ],
    docs_url=None,
    redoc_url=None,
    description="\n\n".join(docs),
)

@app.exception_handler(404)
async def not_found(_: Request, exc: HTTPException):
    return ORJSONResponse(
        models.Response(
            done=False,
            reason=exc.detail,
            code=consts.DEFAULT_EXC.get(exc.status_code, models.ResponseCode.UNKNOWN)
        ).dict(),
        status_code=exc.status_code,
    )


@app.exception_handler(models.ResponseRaise)
async def unicorn_exception_handler(_: Request, exc: models.ResponseRaise):
    return ORJSONResponse(
        status_code=exc.status_code,
        content=exc.response.dict(),
    )

@app.middleware("http")
async def cors(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "false"
    response.headers[
        "Access-Control-Allow-Headers"
    ] = "Content-Type, Authorization, Accept, Frostpaw-Cache, Frostpaw-Auth, Frostpaw-Target, Frostpaw-Server"

    if request.method == "OPTIONS":
        response.status_code = 200
    return response


@app.on_event("startup")
async def open_database_connection_pool():
    engine = engine_finder()
    # asyncio.create_task(bot.start(secrets["token"]))
    # await bot.load_extension("jishaku")
    await engine.start_connnection_pool()


@app.on_event("shutdown")
async def close_database_connection_pool():
    engine = engine_finder()
    await engine.close_connnection_pool()

# This is the only exception to not using @route
@app.get("/docs", include_in_schema=False)
async def docs():
    return HTMLResponse(docs_page)

# Load all routes
from fates import routes
nop(routes)