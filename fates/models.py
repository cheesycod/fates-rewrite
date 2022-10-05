import datetime
from typing import Any, Optional, Generic, TypeVar
import uuid

from .tables import BotCommands, Bots, Users, UserBotLogs, Servers
from piccolo.utils.pydantic import create_pydantic_model
from piccolo.query import Select
from pydantic import BaseModel
from pydantic.generics import GenericModel
import silverpelt.types.types as silver_types
from fates.enums import *

from fates import tables

# Add models here
BotBase = create_pydantic_model(
    Bots,
    deserialize_json=True,
    exclude_columns=(
        Bots.api_token,
        Bots.webhook_secret,
        Bots.webhook,
    ),
)
UserBase = create_pydantic_model(
    Users, deserialize_json=True, exclude_columns=(Users.api_token,)
)

UserBotLogsBase = create_pydantic_model(UserBotLogs, deserialize_json=True)

BotCommandsBase = create_pydantic_model(BotCommands, deserialize_json=True)

BOT_SNIPPET_COLS = (
    Bots.bot_id,
    Bots.votes,
    Bots.description,
    Bots.flags,
    Bots.guild_count,
    Bots.banner_card,
    Bots.state,
)

SERVER_SNIPPET_COLS = (
    Servers.guild_id,
    Servers.votes,
    Servers.description,
    Servers.flags,
    Servers.guild_count,
    Servers.banner_card,
    Servers.state,
)

DEFAULT_USER_EXPERIMENTS = [
    UserExperiment.UserVotePrivacy,
    UserExperiment.LynxExperimentRolloutView,
    UserExperiment.BotReport,
]


async def augment(c: Select, aug: str):
    """Augment a SQL select with custom SQL"""
    return await tables.Bots.raw(str(c) + aug)


class UserBotLog(UserBotLogsBase):  # type: ignore[valid-type, misc]
    bot_id: str
    user_id: str


class BotCommands(BotCommandsBase):
    """Represents a command attached to a bot"""

    bot_id: str
    """The commands bot ID"""


class Entity:
    """Base class for all entities"""

    id: str
    """The entity's ID"""

    @staticmethod
    def to(_: dict) -> "Entity":
        pass

    @classmethod
    def to_list(cls, obj: list[dict]) -> list["Entity"]:
        return [cls.to(e) for e in obj if e]

    def __eq__(self, other):
        if getattr(other, "id", None):
            return self.id == getattr(other, "id", None)
        return self.id == other


class ResolvedPackBot(BaseModel):
    """Represents a bot that is part of a pack"""

    user: silver_types.DiscordUser
    """The bot's user"""

    description: str
    """The bot's description"""


class BotPack(BaseModel):
    """Represents a bot pack on the list"""

    id: uuid.UUID
    """The pack's ID"""

    name: str
    """The pack's name"""

    description: str
    """The pack's description"""

    icon: str
    """The pack's icon"""

    banner: Optional[str] = None
    """The pack's banner"""

    resolved_bots: list[ResolvedPackBot]
    """The bots in the pack"""

    owner: silver_types.DiscordUser
    """The pack's owner"""

    created_at: datetime.datetime
    """The pack's creation date"""


class Permission(BaseModel):
    """A permission for a staff member on the list"""

    index: int
    roles: list[str]
    name: str

    def __eq__(self, other: "Permission") -> bool:
        if not isinstance(other, Permission):
            return False
        return self.index == other.index

    def __lt__(self, other: "Permission") -> bool:
        if not isinstance(other, Permission):
            return False
        return self.index < other.index

    def __gt__(self, other: "Permission") -> bool:
        if not isinstance(other, Permission):
            return False
        return self.index > other.index

    def __le__(self, other: "Permission") -> bool:
        if not isinstance(other, Permission):
            return False
        return self.index <= other.index

    def __ge__(self, other: "Permission") -> bool:
        if not isinstance(other, Permission):
            return False
        return self.index >= other.index


class PermissionList(BaseModel):
    perms: dict[str, Permission]


