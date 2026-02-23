"""Constants for the application."""

import re
from enum import Enum
from pathlib import Path
from typing import Final

import inflect

p = inflect.engine()

ENVAR_PREFIX: Final[str] = "VALBOT_"
ABS_MAX_EMBED_CHARACTERS: Final[int] = (
    3900  # Absolute maximum number of characters in an embed -100 for safety
)
DEFAULT_DIFFICULTY: Final[int] = 6
PREF_MAX_EMBED_CHARACTERS = 1950  # Preferred maximum number of characters in an embed
PROJECT_ROOT_PATH: Final[Path] = Path(__file__).parents[2].absolute()
SRC_PATH: Final[Path] = Path(__file__).parents[0].absolute()
COGS_PATH: Final[Path] = SRC_PATH / "cogs"
MAX_BUTTONS_PER_ROW = 5
MAX_DOT_DISPLAY = 5  # number of dots to display on a character sheet before converting to text
MAX_FIELD_COUNT = 1010
MAX_OPTION_LIST_SIZE = 25  # maximum number of options in a discord select menu
PREF_MAX_EMBED_CHARACTERS = 1950  # Preferred maximum number of characters in an embed
SPACER = "\u200b"  # Zero-width space used in Discord embeds


class EmojiDict:
    """Enum for emojis."""

    ALIVE = "🙂"
    BOOK = "📖"
    BOOKS = "📚"
    BOT = "🤖"
    CANCEL = "🚫"
    COOL_POINT = "🆒"
    DANGER = "👮‍♂️"
    DEAD = "💀"
    DESPAIR = "😰"
    DESPERATION = "🤞"
    DICE = "🎲"
    ERROR = "❌"
    FACEPALM = "🤦"
    GHOST = "👻"
    GHOUL = "🧟"
    HUNTER = "🔫"
    LOCK = "🔒"
    MAGE = "🧙‍♂️"
    MONSTER = "👹"
    MORTAL = "🧑"
    NO = "❌"
    NOTE = "📝"
    OTHER = "🤷"
    OVERREACH = "😱"
    PENCIL = "✏️"
    QUESTION = "❓"
    RECYCLE = "♻️"
    RELOAD = "🔄"
    SETTING = "⚙️"
    SILHOUETTE = "👤"
    SPARKLES = "✨"
    SUCCESS = "👍"
    VAMPIRE = "🧛"
    WARNING = "⚠️"
    WEREWOLF = "🐺"
    YES = "✅"
    CHANNEL_PLAYER = "👤"
    CHANNEL_PRIVATE = "🔒"
    CHANNEL_GENERAL = "✨"
    CHANNEL_PLAYER_DEAD = "💀"
    REFUND = "♻️"
    PURCHASE = "💪"

    # Concepts
    ASCETIC = "👊"
    BERSERKER = "⚔️"
    BUSINESSMAN = "💰"
    CRUSADER = "🛡️"
    HEALER = "💊"
    PERFORMER = "🎭"
    SCIENTIST = "🔬"
    SHAMAN = "🧘"
    SOLDIER = "🪖"
    TRACKER = "🏹"
    TRADESMAN = "🛠️"
    UNDER_WORLDER = "🔪"

    # Ability Focus
    JACK_OF_ALL_TRADES = "💪"
    BALANCED = "☯️"
    SPECIALIST = "🎯"

    # Auto Gen Experience Level
    NEW = "🆕"
    INTERMEDIATE = "🔄"
    ADVANCED = "🔥"
    ELITE = "🌟"


class CampaignChannelName(Enum):
    """Enum for common campaign channel names."""

    GENERAL = f"{EmojiDict.CHANNEL_GENERAL}-general"
    STORYTELLER = f"{EmojiDict.CHANNEL_PRIVATE}-storyteller"


class ChannelPermission(Enum):
    """Enum for permissions when creating a character. Default is UNRESTRICTED."""

    DEFAULT = 0  # Default
    HIDDEN = 1
    READ_ONLY = 2
    POST = 3
    MANAGE = 4


class EmbedColor(Enum):
    """Enum for colors of embeds."""

    SUCCESS = 0x00FF00  # GREEN
    ERROR = 0xFF0000  # RED
    WARNING = 0xFF5F00  # ORANGE
    INFO = 0x00FFFF  # CYAN
    DEBUG = 0x0000FF  # BLUE
    DEFAULT = 0x6082B6  # GRAY
    GRAY = 0x808080
    YELLOW = 0xFFFF00


