# combot.py - Universal Fighting Game Combo Bot Template
# A Discord bot for managing and displaying fighting game combos
# GitHub: https://github.com/ENVYFGC/combot

import os
import json
import re
import logging
import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, quote_plus, unquote_plus
from typing import Any, Dict, List, Optional, Tuple, Union, Set
from dataclasses import dataclass, field, asdict
from functools import lru_cache, wraps
from pathlib import Path
import time
from enum import Enum

from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.app_commands import Choice
from discord.ui import View, Button, Modal, TextInput
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─── Configuration & Setup ─────────────────────────────────────────────────────

load_dotenv()

# Enums for better type safety
class ConfigKey(str, Enum):
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

# Configuration dataclasses
@dataclass
class PageSizes:
    starters: int = 10
    combos: int = 5
    players: int = 5
    resources: int = 10

@dataclass
class BotConfiguration:
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
        """Get Discord color from hex string"""
        try:
            color_int = int(self.main_embed_color_hex.replace("0x", ""), 16)
            return discord.Color(color_int)
        except ValueError:
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
        """Create from dictionary loaded from JSON"""
        # Extract page sizes
        page_sizes = PageSizes(
            starters=data.pop('page_size_starters', 10),
            combos=data.pop('page_size_combos', 5),
            players=data.pop('page_size_players', 5),
            resources=data.pop('page_size_resources', 10)
        )
        data['page_sizes'] = page_sizes
        
        # Remove any unknown keys
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)

@dataclass
class ComboEntry:
    notation: str
    notes: str
    link: str

@dataclass
class ResourceEntry:
    name: str
    type: str
    link: str
    credit: Optional[str] = None

@dataclass
class PlayerEntry:
    name: str
    region_emoji: str
    social_link: str
    image_url: str
    description_lines: List[str]
    color_footer: str

# Environment configuration
@dataclass
class EnvConfig:
    discord_token: str
    youtube_api_key: str
    owner_ids: Set[int]
    config_filename: str = "character_bot_data.json"
    
    @classmethod
    def from_env(cls) -> 'EnvConfig':
        token = os.getenv("DISCORD_BOT_TOKEN")
        yt_key = os.getenv("YOUTUBE_API_KEY")
        owner_ids_str = os.getenv("DISCORD_OWNER_IDS", "")
        config_file = os.getenv("CONFIG_FILENAME", "character_bot_data.json")
        
        if not token or not yt_key:
            raise EnvironmentError("Missing DISCORD_BOT_TOKEN or YOUTUBE_API_KEY")
        
        owner_ids = {int(x) for x in owner_ids_str.split(",") if x.strip()}
        if not owner_ids:
            logging.warning("No DISCORD_OWNER_IDS set. Admin commands disabled.")
        
        return cls(token, yt_key, owner_ids, config_file)

# Initialize configuration
env_config = EnvConfig.from_env()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

CACHE_DURATION = timedelta(minutes=10)
MAX_EMBED_FIELD_VALUE_LENGTH = 1000
MAX_EMBED_DESCRIPTION_LENGTH = 4000
MAX_LINES_FOR_CONFIG_DISPLAY = 25
MAX_CUSTOM_ID_LENGTH = 100
MODAL_DEFAULT_VALUE_MAX_LEN = 1900
DEFAULT_MODAL_TIMEOUT = 300.0

# ─── Performance Utilities ─────────────────────────────────────────────────────

def async_ttl_cache(seconds: int = 300):
    """Async cache decorator with time-to-live"""
    def decorator(func):
        cache = {}
        cache_times = {}
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function arguments
            key = f"{args}:{kwargs}"
            now = time.time()
            
            # Check if cached and not expired
            if key in cache and now - cache_times.get(key, 0) < seconds:
                return cache[key]
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            cache[key] = result
            cache_times[key] = now
            
            # Clean old entries
            expired_keys = [k for k, t in cache_times.items() if now - t >= seconds]
            for k in expired_keys:
                cache.pop(k, None)
                cache_times.pop(k, None)
            
            return result
        
        wrapper.clear_cache = lambda: (cache.clear(), cache_times.clear())
        return wrapper
    return decorator

# ─── Data Management ───────────────────────────────────────────────────────────