class Tag(BaseModel, Entity):
    """Represents a tag"""

    id: str
    """The tag's ID"""

    iconify_data: str
    """The tag's iconify class"""

    name: str
    """The tag name"""

    owner_guild: Optional[str]
    """The guild ID of the tags owner (server only)"""

    @staticmethod
    def to(tag: dict) -> "Tag":
        """Returns all tags for a bot"""
        return Tag(
            id=tag["id"],
            iconify_data=tag["icon"] if "icon" in tag else tag["iconify_data"],
            name=tag["id"].replace("_", " ").title(),
            owner_guild=tag.get("owner_guild", None),
        )


class Feature(BaseModel, Entity):
    """Represents a feature"""

    id: str
    """The feature's ID"""

    name: str
    """Feature Name"""

    viewed_as: str
    """What the feature is viewed as"""

    description: str
    """Feature description"""

    # kitescratch-end

    @staticmethod
    def to(feature: dict) -> "Feature":
        """Returns all features for a bot"""
        return Feature(
            id=feature["id"],
            name=feature["name"],
            viewed_as=feature["viewed_as"],
            description=feature["description"],
        )


class Owner(BaseModel):
    """Represents a bot owner"""

    user: silver_types.DiscordUser
    """The owner's user object"""

    main: bool
    """Whether the owner is the main owner"""

    # kitescratch-end


class Bot(BotBase):  # type: ignore[misc, valid-type]
    """Represents a bot"""

    user: silver_types.DiscordUser
    """The bot's user object"""

    owners: list[Owner]
    """The bot's owners"""

    # These fields have the wrong type set for API response, change them
    bot_id: str

    verifier: Optional[str]
    """The reviewer who has approved/denied the bot"""

    extra_links: dict
    """Extra links for the bot ({"Website": "https://blah.com"})"""

    long_description_raw: str
    """Raw unsanitized long description"""

    css_raw: str
    """Raw unsanitized CSS"""

    action_logs: list[UserBotLog]
    """Action logs for the bot"""

    tags: list[Tag]
    """Tags for the bot"""

    features: list[Feature]
    """Features for the bot"""

    state: BotServerState
    """The bot's state"""

    flags: list[BotServerFlag]
    """The bot's flags"""

    commands: list[BotCommands]
    """The bot's commands"""

    # kitescratch-end


class User(UserBase):  # type: ignore[valid-type, misc]
    """Represents a user"""

    pass


class Snippet(BaseModel):
    """
    Represents a snippet which is essentially a miniature version of a bot/server where a full Bot is too expensive to return

    - This applies to both ``Bot`` and ``Server`` entities

    """

    user: silver_types.DiscordUser
    """The bot's/server's user object"""

    votes: int
    """The bot's/server's vote count"""

    description: str
    """The bot's/server's short description"""

    flags: list[BotServerFlag]
    """The bot's/server's flags"""

    banner_card: Optional[str]
    """The bot's/server's banner_card"""

    state: BotServerState
    """The bot's/server's state"""

    guild_count: int
    """The bot's/server's guild count"""


class ProfileSnippet(BaseModel):
    """
    Represents a snippet which is essentially a miniature version of a profile where a full Profile is too expensive to return

    - This applies to both ``User`` entities
    """

    user: silver_types.DiscordUser
    """The user's user object"""

    banner: Optional[str] = None
    """The user's banner"""

    description: str
    """The user's description"""


class Index(BaseModel):
    """Represents an index"""

    new: list[Snippet]
    """New bots/servers"""

    top_voted: list[Snippet]
    """Top voted bots/servers"""

    certified: list[Snippet]
    """Certified bots/servers this week"""


class BotListMeta(BaseModel):
    """Core metadata about the bot list part of fates list"""

    tags: list[Tag]
    """All tags for a bot"""

    features: list[Feature]
    """All features for a bot"""


class ServerListMeta(BaseModel):
    """Core metadata about the server list part of fates list"""

    tags: list[Tag]
    """All tags for a server"""