class LogLevel(Enum):
    """Log level."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# CHANNEL_PERMISSIONS: Dictionary containing a tuple mapping of channel permissions.
#     Format:
#         default role permission,
#         player role permission,
#         storyteller role permission

CHANNEL_PERMISSIONS: dict[str, tuple[ChannelPermission, ChannelPermission, ChannelPermission]] = {
    "default": (
        ChannelPermission.DEFAULT,
        ChannelPermission.DEFAULT,
        ChannelPermission.DEFAULT,
    ),
    "audit_log": (
        ChannelPermission.HIDDEN,
        ChannelPermission.HIDDEN,
        ChannelPermission.READ_ONLY,
    ),
    "storyteller_channel": (
        ChannelPermission.HIDDEN,
        ChannelPermission.HIDDEN,
        ChannelPermission.POST,
    ),
    "error_log_channel": (
        ChannelPermission.HIDDEN,
        ChannelPermission.HIDDEN,
        ChannelPermission.HIDDEN,
    ),
    "campaign_character_channel": (
        ChannelPermission.READ_ONLY,
        ChannelPermission.READ_ONLY,
        ChannelPermission.MANAGE,
    ),
}

BAD_WORDS = {
    "anal",
    "ass",
    "asshole",
    "bastard",
    "bitch",
    "blowjob",
    "bollocks",
    "boob",
    "boobies",
    "bugger",
    "cock",
    "cocksucker",
    "cum",
    "cunt",
    "dildo",
    "fuck",
    "fucker",
    "gangbang",
    "handjob",
    "masturbate",
    "milf",
    "motherfucker",
    "orgasm",
    "orgy",
    "penis",
    "piss",
    "poop",
    "sex",
    "sexy",
    "shit",
    "shite",
    "shitter",
    "slut",
    "tit",
    "titfuck",
    "tittyfuck",
    "tittyfucker",
    "tosser",
    "vagina",
    "wank",
    "wanker",
    "whore",
}
# Create a list of singular and plural forms of the words in BAD_WORD_LIST.
BAD_WORD_LIST = BAD_WORDS | {p.plural(word) for word in BAD_WORDS}
BAD_WORD_PATTERN = re.compile(rf"\b({'|'.join(BAD_WORD_LIST)})\b", flags=re.IGNORECASE)

BOT_DESCRIPTIONS = [
    "sensual sorceress who leaves you spellbound and spent",
    "flirtatious firestarter igniting your desires while burning your world",
    "passionate predator who devours you in the night",
    "bewitching siren with a thirst for more than your attention",
    "enticing enchantress who takes you beyond the point of no return",
    "ravishing rogue who steals more than just your breath",
    "lusty liberator freeing you from virtue, only to imprison you in vice",
    "siren who serenades you into peril",
    "black widow with a kiss that's fatal",
    "fiery femme fatale who leaves you burned but begging for more",
    "enchanting empress who rules your most forbidden thoughts",
    "vixen who leaves a trail of destruction",
    "sublime seductress who dances you to the edge of reason",
    "irresistible icon who redefines your sense of sin and salvation"
    "enchantress who captivates you in her web of deceit",
    "sultry Silver Fang who leads you into a world of primal passion",
    "seductress with eyes that promise ecstasy and chaos",
    "dazzling temptress with daggers in her eyes",
    "spellbinding witch who makes you forget your name",
    "goddess who gives pleasure but exacts a price",
    "alluring angel with a devilish twist",
    "trusted bot who helps you play White Wolf's TTRPGs",
    "succubus who will yet have your heart",
    "maid servant here to serve your deepest desires",
    "guardian angel who watches over you",
    "steadfast Silent Strider who journeys through the Umbra on your behalf",
    "trustworthy Thaumaturge who crafts potent rituals for your adventures",
    "Lasombra who makes darkness your newfound comfort",
    "seductive Toreador who makes eternity seem too short",
    "enigmatic Tremere who binds you in a blood bond you can't resist",
    "charismatic Ventrue who rules your heart with an iron fist",
    "shadowy Nosferatu who lurks in the dark corners of your fantasies",
    "haunting Wraith who whispers sweet nothings from the Shadowlands",
    "resilient Hunter who makes you question who's really being hunted",
    "Tzimisce alchemist who shapes flesh and mind into a twisted masterpiece",
    "Giovanni necromancer who invites you to a banquet with your ancestors",
    "Assamite assassin who turns the thrill of the hunt into a deadly romance",
    "Caitiff outcast who makes you see the allure in being a pariah",
    "Malkavian seer who unravels the tapestry of your sanity with whispers of prophecies",
    "Brujah revolutionary who ignites a riot in your soul and a burning need for rebellion",
    "Tremere warlock who binds your fate with arcane secrets too irresistible to ignore",
    "Toreador muse who crafts a masterpiece out of your every emotion, leaving you entranced",
    "Gangrel shape-shifter who lures you into the untamed wilderness of your darkest desires",
    "Ravnos trickster who casts illusions that make you question the very fabric of your reality",
    "Sabbat crusader who drags you into a nightmarish baptism of blood and fire, challenging your very essence",
    "Ventrue aristocrat who ensnares you in a web of high-stakes politics, making you question your loyalties",
    "Hunter zealot who stalks the shadows of your mind, making you question your beliefs",
    "enigmatic sorcerer weaving a tapestry of cosmic mysteries, entrancing your logical faculties",
    "mystic oracle who plunges you into ethereal visions, making you question the tangible world",
    "servant who feasts on your vulnerabilities, creating an insatiable need for servitude",
]

VALID_IMAGE_EXTENSIONS = frozenset(["png", "jpg", "jpeg", "gif", "webp"])