class DataManager:
    """Centralized async data management with validation and caching"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._config: Optional[BotConfiguration] = None
        self._combo_data: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, Any] = {"note": "Additional resources", "resources": []}
        self._lock = asyncio.Lock()
        self._dirty = False
        self._last_save = time.time()
        self._save_interval = 5.0  # Debounce saves
    
    async def load(self) -> None:
        """Load data from file"""
        async with self._lock:
            if self.file_path.exists():
                try:
                    # Use asyncio.to_thread for async file reading
                    content = await asyncio.to_thread(self.file_path.read_text, encoding='utf-8')
                    data = json.loads(content)
                except Exception as e:
                    logger.error(f"Error loading data: {e}")
                    data = {}
            else:
                logger.info(f"Creating new data file: {self.file_path}")
                data = {}
            
            # Load configuration
            config_data = data.get("config", {})
            self._config = BotConfiguration.from_dict(config_data)
            
            # Initialize starters for each category
            for category in self._config.combo_categories:
                if category not in self._config.starters:
                    self._config.starters[category] = []
                self._combo_data[category] = data.get(category, {})
            
            # Load resources
            self._resources = data.get("RESOURCES", {"note": "Additional resources", "resources": []})
            
            logger.info(f"Loaded configuration for: {self._config.character_name}")
    
    async def save(self, force: bool = False) -> None:
        """Save data to file with debouncing"""
        now = time.time()
        if not force and not self._dirty:
            return
        if not force and now - self._last_save < self._save_interval:
            # Schedule a save later
            asyncio.create_task(self._delayed_save())
            return
        
        async with self._lock:
            data = {
                "config": self._config.to_dict() if self._config else {},
                "RESOURCES": self._resources
            }
            
            # Add combo data for each category
            for category, combos in self._combo_data.items():
                data[category] = combos
            
            # Atomic write using asyncio.to_thread
            temp_file = self.file_path.with_suffix('.tmp')
            
            def write_file():
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                temp_file.replace(self.file_path)
            
            await asyncio.to_thread(write_file)
            
            self._dirty = False
            self._last_save = now
            logger.info(f"Saved data to {self.file_path}")
    
    async def _delayed_save(self) -> None:
        """Save after delay"""
        await asyncio.sleep(self._save_interval)
        await self.save()
    
    @property
    def config(self) -> BotConfiguration:
        """Get current configuration"""
        if not self._config:
            raise RuntimeError("Data not loaded")
        return self._config
    
    async def update_config(self, **kwargs) -> None:
        """Update configuration fields"""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
            self._dirty = True
    
    async def get_combos(self, category: str, starter: str) -> List[ComboEntry]:
        """Get combos for a category/starter"""
        combos_data = self._combo_data.get(category, {}).get(starter, {}).get("combos", [])
        return [ComboEntry(**c) for c in combos_data]
    
    async def update_combos(self, category: str, starter: str, combos: List[ComboEntry], note: str = "") -> None:
        """Update combos for a category/starter"""
        async with self._lock:
            if category not in self._combo_data:
                self._combo_data[category] = {}
            
            self._combo_data[category][starter] = {
                "note": note or f"Combos for {starter}",
                "combos": [asdict(c) for c in combos]
            }
            self._dirty = True
    
    async def get_resources(self) -> Tuple[str, List[ResourceEntry]]:
        """Get resources"""
        note = self._resources.get("note", "")
        resources_data = self._resources.get("resources", [])
        resources = [ResourceEntry(**r) for r in resources_data]
        return note, resources
    
    async def add_resource(self, resource: ResourceEntry) -> None:
        """Add a resource"""
        async with self._lock:
            self._resources.setdefault("resources", []).append(asdict(resource))
            self._dirty = True
    
    async def add_starter(self, category: str, starter: str) -> None:
        """Add a starter to a category"""
        async with self._lock:
            if category not in self._config.starters:
                self._config.starters[category] = []
            
            if starter not in self._config.starters[category]:
                self._config.starters[category].append(starter)
                self._dirty = True
    
    async def remove_starter(self, category: str, starter: str) -> Tuple[bool, bool]:
        """Remove a starter and its data. Returns (removed_from_config, removed_data)"""
        async with self._lock:
            removed_config = False
            removed_data = False
            
            # Remove from config
            if category in self._config.starters and starter in self._config.starters[category]:
                self._config.starters[category].remove(starter)
                removed_config = True
            
            # Remove combo data
            if category in self._combo_data and starter in self._combo_data[category]:
                del self._combo_data[category][starter]
                removed_data = True
            
            if removed_config or removed_data:
                self._dirty = True
            
            return removed_config, removed_data

# ─── YouTube Service ───────────────────────────────────────────────────────────

class YouTubeService:
    """YouTube API service with caching and error handling"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._service = None
    
    @property
    def service(self):
        """Lazy load YouTube service"""
        if not self._service:
            self._service = build("youtube", "v3", developerKey=self.api_key)
        return self._service
    
    @staticmethod
    def extract_playlist_id(url_or_id: str) -> Optional[str]:
        """Extract playlist ID from URL or validate ID"""
        parsed = urlparse(url_or_id)
        
        # Check if it's a YouTube URL
        if parsed.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
            if parsed.path == '/playlist':
                return parse_qs(parsed.query).get('list', [None])[0]
        
        # Check if it's already a playlist ID
        if re.match(r"^(PL|UU|FL|OL|RD)?[a-zA-Z0-9_-]{10,}$", url_or_id):
            return url_or_id
        
        return None
    
    @async_ttl_cache(600)  # Cache for 10 minutes
    async def fetch_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """Fetch playlist data with caching"""
        try:
            # Get playlist info
            pl_resp = await asyncio.to_thread(
                self.service.playlists().list(
                    part="snippet",
                    id=playlist_id
                ).execute
            )
            
            if not pl_resp.get("items"):
                raise ValueError(f"Playlist '{playlist_id}' not found or private")
            
            # Extract note from description
            desc = pl_resp["items"][0]["snippet"].get("description", "")
            note_match = re.search(r"(?i)Note:\s*(.+)", desc)
            note = note_match.group(1).strip() if note_match else "No overall notes."
            
            # Fetch videos (max 200)
            videos = []
            page_token = None
            
            while len(videos) < 200:
                items_resp = await asyncio.to_thread(
                    self.service.playlistItems().list(
                        part="snippet",
                        playlistId=playlist_id,
                        maxResults=50,
                        pageToken=page_token
                    ).execute
                )
                
                items = items_resp.get("items", [])
                videos.extend(items)
                
                page_token = items_resp.get("nextPageToken")
                if not page_token or not items:
                    break
            
            # Process videos
            processed_videos = []
            for item in videos:
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId")
                if not video_id:
                    continue
                
                # Parse description for notation and notes
                desc = snippet.get("description", "")
                parsed = self._parse_video_description(desc)
                
                processed_videos.append({
                    "title": snippet.get("title", ""),
                    "notation": parsed["notation"],
                    "notes": parsed["notes"],
                    "link": f"https://youtu.be/{video_id}"
                })
            
            return {
                "note": note,
                "videos": processed_videos
            }
            
        except HttpError as e:
            if e.resp.status == 403:
                raise ValueError("YouTube API quota exceeded or forbidden")
            elif e.resp.status == 404:
                raise ValueError(f"Playlist '{playlist_id}' not found")
            else:
                raise ValueError(f"YouTube API error (status {e.resp.status})")
        except Exception as e:
            logger.error(f"Error fetching playlist: {e}")
            raise ValueError(f"Failed to fetch playlist: {str(e)}")
    
    @staticmethod
    def _parse_video_description(desc: str) -> Dict[str, str]:
        """Parse video description for notation and notes"""
        notation_match = re.search(r"(?i)notation:\s*(.+)", desc)
        notes_match = re.search(r"(?i)notes?:\s*(.+)", desc)
        
        notation = "Unknown Notation"
        if notation_match:
            notation = notation_match.group(1).strip().replace(",", " >")
        
        notes = "No Notes Provided"
        if notes_match:
            notes = notes_match.group(1).splitlines()[0].strip()
        
        return {"notation": notation, "notes": notes}

