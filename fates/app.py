import uuid
from fates import models
from fates.auth import auth
from fates.decorators import Ratelimit, SharedRatelimit, route, Route, Method, nop
from . import tables
from . import tags
import inspect
import piccolo
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import ORJSONResponse
from piccolo.columns.combination import WhereRaw
from starlette.routing import Mount
from piccolo_admin.endpoints import create_admin
from piccolo.engine import engine_finder

from mapleshade import SilverNoData, Mapleshade, Permission
import silverpelt.types.types as silver_types
import orjson
from pydantic import BaseModel

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
with open("docs/meta.json") as meta_f:
    meta: list[str] = orjson.loads(meta_f.read())

for file_name in meta:
    with open(f"docs/{file_name}") as doc:
        docs.append(doc.read())

app = FastAPI(
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
    description="\n\n".join(docs),
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


@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/random",
        response_model=models.Snippet,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def random_snippet(
    request: Request,
    target_type: models.TargetType = models.TargetType.Bot, reroll: bool = False
):
    """
Fetches a random 'snippet' from the list.

**Query Parameters**

- reroll: Whether to reroll and bypass cache (default: false)
    """

    nop(request)

    if target_type != models.TargetType.Bot:
        raise HTTPException(400, "Not yet implemented")

    if target_type == models.TargetType.User:
        raise HTTPException(400, detail="User snippets are not supported *yet*")

    if not reroll:
        if cached := mapleshade.cache.get("random-bot"):
            return cached.value()
    flag = 0
    while flag < 10:
        try:
            v = (
                await mapleshade.to_snippet(
                    await models.augment(
                        tables.Bots.select(*models.BOT_SNIPPET_COLS).where(
                            tables.Bots.state == models.BotServerState.Certified
                        ),
                        "ORDER BY RANDOM() LIMIT 1",
                    )
                )
            )[0]
            mapleshade.cache.set("random-bot", v, expiry=60 * 60 * 3)
            return v
        except Exception as exc:
            print(exc)
            flag += 1


@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/index",
        response_model=models.Index,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def get_index(
    request: Request,
    target_type: models.TargetType
):
    """
Fetches the index for a bot/server.

*An index is made of `Snippets`*
    """

    nop(request)

    if target_type != models.TargetType.Bot:
        raise HTTPException(400, "Not yet implemented")

    if cached_index := mapleshade.cache.get("bot_index"):
        return cached_index.value()

    index = models.Index(
        top_voted=await mapleshade.to_snippet(
            await tables.Bots.select(*models.BOT_SNIPPET_COLS)
            .where(tables.Bots.state == models.BotServerState.Approved)
            .order_by(tables.Bots.votes, ascending=False)
            .limit(12)
        ),
        new=await mapleshade.to_snippet(
            await tables.Bots.select(*models.BOT_SNIPPET_COLS)
            .where(tables.Bots.state == models.BotServerState.Approved)
            .order_by(tables.Bots.created_at, ascending=False)
            .limit(12)
        ),
        certified=await mapleshade.to_snippet(
            await tables.Bots.select(*models.BOT_SNIPPET_COLS)
            .where(tables.Bots.state == models.BotServerState.Certified)
            .order_by(tables.Bots.votes, ascending=False)
            .limit(12)
        ),
    )
    mapleshade.cache.set("bot_index", index, expiry=30)
    return index


@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/bots/{bot_id}",
        response_model=models.Bot,
        method=Method.get,
        tags=[tags.bot],
        ratelimit=Ratelimit(
            num=10,
            interval=1,
            name="get_bot"
        )
    )
)
async def get_bot(
    request: Request,
    bot_id: int
):
    """
Gets a bot based on its ``bot_id``
    """
    nop(request)

    bot = await mapleshade.bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Not Found")
    return bot

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/bots/{bot_id}/invite",
        response_model=models.Invite,
        method=Method.get,
        tags=[tags.bot],
        ratelimit=Ratelimit(
            num=3,
            interval=1.5,
            name="get_bot_invite"
        )
    )
)
async def get_bot_invite(request: Request, bot_id: int):
    """
    Gets the invite for a bot.

    If ``Frostpaw-Target`` is set to ``invite``, then this also updates invite_amount
    """

    nop(request)

    invite_url = await tables.Bots.select(tables.Bots.invite).where(tables.Bots.bot_id == bot_id).first()

    if not invite_url:
        raise HTTPException(status_code=404, detail="Not Found")
    
    if request.headers.get("Frostpaw-Target") == "invite":
        await tables.Bots.update(invite_amount = tables.Bots.invite_amount + 1).where(tables.Bots.bot_id == bot_id)

    if not invite_url["invite"]:
        return models.Invite(
            invite=f"https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions=0&scope=bot%20applications.commands"
        )
    elif invite_url["invite"].startswith("P:"):
        perm_num = invite_url["invite"][2:]
        return models.Invite(
            invite=f"https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions={perm_num}&scope=bot%20applications.commands"
        )
    else:
        return models.Invite(invite=invite_url["invite"])

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/bots/{bot_id}/secrets",
        response_model=models.BotSecrets,
        method=Method.get,
        tags=[tags.bot],
        ratelimit=Ratelimit(
            num=3,
            interval=2,
            name="get_bot_secrets",
        ),
        auth=models.TargetType.User
    )
)
async def get_bot_secrets(request: Request, bot_id: int, auth: models.AuthData = Depends(auth)):
    """
Returns the secrets of a bot (``api_token``, ``webhook`` and ``webhook_secret`` as of now)
    """
    if auth.auth_type != models.TargetType.User:
        raise HTTPException(401, "User-only endpoint")
    
    nop(request)

    bot_owners = await tables.BotOwner.select().where(tables.BotOwner.bot_id == bot_id)

    if not bot_owners:
        raise HTTPException(status_code=404, detail="Not Found")
    
    flag = False
    for owner in bot_owners:
        if owner["owner"] == auth.target_id:
            flag = True
            break
    
    if not flag:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    bot_secrets = await tables.Bots.select(tables.Bots.webhook, tables.Bots.webhook_secret, tables.Bots.api_token).where(tables.Bots.bot_id == bot_id).first()

    return models.BotSecrets(
        api_token=bot_secrets["api_token"],
        webhook=bot_secrets["webhook"],
        webhook_secret=bot_secrets["webhook_secret"]
    )

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/@auth",
        response_model=models.AuthData,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core"),
        auth=True
    )
)
async def check_auth_header(request: Request, auth: models.AuthData = Depends(auth)):
    """
Tests an ``Frostpaw-Auth`` or an ``Authorization`` header

**Libraries are free (and encouraged) to use this to verify their auth code**
    """

    nop(request)

    return auth

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/@bot",
        response_model=silver_types.DiscordUser,
        method=Method.get,
        tags=[tags.tests],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def test_sv_resp(request: Request):
    """Returns the current Fates List user thats logged in on the API"""

    nop(request)

    req = await mapleshade.silverpelt_req("@me")
    return req