class ListMeta(BaseModel):
    """Core metadata (tags/features for servers and bots)"""

    bot: BotListMeta

    server: ServerListMeta


class BotSecrets(BaseModel):
    """Represents a bot's secrets"""

    api_token: str
    """The bot's API token"""

    webhook: Optional[str] = None
    """The bot's webhook"""

    webhook_secret: Optional[str] = None
    """The bot's webhook secret"""


class Vanity(BaseModel):
    """Represents a vanity"""

    target_id: str
    """The vanity's target ID"""

    target_type: TargetType
    """The vanity's target type"""

    code: str
    """The vanity's code"""


class Login(BaseModel):
    """Represents a login"""

    code: str
    """The Discord OAuth2 code"""


class OauthUser(BaseModel):
    """OAuth2 login response"""

    state: UserState
    """The user's state"""

    token: str
    """The user's token. If in data_action login mode, this will be the ticket for the action instead"""

    user: silver_types.DiscordUser
    """The user's user object"""

    site_lang: str
    """The user's site language"""

    css: Optional[str] = None
    """The user's CSS"""

    user_experiments: list[UserExperiment]
    """The user's experiments"""

    permissions: Permission
    """The user's permissions"""


class OAuth2Login(BaseModel):
    """OAuth2 login response"""

    state: str
    """The user's state"""

    url: str
    """The url to redirect to"""


class Invite(BaseModel):
    """A invite for a bot/server"""

    invite: str


class ResponseCode(Enum):
    """A API response code (can be used for programatic error handling)"""

    OK = "ok"
    AUTH_FAIL = "auth_fail"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"
    INVALID_DATA = "invalid_data"
    FORBIDDEN = "forbidden"


class Response(BaseModel):
    """A API Response"""

    done: bool
    """Whether or not the request was successful"""

    code: Optional[ResponseCode] = ResponseCode.OK
    """The response code (can be used for programatic error handling)"""

    reason: Optional[str] = None
    """The reason for the request failing (if any)"""

    def error(self, status_code: int):
        raise ResponseRaise(self, status_code)

    @staticmethod
    def not_implemented():
        Response(
            done=False,
            code=ResponseCode.UNKNOWN,
            reason="This feature/endpoint is not implemented yet",
        ).error(
            409
        )  # Conflict


class ResponseRaise(Exception):
    """Raised via ``Response.error``"""

    def __init__(self, response: Response, status_code: int):
        self.status_code = status_code
        self.response = response


# Test model
class NestedModel(BaseModel):
    test: str
    perms: Permission


class TaskResponse(BaseModel):
    """A created task response"""

    task_id: str
    """The task ID"""


class AuthData(BaseModel):
    """INTERNAL: Auth struct"""

    auth_type: TargetType
    target_id: int
    token: str
    compat: bool


class AuthDataHTTPResponse(AuthData):
    """AuthData struct for HTTP responses"""

    target_id: str


DataT = TypeVar("DataT")


class SearchFilter(GenericModel, Generic[DataT]):
    """A filter for search"""

    filter_from: DataT
    """The value to filter from"""

    filter_to: DataT
    """The value to filter to"""

    def __iter__(self):
        yield self.filter_from
        yield self.filter_to


class SearchTags(BaseModel):
    """Filter by tag"""

    bot: list[str] = []
    """Bot tags"""

    server: list[str] = []
    """Server tags"""


class SearchQuery(BaseModel):
    """A search query"""

    query: str
    """The search query"""

    guild_count: SearchFilter[int] = SearchFilter[int](filter_from=0, filter_to=-1)
    """The guild count filter"""

    votes: SearchFilter[int] = SearchFilter[int](filter_from=0, filter_to=-1)
    """The vote count filter"""

    tags: SearchTags = SearchTags()


class SearchResponse(BaseModel):
    """A search response"""

    bots: list[Snippet]
    """The bots that matched the search query"""

    servers: list[Snippet]
    """The servers that matched the search query"""

    profiles: list[ProfileSnippet]
    """The profiles that matched the search query"""

    packs: list[BotPack]