# ─── UI Base Classes ───────────────────────────────────────────────────────────

class BaseView(View):
    """Base view with common functionality"""
    
    def __init__(self, user: discord.User, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.user = user
        self.message: Optional[discord.Message] = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if interaction is from original user"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This menu belongs to someone else.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Handle timeout"""
        if self.message:
            try:
                await self.message.edit(
                    content="*This menu has timed out.*",
                    view=None,
                    embed=None
                )
            except discord.NotFound:
                pass
            except Exception as e:
                logger.error(f"Error handling timeout: {e}")

class PaginatedView(BaseView):
    """Base paginated view"""
    
    def __init__(self, user: discord.User, items: List[Any], 
                 per_page: int = 10, timeout: float = 180.0):
        super().__init__(user, timeout)
        self.items = items
        self.per_page = per_page
        self.current_page = 0
    
    @property
    def max_pages(self) -> int:
        """Get total number of pages"""
        return max(1, (len(self.items) - 1) // self.per_page + 1)
    
    @property
    def current_items(self) -> List[Any]:
        """Get items for current page"""
        start = self.current_page * self.per_page
        end = start + self.per_page
        return self.items[start:end]
    
    def update_buttons(self) -> None:
        """Update navigation buttons"""
        self.clear_items()
        
        # Add page-specific buttons
        self._add_page_items()
        
        # Add navigation
        if self.current_page > 0:
            prev_btn = Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.secondary
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)
        
        if self.current_page < self.max_pages - 1:
            next_btn = Button(
                label="Next ▶️",
                style=discord.ButtonStyle.secondary
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)
        
        # Add back button
        back_btn = Button(
            label="↩️ Back",
            style=discord.ButtonStyle.danger
        )
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    def _add_page_items(self) -> None:
        """Override to add page-specific buttons"""
        pass
    
    async def _prev_page(self, interaction: discord.Interaction) -> None:
        """Go to previous page"""
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(
            embed=await self.create_embed(),
            view=self
        )
    
    async def _next_page(self, interaction: discord.Interaction) -> None:
        """Go to next page"""
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(
            embed=await self.create_embed(),
            view=self
        )
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Override to handle back navigation"""
        pass
    
    async def create_embed(self) -> discord.Embed:
        """Override to create page embed"""
        raise NotImplementedError

# ─── Main Menu View ────────────────────────────────────────────────────────────

class MainMenuView(BaseView):
    """Main category selection menu"""
    
    def __init__(self, user: discord.User, config: BotConfiguration, data_manager: DataManager):
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self._add_buttons()
    
    def _add_buttons(self) -> None:
        """Add category buttons"""
        # Combo category buttons
        styles = [discord.ButtonStyle.primary, discord.ButtonStyle.success, discord.ButtonStyle.secondary]
        
        for i, category in enumerate(self.config.combo_categories):
            btn = Button(
                label=category,
                style=styles[i % len(styles)],
                custom_id=f"cat_{quote_plus(category)}"
            )
            btn.callback = self._make_category_callback(category)
            self.add_item(btn)
        
        # Resources button
        res_btn = Button(
            label="📚 Resources",
            style=discord.ButtonStyle.secondary
        )
        res_btn.callback = self._show_resources
        self.add_item(res_btn)
        
        # Ender info button (if configured)
        if self.config.info_section_ender_title:
            ender_btn = Button(
                label=self.config.info_section_ender_title,
                style=discord.ButtonStyle.secondary
            )
            ender_btn.callback = self._show_ender_info
            self.add_item(ender_btn)
        
        # Routes button (if configured)
        if self.config.info_section_routes_title:
            routes_btn = Button(
                label=self.config.info_section_routes_title,
                style=discord.ButtonStyle.secondary
            )
            routes_btn.callback = self._show_routes
            self.add_item(routes_btn)
        
        # Close button
        close_btn = Button(
            label="✖️ Close",
            style=discord.ButtonStyle.grey
        )
        close_btn.callback = self._close
        self.add_item(close_btn)
    
    def _make_category_callback(self, category: str):
        """Create callback for category button"""
        async def callback(interaction: discord.Interaction):
            starters = self.config.starters.get(category, [])
            if not starters:
                await interaction.response.send_message(
                    f"No starters configured for {category}",
                    ephemeral=True
                )
                return
            
            view = StarterListView(
                self.user,
                self.config,
                self.data_manager,
                category,
                starters
            )
            
            self.stop()
            await interaction.response.edit_message(
                embed=await view.create_embed(),
                view=view
            )
            view.message = interaction.message
        
        return callback
    
    async def _show_resources(self, interaction: discord.Interaction) -> None:
        """Show resources menu"""
        view = ResourceMenuView(self.user, self.config, self.data_manager)
        self.stop()
        await interaction.response.edit_message(
            embed=view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    async def _show_ender_info(self, interaction: discord.Interaction) -> None:
        """Show ender info"""
        embed = discord.Embed(
            title=self.config.info_section_ender_title,
            description="\n".join(self.config.ender_info) or "_No ender info configured._",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        if self.config.ender_info_credit:
            embed.set_footer(text=self.config.ender_info_credit)
        
        # Simple back button view
        back_view = BaseView(self.user, self.config.view_timeout_seconds)
        back_btn = Button(label="↩️ Back", style=discord.ButtonStyle.danger)
        
        async def go_back(inter: discord.Interaction):
            back_view.stop()
            new_main = MainMenuView(self.user, self.config, self.data_manager)
            await inter.response.edit_message(
                embed=new_main.create_embed(),
                view=new_main
            )
            new_main.message = inter.message
        
        back_btn.callback = go_back
        back_view.add_item(back_btn)
        
        self.stop()
        await interaction.response.edit_message(embed=embed, view=back_view)
        back_view.message = interaction.message
    
    async def _show_routes(self, interaction: discord.Interaction) -> None:
        """Show interesting routes"""
        embed = discord.Embed(
            title=self.config.info_section_routes_title,
            description="\n".join(f"- {route}" for route in self.config.interesting_routes) or "_No routes configured._",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        # Simple back button view
        back_view = BaseView(self.user, self.config.view_timeout_seconds)
        back_btn = Button(label="↩️ Back", style=discord.ButtonStyle.danger)
        
        async def go_back(inter: discord.Interaction):
            back_view.stop()
            new_main = MainMenuView(self.user, self.config, self.data_manager)
            await inter.response.edit_message(
                embed=new_main.create_embed(),
                view=new_main
            )
            new_main.message = inter.message
        
        back_btn.callback = go_back
        back_view.add_item(back_btn)
        
        self.stop()
        await interaction.response.edit_message(embed=embed, view=back_view)
        back_view.message = interaction.message
    
    async def _close(self, interaction: discord.Interaction) -> None:
        """Close menu"""
        self.stop()
        await interaction.response.edit_message(
            content="*Menu closed.*",
            view=None,
            embed=None
        )
    
    def create_embed(self) -> discord.Embed:
        """Create main menu embed"""
        embed = discord.Embed(
            title=f"🎮 {self.config.character_name} Combos",
            description="Select a category:",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        return embed

# ─── Starter List View ─────────────────────────────────────────────────────────

class StarterListView(PaginatedView):
    """View for selecting starters"""
    
    def __init__(self, user: discord.User, config: BotConfiguration,
                 data_manager: DataManager, category: str, starters: List[str]):
        super().__init__(user, starters, config.page_sizes.starters, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.category = category
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add starter buttons"""
        for i, starter in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            btn = Button(
                label=f"{global_index + 1}. {starter[:50]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"s_{global_index}"
            )
            btn.callback = self._make_starter_callback(starter)
            self.add_item(btn)
    
    def _make_starter_callback(self, starter: str):
        """Create callback for starter button"""
        async def callback(interaction: discord.Interaction):
            combos = await self.data_manager.get_combos(self.category, starter)
            
            if not combos:
                await interaction.response.send_message(
                    f"No combos found for **{starter}**",
                    ephemeral=True
                )
                return
            
            view = ComboListView(
                self.user,
                self.config,
                self.category,
                starter,
                combos
            )
            
            await interaction.response.send_message(
                embed=await view.create_embed(),
                view=view,
                ephemeral=True
            )
            view.message = await interaction.original_response()
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to main menu"""
        self.stop()
        main_view = MainMenuView(self.user, self.config, self.data_manager)
        await interaction.response.edit_message(
            embed=main_view.create_embed(),
            view=main_view
        )
        main_view.message = interaction.message
    
    async def create_embed(self) -> discord.Embed:
        """Create starter list embed"""
        embed = discord.Embed(
            title=f"🔹 {self.category} Starters (Page {self.current_page + 1}/{self.max_pages})",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        if not self.items:
            embed.description = "No starters configured for this category."
        else:
            descriptions = []
            for i, starter in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                # Get combo count for this starter
                combos_data = await self.data_manager.get_combos(self.category, starter)
                note = f"{len(combos_data)} combos" if combos_data else "No combos yet"
                descriptions.append(f"**{global_index + 1}. {starter}** - _{note}_")
            
            embed.description = "\n".join(descriptions)
        
        embed.set_footer(text="Select a starter to view combos")
        return embed

# ─── Combo List View ───────────────────────────────────────────────────────────

class ComboListView(PaginatedView):
    """View for displaying combos"""
    
    def __init__(self, user: discord.User, config: BotConfiguration,
                 category: str, starter: str, combos: List[ComboEntry]):
        super().__init__(user, combos, config.page_sizes.combos, config.view_timeout_seconds)
        self.config = config
        self.category = category
        self.starter = starter
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add combo number buttons"""
        for i, combo in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            btn = Button(
                label=str(global_index + 1),
                style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_combo_callback(global_index, combo)
            self.add_item(btn)
    
    def _make_combo_callback(self, index: int, combo: ComboEntry):
        """Create callback for combo button"""
        async def callback(interaction: discord.Interaction):
            content = f"**Combo #{index + 1} for {self.starter}**\n\n"
            content += f"**Notation:**\n```{combo.notation[:800]}```\n"
            
            if combo.notes and combo.notes != "No Notes Provided":
                content += f"**Notes:**\n{combo.notes[:800]}\n"
            
            content += f"\n{combo.link}"
            
            await interaction.response.send_message(
                content=content,
                ephemeral=True,
                suppress_embeds=False
            )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Close combo list"""
        self.stop()
        await interaction.response.edit_message(
            content="*Combo list closed.*",
            view=None,
            embed=None
        )
    
    async def create_embed(self) -> discord.Embed:
        """Create combo list embed"""
        embed = discord.Embed(
            title=f"📜 {self.starter} Combos (Page {self.current_page + 1}/{self.max_pages})",
            description="Select a number for full details & video.",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        for i, combo in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            
            notation = combo.notation[:250]
            if len(combo.notation) > 250:
                notation += "..."
            
            field_value = "_No specific notes._"
            if combo.notes and combo.notes != "No Notes Provided":
                field_value = f"**Note:** {combo.notes[:200]}"
                if len(combo.notes) > 200:
                    field_value += "..."
            
            embed.add_field(
                name=f"{global_index + 1}. __{notation}__",
                value=field_value,
                inline=False
            )
        
        start = self.current_page * self.per_page + 1
        end = min((self.current_page + 1) * self.per_page, len(self.items))
        embed.set_footer(text=f"Showing combos {start}-{end} of {len(self.items)}")
        
        return embed

# ─── Resource Views ────────────────────────────────────────────────────────────

class ResourceMenuView(BaseView):
    """Resource category menu"""
    
    def __init__(self, user: discord.User, config: BotConfiguration, data_manager: DataManager):
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self._add_buttons()
    
    def _add_buttons(self) -> None:
        """Add resource category buttons"""
        # General resources
        gen_btn = Button(
            label="🔗 General Resources",
            style=discord.ButtonStyle.primary
        )
        gen_btn.callback = self._show_general
        self.add_item(gen_btn)
        
        # Notable players
        if self.config.notable_players:
            players_btn = Button(
                label="✨ Notable Players",
                style=discord.ButtonStyle.primary
            )
            players_btn.callback = self._show_players
            self.add_item(players_btn)
        
        # Back button
        back_btn = Button(
            label="↩️ Main Menu",
            style=discord.ButtonStyle.danger
        )
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    async def _show_general(self, interaction: discord.Interaction) -> None:
        """Show general resources"""
        note, resources = await self.data_manager.get_resources()
        
        view = ResourceListView(
            self.user,
            self.config,
            self.data_manager,
            resources,
            note
        )
        
        self.stop()
        await interaction.response.edit_message(
            embed=await view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    async def _show_players(self, interaction: discord.Interaction) -> None:
        """Show notable players"""
        view = PlayerListView(
            self.user,
            self.config,
            self.data_manager,
            self.config.notable_players
        )
        
        self.stop()
        await interaction.response.edit_message(
            embed=await view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to main menu"""
        self.stop()
        main_view = MainMenuView(self.user, self.config, self.data_manager)
        await interaction.response.edit_message(
            embed=main_view.create_embed(),
            view=main_view
        )
        main_view.message = interaction.message
    
    def create_embed(self) -> discord.Embed:
        """Create resource menu embed"""
        embed = discord.Embed(
            title="📚 Resources",
            description="Select a resource category:",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        return embed

class ResourceListView(PaginatedView):
    """View for general resources"""
    
    def __init__(self, user: discord.User, config: BotConfiguration,
                 data_manager: DataManager, resources: List[ResourceEntry], note: str):
        super().__init__(user, resources, config.page_sizes.resources, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.note = note
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add resource buttons"""
        for i, resource in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            label = f"{global_index + 1}. {resource.name[:60]}"
            
            btn = Button(
                label=label,
                style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_resource_callback(resource)
            self.add_item(btn)
    
    def _make_resource_callback(self, resource: ResourceEntry):
        """Create callback for resource button"""
        async def callback(interaction: discord.Interaction):
            content = f"**Resource: {resource.name}**\n"
            content += f"Type: `{resource.type}`\n"
            if resource.credit:
                content += f"Credit: *{resource.credit}*\n"
            content += f"\n{resource.link}"
            
            await interaction.response.send_message(
                content=content,
                ephemeral=True,
                suppress_embeds=False
            )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to resource menu"""
        self.stop()
        view = ResourceMenuView(self.user, self.config, self.data_manager)
        await interaction.response.edit_message(
            embed=view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    async def create_embed(self) -> discord.Embed:
        """Create resource list embed"""
        embed = discord.Embed(
            title=f"🔗 General Resources (Page {self.current_page + 1}/{self.max_pages})",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        if self.note:
            description = f"{self.note}\n\n"
        else:
            description = ""
        
        if not self.items:
            description += "_No resources configured yet._"
        else:
            for i, resource in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                description += f"**{global_index + 1}. {resource.name}** ({resource.type})\n"
        
        embed.description = description
        embed.set_footer(text="Select a resource for details and link")
        
        return embed

class PlayerListView(PaginatedView):
    """View for notable players"""
    
    def __init__(self, user: discord.User, config: BotConfiguration,
                 data_manager: DataManager, players: List[Dict[str, Any]]):
        super().__init__(user, players, config.page_sizes.players, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add player buttons"""
        for i, player in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            name = player.get('name', 'Unknown')
            emoji = player.get('region_emoji', '')
            
            btn = Button(
                label=f"{global_index + 1}. {name} {emoji}"[:80],
                style=discord.ButtonStyle.primary
            )
            btn.callback = self._make_player_callback(global_index)
            self.add_item(btn)
    
    def _make_player_callback(self, index: int):
        """Create callback for player button"""
        async def callback(interaction: discord.Interaction):
            view = PlayerDetailView(
                self.user,
                self.config,
                self.items,
                index
            )
            
            self.stop()
            await interaction.response.edit_message(
                embed=view.create_embed(),
                view=view
            )
            view.message = interaction.message
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to resource menu"""
        self.stop()
        view = ResourceMenuView(self.user, self.config, self.data_manager)
        await interaction.response.edit_message(
            embed=view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    async def create_embed(self) -> discord.Embed:
        """Create player list embed"""
        embed = discord.Embed(
            title=f"✨ Notable Players (Page {self.current_page + 1}/{self.max_pages})",
            color=self.config.embed_color
        )
        embed.set_thumbnail(url=self.config.thumbnail_url)
        
        descriptions = []
        for i, player in enumerate(self.current_items):
            global_index = self.current_page * self.per_page + i
            name = player.get('name', 'Unknown')
            emoji = player.get('region_emoji', '')
            descriptions.append(f"**{global_index + 1}. {name}** {emoji}")
        
        embed.description = "\n".join(descriptions) + "\n\nSelect a player for details."
        
        return embed

class PlayerDetailView(BaseView):
    """Player detail view"""
    
    def __init__(self, user: discord.User, config: BotConfiguration,
                 all_players: List[Dict[str, Any]], current_index: int):
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.all_players = all_players
        self.current_index = current_index
        self._update_buttons()
    
    def _update_buttons(self) -> None:
        """Update navigation buttons"""
        self.clear_items()
        
        # Previous player
        if self.current_index > 0:
            prev_btn = Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.primary
            )
            prev_btn.callback = self._prev_player
            self.add_item(prev_btn)
        
        # Next player
        if self.current_index < len(self.all_players) - 1:
            next_btn = Button(
                label="Next ▶️",
                style=discord.ButtonStyle.primary
            )
            next_btn.callback = self._next_player
            self.add_item(next_btn)
        
        # Back to list
        back_btn = Button(
            label="↩️ Player List",
            style=discord.ButtonStyle.danger
        )
        back_btn.callback = self._back_to_list
        self.add_item(back_btn)
    
    async def _prev_player(self, interaction: discord.Interaction) -> None:
        """Show previous player"""
        self.current_index -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )
    
    async def _next_player(self, interaction: discord.Interaction) -> None:
        """Show next player"""
        self.current_index += 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=self.create_embed(),
            view=self
        )
    
    async def _back_to_list(self, interaction: discord.Interaction) -> None:
        """Return to player list"""
        self.stop()
        view = PlayerListView(self.user, self.config, self.all_players)
        view.current_page = self.current_index // view.per_page
        view.update_buttons()
        await interaction.response.edit_message(
            embed=await view.create_embed(),
            view=view
        )
        view.message = interaction.message
    
    def create_embed(self) -> discord.Embed:
        """Create player detail embed"""
        player = self.all_players[self.current_index]
        
        title = f"{player.get('name', 'Unknown')} {player.get('region_emoji', '')}"
        description = "\n".join(player.get('description_lines', ["No description"]))
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=self.config.embed_color,
            url=player.get('social_link')
        )
        
        if player.get('image_url'):
            embed.set_image(url=player['image_url'])
        
        if player.get('color_footer'):
            embed.set_footer(text=player['color_footer'])
        
        embed.add_field(
            name="\u200B",
            value=f"Player {self.current_index + 1} of {len(self.all_players)}",
            inline=False
        )
        
        return embed

# ─── Modal Classes ─────────────────────────────────────────────────────────────

class SetupModal(Modal, title="Bot Setup"):
    """Initial bot setup modal"""
    
    def __init__(self, current_config: BotConfiguration):
        super().__init__(timeout=None)
        
        self.char_name = TextInput(
            label="Character Name",
            placeholder="e.g., Carmine, Sol Badguy",
            default=current_config.character_name,
            required=True
        )
        
        self.thumbnail = TextInput(
            label="Thumbnail URL (optional)",
            placeholder="https://i.imgur.com/....png",
            default=current_config.thumbnail_url,
            required=False
        )
        
        self.color = TextInput(
            label="Embed Color (hex)",
            placeholder="FF0000 for red",
            default=current_config.main_embed_color_hex.replace("0x", ""),
            required=False,
            max_length=6
        )
        
        self.ender_title = TextInput(
            label="Ender Info Title (blank to hide)",
            placeholder="📑 Ender Optimization",
            default=current_config.info_section_ender_title,
            required=False
        )
        
        self.routes_title = TextInput(
            label="Routes Title (blank to hide)",
            placeholder="✨ Special Routes",
            default=current_config.info_section_routes_title,
            required=False
        )
        
        self.add_item(self.char_name)
        self.add_item(self.thumbnail)
        self.add_item(self.color)
        self.add_item(self.ender_title)
        self.add_item(self.routes_title)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle setup submission"""
        char_name = self.char_name.value.strip()
        thumbnail = self.thumbnail.value.strip()
        color = self.color.value.strip().upper().replace("#", "").replace("0X", "")
        
        # Validate
        if not char_name:
            await interaction.response.send_message(
                "Character name is required.",
                ephemeral=True
            )
            return
        
        if thumbnail and not urlparse(thumbnail).scheme:
            await interaction.response.send_message(
                "Invalid thumbnail URL.",
                ephemeral=True
            )
            return
        
        if color and not re.match(r"^[0-9A-F]{6}$", color):
            await interaction.response.send_message(
                "Invalid color hex value.",
                ephemeral=True
            )
            return
        
        # Update config
        await data_manager.update_config(
            character_name=char_name,
            thumbnail_url=thumbnail or BotConfiguration().thumbnail_url,
            main_embed_color_hex=f"0x{color}" if color else BotConfiguration().main_embed_color_hex,
            info_section_ender_title=self.ender_title.value.strip(),
            info_section_routes_title=self.routes_title.value.strip()
        )
        
        await data_manager.save(force=True)
        
        await interaction.response.send_message(
            f"✅ Bot configured for **{char_name}**!",
            ephemeral=True
        )

class ResourceModal(Modal, title="Add Resource"):
    """Modal for adding resources"""
    
    def __init__(self, link: str = ""):
        super().__init__(timeout=300)
        
        self.name = TextInput(
            label="Resource Name",
            required=True
        )
        
        self.type = TextInput(
            label="Type (e.g., video, doc, sheet)",
            required=True
        )
        
        self.link = TextInput(
            label="Link (URL)",
            default=link,
            required=True
        )
        
        self.credit = TextInput(
            label="Credit/Source (optional)",
            required=False
        )
        
        self.add_item(self.name)
        self.add_item(self.type)
        self.add_item(self.link)
        self.add_item(self.credit)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle resource submission"""
        # Validate URL
        if not urlparse(self.link.value).scheme:
            await interaction.response.send_message(
                "Invalid URL provided.",
                ephemeral=True
            )
            return
        
        resource = ResourceEntry(
            name=self.name.value.strip(),
            type=self.type.value.strip(),
            link=self.link.value.strip(),
            credit=self.credit.value.strip() if self.credit.value else None
        )
        
        await data_manager.add_resource(resource)
        await data_manager.save()
        
        await interaction.response.send_message(
            f"✅ Resource **{resource.name}** added!",
            ephemeral=True
        )

class PlayerModal(Modal, title="Add Notable Player"):
    """Modal for adding players"""
    
    def __init__(self):
        super().__init__(timeout=600)
        
        self.name = TextInput(label="Player Name", required=True)
        self.region = TextInput(label="Region Emoji", placeholder="🇺🇸", required=True, max_length=5)
        self.social = TextInput(label="Social Link", placeholder="https://x.com/player", required=True)
        self.image = TextInput(label="Character Image URL", required=True)
        self.desc = TextInput(
            label="Description (use \\n for newlines)",
            style=discord.TextStyle.paragraph,
            required=False
        )
        
        self.add_item(self.name)
        self.add_item(self.region)
        self.add_item(self.social)
        self.add_item(self.image)
        self.add_item(self.desc)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle player submission"""
        # Validate URLs
        for url, field in [(self.social.value, "Social"), (self.image.value, "Image")]:
            if not urlparse(url).scheme:
                await interaction.response.send_message(
                    f"Invalid {field} URL.",
                    ephemeral=True
                )
                return
        
        # Process description
        desc_lines = []
        if self.desc.value:
            desc_lines = [line.strip() for line in self.desc.value.split('\\n')]
        
        player_data = {
            "name": self.name.value.strip(),
            "region_emoji": self.region.value.strip(),
            "social_link": self.social.value.strip(),
            "image_url": self.image.value.strip(),
            "description_lines": desc_lines,
            "color_footer": f"Color for {self.name.value}"
        }
        
        # Check for duplicates
        if any(p.get("name", "").lower() == player_data["name"].lower() 
               for p in data_manager.config.notable_players):
            await interaction.response.send_message(
                f"Player '{player_data['name']}' already exists.",
                ephemeral=True
            )
            return
        
        data_manager.config.notable_players.append(player_data)
        await data_manager.save()
        
        await interaction.response.send_message(
            f"✅ Player **{player_data['name']}** added!",
            ephemeral=True
        )

# ─── Bot Instance & Commands ───────────────────────────────────────────────────

# Create bot instance
intents = discord.Intents.default()
intents.dm_messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global instances
data_manager: DataManager = None
youtube_service: YouTubeService = None

# ─── Main Commands ─────────────────────────────────────────────────────────────

@bot.tree.command(name="combos", description="Show character combo menu")
async def combos_command(interaction: discord.Interaction):
    """Main combo menu command"""
    if not data_manager:
        await interaction.response.send_message(
            "Bot is still loading, please try again.",
            ephemeral=True
        )
        return
    
    view = MainMenuView(interaction.user, data_manager.config, data_manager)
    await interaction.response.send_message(
        embed=view.create_embed(),
        view=view,
        ephemeral=True
    )
    view.message = await interaction.original_response()

@bot.tree.command(name="update", description="Update combos or add resources")
@discord.app_commands.describe(
    category="Category to update",
    playlist_or_url="YouTube playlist ID/URL or resource URL",
    starter="Starter name (for combo categories)"
)
async def update_command(interaction: discord.Interaction, 
                        category: str, 
                        playlist_or_url: str,
                        starter: Optional[str] = None):
    """Update combos or add resources"""
    # Check authorization
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    # Handle resources
    if category.lower() == "resources":
        await interaction.response.send_modal(ResourceModal(link=playlist_or_url))
        return
    
    # Validate category
    if category not in data_manager.config.combo_categories:
        await interaction.response.send_message(
            f"Invalid category. Valid categories: {', '.join(data_manager.config.combo_categories)}",
            ephemeral=True
        )
        return
    
    # Check starter
    if not starter:
        await interaction.response.send_message(
            "Starter name required for combo categories.",
            ephemeral=True
        )
        return
    
    if starter not in data_manager.config.starters.get(category, []):
        await interaction.response.send_message(
            f"Invalid starter '{starter}' for {category}.",
            ephemeral=True
        )
        return
    
    # Extract playlist ID
    playlist_id = youtube_service.extract_playlist_id(playlist_or_url)
    if not playlist_id:
        await interaction.response.send_message(
            "Invalid YouTube playlist URL or ID.",
            ephemeral=True
        )
        return
    
    # Defer for long operation
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Fetch playlist
        playlist_data = await youtube_service.fetch_playlist(playlist_id)
        
        # Convert to combo entries
        combos = []
        for video in playlist_data["videos"]:
            combos.append(ComboEntry(
                notation=video["notation"],
                notes=video["notes"],
                link=video["link"]
            ))
        
        # Update data
        await data_manager.update_combos(
            category,
            starter,
            combos,
            playlist_data["note"]
        )
        await data_manager.save(force=True)
        
        await interaction.followup.send(
            f"✅ Updated **{category} → {starter}**: "
            f"**{len(combos)}** combos from playlist.",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f"Update error: {e}")
        await interaction.followup.send(
            f"⚠️ Error: {str(e)}",
            ephemeral=True
        )

# ─── Admin Commands ────────────────────────────────────────────────────────────

admin_group = discord.app_commands.Group(
    name="admin",
    description="Admin configuration commands"
)

@admin_group.command(name="setup", description="Initial bot setup")
async def admin_setup(interaction: discord.Interaction):
    """Setup bot configuration"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    await interaction.response.send_modal(SetupModal(data_manager.config))

@admin_group.command(name="add_starter", description="Add a starter")
@discord.app_commands.describe(
    category="Combo category",
    starter="Starter name"
)
async def admin_add_starter(interaction: discord.Interaction, category: str, starter: str):
    """Add a starter to a category"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    # Validate category
    if category not in data_manager.config.combo_categories:
        await interaction.response.send_message(
            f"Invalid category. Valid categories: {', '.join(data_manager.config.combo_categories)}",
            ephemeral=True
        )
        return
    
    # Check if already exists
    if starter in data_manager.config.starters.get(category, []):
        await interaction.response.send_message(
            f"Starter '{starter}' already exists in {category}.",
            ephemeral=True
        )
        return
    
    await data_manager.add_starter(category, starter)
    await data_manager.save()
    
    await interaction.response.send_message(
        f"✅ Added starter '{starter}' to {category}.",
        ephemeral=True
    )

@admin_group.command(name="remove_starter", description="Remove a starter")
@discord.app_commands.describe(
    category="Combo category",
    starter="Starter name"
)
async def admin_remove_starter(interaction: discord.Interaction, category: str, starter: str):
    """Remove a starter from a category"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    removed_config, removed_data = await data_manager.remove_starter(category, starter)
    
    if removed_config or removed_data:
        await data_manager.save()
        
        if removed_config and removed_data:
            msg = f"✅ Removed starter '{starter}' and its combo data."
        elif removed_config:
            msg = f"✅ Removed starter '{starter}' from config."
        else:
            msg = f"✅ Removed combo data for '{starter}'."
        
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.response.send_message(
            f"Starter '{starter}' not found in {category}.",
            ephemeral=True
        )

@admin_group.command(name="add_category", description="Add a new combo category")
@discord.app_commands.describe(name="Category name")
async def admin_add_category(interaction: discord.Interaction, name: str):
    """Add a new combo category"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    if name in data_manager.config.combo_categories:
        await interaction.response.send_message(
            f"Category '{name}' already exists.",
            ephemeral=True
        )
        return
    
    data_manager.config.combo_categories.append(name)
    data_manager.config.starters[name] = []
    await data_manager.save()
    
    await interaction.response.send_message(
        f"✅ Added category '{name}'.",
        ephemeral=True
    )

@admin_group.command(name="add_player", description="Add a notable player")
async def admin_add_player(interaction: discord.Interaction):
    """Add a notable player"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    await interaction.response.send_modal(PlayerModal())

@admin_group.command(name="remove_player", description="Remove a player")
@discord.app_commands.describe(name="Player name")
async def admin_remove_player(interaction: discord.Interaction, name: str):
    """Remove a notable player"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    # Find and remove player
    original_count = len(data_manager.config.notable_players)
    data_manager.config.notable_players = [
        p for p in data_manager.config.notable_players
        if p.get("name", "").lower() != name.lower()
    ]
    
    if len(data_manager.config.notable_players) < original_count:
        await data_manager.save()
        await interaction.response.send_message(
            f"✅ Removed player '{name}'.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Player '{name}' not found.",
            ephemeral=True
        )

@admin_group.command(name="config", description="View current configuration")
async def admin_config(interaction: discord.Interaction):
    """View current bot configuration"""
    if interaction.user.id not in env_config.owner_ids:
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    config = data_manager.config
    
    embed = discord.Embed(
        title="⚙️ Bot Configuration",
        color=config.embed_color
    )
    
    embed.add_field(
        name="Basic Info",
        value=f"**Character:** {config.character_name}\n"
              f"**Color:** {config.main_embed_color_hex}\n"
              f"**Timeout:** {config.view_timeout_seconds}s",
        inline=False
    )
    
    embed.add_field(
        name="Categories",
        value=", ".join(config.combo_categories) or "None",
        inline=False
    )
    
    embed.add_field(
        name="Page Sizes",
        value=f"Starters: {config.page_sizes.starters}\n"
              f"Combos: {config.page_sizes.combos}\n"
              f"Players: {config.page_sizes.players}\n"
              f"Resources: {config.page_sizes.resources}",
        inline=False
    )
    
    embed.add_field(
        name="Info Sections",
        value=f"Ender: {config.info_section_ender_title or 'Hidden'}\n"
              f"Routes: {config.info_section_routes_title or 'Hidden'}",
        inline=False
    )
    
    embed.set_thumbnail(url=config.thumbnail_url)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── Bot Events ────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    """Bot startup"""
    global data_manager, youtube_service
    
    # Initialize services
    data_manager = DataManager(env_config.config_filename)
    youtube_service = YouTubeService(env_config.youtube_api_key)
    
    # Load data
    await data_manager.load()
    
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Configured for: {data_manager.config.character_name}")
    
    # Add command groups
    bot.tree.add_command(admin_group)
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.event
async def on_shutdown():
    """Bot shutdown cleanup"""
    if data_manager:
        await data_manager.save(force=True)
    logger.info("Bot shutting down")

# ─── Helper Functions ──────────────────────────────────────────────────────────

def create_combo_bot(config_file: str = "character_bot_data.json") -> commands.Bot:
    """Factory function to create a configured bot instance"""
    os.environ["CONFIG_FILENAME"] = config_file
    return bot

# ─── Main Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        bot.run(env_config.discord_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