@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/blazefire/{user_id}",
        response_model=silver_types.DiscordUser,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def get_discord_user(request: Request, user_id: int):
    """
Internally used for extra owners etc, this fetches a user from the Discord API handling caching as well
    """

    nop(request)

    try:
        req = await mapleshade.silverpelt_req(f"users/{user_id}")
    except SilverNoData as e:
        raise HTTPException(status_code=404, detail="Not Found") from e
    return req

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/meta",
        response_model=models.ListMeta,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def get_meta(request: Request):
    """Returns the metadata of the list (tags, features etc)"""

    nop(request)

    return models.ListMeta(
        bot=models.BotListMeta(
            tags=models.Tag.to_list(await tables.BotListTags.select()),
            features=models.Feature.to_list(await tables.Features.select()),
        ),
        server=models.ServerListMeta(
            tags=models.Tag.to_list(await tables.ServerTags.select()),
        ),
    )

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/code/{vanity}",
        response_model=models.Vanity,
        method=Method.get,
        tags=[tags.generic],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def get_code(request: Request, vanity: str):
    """Resolves a vanity based on the code"""

    nop(request)
    vanity = await tables.Vanity.select().where(WhereRaw("lower(vanity_url) = {}", vanity.lower())).first()

    if not vanity:
        raise HTTPException(status_code=404, detail="Not Found")

    vanity_map = {
        0: models.TargetType.Server,
        1: models.TargetType.Bot,
        2: models.TargetType.User,
    }

    try:
        vanity["type"] = vanity_map[vanity["type"]]
    except KeyError:
        raise HTTPException(status_code=500, detail="Unknown Vanity Type")
    
    return models.Vanity(
        target_type=vanity["type"],
        code=vanity["vanity_url"],
        target_id=vanity["redirect"]
    )

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/oauth2",
        response_model=models.OAuth2Login,
        method=Method.get,
        tags=[tags.internal],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def get_oauth2(request: Request):
    """Returns the OAuth2 login URL to redirect to"""
    if not request.headers.get("Frostpaw-Server"):
        raise HTTPException(400, "Missing Frostpaw-Server header")
    state = str(uuid.uuid4())
    return {
        "state": state,
        "url": f"https://discord.com/oauth2/authorize?client_id={mapleshade.config['secrets']['client_id']}&redirect_uri={request.headers.get('Frostpaw-Server')}/frostpaw/login&scope=identify&response_type=code",
    }

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/oauth2",
        response_model=models.OauthUser,
        method=Method.post,
        tags=[tags.internal],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def login_user(request: Request, login: models.Login):
    """Logs in a user and returns a OauthUser including their User ID and Token among other things"""
    redirect_url_d = request.headers.get("Frostpaw-Server")

    if not redirect_url_d:
        redirect_url_d = "https://fateslist.xyz"

    redirect_url = f'https://{redirect_url_d.replace("https://", "", 1).replace("http://", "", 1)}/frostpaw/login'

    if redirect_url_d.startswith("http://"):
        redirect_url = f'http://{redirect_url_d.replace("https://", "", 1).replace("http://", "", 1)}/frostpaw/login'

    try:
        oauth = await mapleshade.login(login.code, redirect_url)
    except Exception as e:
        print("Error logging in user", type(e), e)
        raise HTTPException(status_code=400, detail=str(e))
    
    return oauth

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/guppy",
        response_model=Permission,
        method=Method.get,
        tags=[tags.tests],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def guppy_test(request: Request, user_id: int):
    """Returns a users permissions on the list"""

    nop(request)

    return await mapleshade.guppy(user_id)

# Test model

class NestedModel(BaseModel):
    test: str
    perms: Permission

@route(
    Route(  
        app=app,
        mapleshade=mapleshade,
        url="/@test-tryitout/{user_id}/{a:path}",
        response_model=Permission,
        method=Method.put,
        tags=[tags.tests],
        ratelimit=SharedRatelimit.new("core")
    )
)
async def test_tio(request: Request, user_id: int, b: int, permission: NestedModel):
    """Returns a users permissions on the list"""

    nop(request)

    return await mapleshade.guppy(user_id)