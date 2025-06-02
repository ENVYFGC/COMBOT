"""
Configuration management for Combot
Handles environment variables and bot configuration dataclasses
"""

import os
import logging
from typing import Set, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigKey(str, Enum):
    """Configuration keys for type safety"""
    CHARACTER_NAME = "character_name"
    THUMBNAIL_URL = "thumbnail_url"
    MAIN_COLOR = "main_embed_color_hex"
    COMBO_CATEGORIES = "combo_categories"
    STARTERS = "starters"
    ENDER_TITLE = "info_section_ender_title"
    ENDER_INFO = "ender_info"
    ENDER_CREDIT = "ender_info_credit"
    ROUTES_TITLE = "info_section_routes_title"
    INTERESTING_ROUTES = "interesting_routes"
    NOTABLE_PLAYERS = "notable_players"
    PAGE_SIZE_STARTERS = "page_size_starters"
    PAGE_SIZE_COMBOS = "page_size_combos"
    PAGE_SIZE_PLAYERS = "page_size_players"
    PAGE_SIZE_RESOURCES = "page_size_resources"
    VIEW_TIMEOUT = "view_timeout_seconds"


@dataclass
class PageSizes:
    """Page size configuration for different views"""
    starters: int = 10
    combos: int = 5
    players: int = 5
    resources: int = 10


@dataclass
class BotConfiguration:
    """Main bot configuration with validation and utility methods"""
    character_name: str = "Character"
    thumbnail_url: str = "https://i.imgur.com/default.png"
    main_embed_color_hex: str = "0x7289DA"
    combo_categories: List[str] = field(default_factory=lambda: ["Midscreen", "Corner"])
    starters: Dict[str, List[str]] = field(default_factory=dict)
    info_section_ender_title: str = "📑 Ender Info"
    ender_info: List[str] = field(default_factory=list)
    ender_info_credit: str = ""
    info_section_routes_title: str = "📌 Interesting Routes"
    interesting_routes: List[str] = field(default_factory=list)
    notable_players: List[Dict[str, Any]] = field(default_factory=list)
    page_sizes: PageSizes = field(default_factory=PageSizes)
    view_timeout_seconds: float = 180.0
    
    @property
    def embed_color(self) -> discord.Color:
        """Get Discord color from hex string with validation"""
        try:
            color_int = int(self.main_embed_color_hex.replace("0x", ""), 16)
            return discord.Color(color_int)
        except ValueError:
            logger.warning(f"Invalid color hex: {self.main_embed_color_hex}, using default")
            return discord.Color.dark_red()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        data = asdict(self)
        # Flatten page_sizes
        page_sizes = data.pop('page_sizes')
        data['page_size_starters'] = page_sizes['starters']
        data['page_size_combos'] = page_sizes['combos']
        data['page_size_players'] = page_sizes['players']
        data['page_size_resources'] = page_sizes['resources']
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotConfiguration':
        """Create from dictionary loaded from JSON with validation"""
        # Extract page sizes
        page_sizes = PageSizes(
            starters=data.pop('page_size_starters', 10),
            combos=data.pop('page_size_combos', 5),
            players=data.pop('page_size_players', 5),
            resources=data.pop('page_size_resources', 10)
        )
        data['page_sizes'] = page_sizes
        
        # Remove any unknown keys to prevent errors
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)


@dataclass
class EnvConfig:
    """Environment configuration with validation"""
    discord_token: str
    youtube_api_key: str
    owner_ids: Set[int]
    config_filename: str = "character_bot_data.json"
    
    @classmethod
    def from_env(cls) -> 'EnvConfig':
        """Create configuration from environment variables with validation"""
        # Required variables
        token = os.getenv("DISCORD_BOT_TOKEN")
        yt_key = os.getenv("YOUTUBE_API_KEY")
        
        # Validate required variables
        missing_vars = []
        if not token:
            missing_vars.append("DISCORD_BOT_TOKEN")
        if not yt_key:
            missing_vars.append("YOUTUBE_API_KEY")
        
        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please set these variables in your .env file or environment."
            )
        
        # Optional variables
        owner_ids_str = os.getenv("DISCORD_OWNER_IDS", "")
        config_file = os.getenv("CONFIG_FILENAME", "character_bot_data.json")
        
        # Parse owner IDs with validation
        owner_ids = set()
        if owner_ids_str:
            try:
                owner_ids = {int(x.strip()) for x in owner_ids_str.split(",") if x.strip()}
            except ValueError as e:
                raise EnvironmentError(f"Invalid DISCORD_OWNER_IDS format: {e}")
        
        if not owner_ids:
            logger.warning(
                "No DISCORD_OWNER_IDS set. Admin commands will be disabled. "
                "Set DISCORD_OWNER_IDS in your .env file to enable admin features."
            )
        
        logger.info(f"Loaded configuration:")
        logger.info(f"  - Config file: {config_file}")
        logger.info(f"  - Owner IDs: {len(owner_ids)} configured")
        logger.info(f"  - Discord token: {'✓' if token else '✗'}")
        logger.info(f"  - YouTube API key: {'✓' if yt_key else '✗'}")
        
        return cls(token, yt_key, owner_ids, config_file)
    
    def validate_setup(self) -> None:
        """Validate that all required components are properly configured"""
        if not self.discord_token:
            raise RuntimeError("Discord token not configured")
        if not self.youtube_api_key:
            raise RuntimeError("YouTube API key not configured")
        
        logger.info("Environment configuration validated successfully")


# Global configuration instance
try:
    env_config = EnvConfig.from_env()
    env_config.validate_setup()
except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise


# Constants
CACHE_DURATION_SECONDS = 600  # 10 minutes
MAX_EMBED_FIELD_VALUE_LENGTH = 1000
MAX_EMBED_DESCRIPTION_LENGTH = 4000
MAX_LINES_FOR_CONFIG_DISPLAY = 25
MAX_CUSTOM_ID_LENGTH = 100
MODAL_DEFAULT_VALUE_MAX_LEN = 1900
DEFAULT_MODAL_TIMEOUT = 300.0
