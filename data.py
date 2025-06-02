"""
Data models and data management for Combot
Handles all data persistence and validation
"""

import json
import asyncio
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

from config import BotConfiguration

logger = logging.getLogger(__name__)


@dataclass
class ComboEntry:
    """Represents a single combo with notation, notes, and video link"""
    notation: str
    notes: str
    link: str
    
    def __post_init__(self):
        """Validate combo entry data"""
        if not self.notation.strip():
            raise ValueError("Combo notation cannot be empty")
        if not self.link.strip():
            raise ValueError("Combo link cannot be empty")


@dataclass
class ResourceEntry:
    """Represents a resource with name, type, link, and optional credit"""
    name: str
    type: str
    link: str
    credit: Optional[str] = None
    
    def __post_init__(self):
        """Validate resource entry data"""
        if not self.name.strip():
            raise ValueError("Resource name cannot be empty")
        if not self.type.strip():
            raise ValueError("Resource type cannot be empty")
        if not self.link.strip():
            raise ValueError("Resource link cannot be empty")


@dataclass
class PlayerEntry:
    """Represents a notable player with all their information"""
    name: str
    region_emoji: str
    social_link: str
    image_url: str
    description_lines: List[str]
    color_footer: str
    
    def __post_init__(self):
        """Validate player entry data"""
        if not self.name.strip():
            raise ValueError("Player name cannot be empty")
        if not self.social_link.strip():
            raise ValueError("Player social link cannot be empty")


class DataManager:
    """
    Centralized async data management with validation, caching, and atomic writes
    
    Features:
    - Async file I/O with locks for thread safety
    - Debounced saves to prevent excessive disk writes
    - Atomic writes to prevent corruption
    - Data validation and error handling
    - Forced saves for critical operations
    """
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._config: Optional[BotConfiguration] = None
        self._combo_data: Dict[str, Dict[str, Any]] = {}
        self._resources: Dict[str, Any] = {"note": "Additional resources", "resources": []}
        self._lock = asyncio.Lock()
        self._dirty = False
        self._last_save = time.time()
        self._save_interval = 5.0  # Debounce saves for 5 seconds
        self._save_task: Optional[asyncio.Task] = None
    
    async def load(self) -> None:
        """Load data from file with error handling and validation"""
        async with self._lock:
            data = {}
            
            if self.file_path.exists():
                try:
                    # Use asyncio.to_thread for proper async file reading
                    content = await asyncio.to_thread(
                        self.file_path.read_text, 
                        encoding='utf-8'
                    )
                    data = json.loads(content)
                    logger.info(f"Loaded existing data from {self.file_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in data file: {e}")
                    # Create backup of corrupted file
                    backup_path = self.file_path.with_suffix('.json.corrupted')
                    await asyncio.to_thread(
                        self.file_path.rename, 
                        backup_path
                    )
                    logger.info(f"Corrupted file backed up to {backup_path}")
                    data = {}
                except Exception as e:
                    logger.error(f"Error loading data file: {e}")
                    data = {}
            else:
                logger.info(f"Creating new data file: {self.file_path}")
            
            # Load and validate configuration
            config_data = data.get("config", {})
            try:
                self._config = BotConfiguration.from_dict(config_data)
            except Exception as e:
                logger.error(f"Error loading configuration: {e}")
                self._config = BotConfiguration()
            
            # Initialize combo data structures
            for category in self._config.combo_categories:
                if category not in self._config.starters:
                    self._config.starters[category] = []
                self._combo_data[category] = data.get(category, {})
            
            # Load resources with validation
            try:
                self._resources = data.get("RESOURCES", {
                    "note": "Additional resources", 
                    "resources": []
                })
                # Validate resource structure
                if not isinstance(self._resources.get("resources", []), list):
                    self._resources["resources"] = []
            except Exception as e:
                logger.error(f"Error loading resources: {e}")
                self._resources = {"note": "Additional resources", "resources": []}
            
            logger.info(f"Data loaded successfully for: {self._config.character_name}")
            logger.info(f"Categories: {len(self._config.combo_categories)}")
            logger.info(f"Resources: {len(self._resources.get('resources', []))}")
            logger.info(f"Notable players: {len(self._config.notable_players)}")
    
    async def save(self, force: bool = False) -> None:
        """
        Save data to file with debouncing and atomic writes
        
        Args:
            force: If True, save immediately regardless of debouncing
        """
        now = time.time()
        
        # Skip if not dirty and not forced
        if not force and not self._dirty:
            return
        
        # If not forced and within debounce interval, schedule delayed save
        if not force and now - self._last_save < self._save_interval:
            if not self._save_task or self._save_task.done():
                self._save_task = asyncio.create_task(self._delayed_save())
            return
        
        # Cancel any pending delayed save
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        
        async with self._lock:
            try:
                # Prepare data for saving
                data = {
                    "config": self._config.to_dict() if self._config else {},
                    "RESOURCES": self._resources
                }
                
                # Add combo data for each category
                for category, combos in self._combo_data.items():
                    data[category] = combos
                
                # Atomic write using temporary file
                temp_file = self.file_path.with_suffix('.tmp')
                
                def write_file():
                    """Synchronous file write operation"""
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    # Atomic replace
                    temp_file.replace(self.file_path)
                
                # Execute write in thread pool
                await asyncio.to_thread(write_file)
                
                self._dirty = False
                self._last_save = now
                logger.info(f"Data saved successfully to {self.file_path}")
                
            except Exception as e:
                logger.error(f"Error saving data: {e}")
                # Clean up temp file if it exists
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
                raise
    
    async def _delayed_save(self) -> None:
        """Execute delayed save after debounce interval"""
        try:
            await asyncio.sleep(self._save_interval)
            await self.save()
        except asyncio.CancelledError:
            pass  # Save was cancelled, probably because immediate save was triggered
        except Exception as e:
            logger.error(f"Error in delayed save: {e}")
    
    @property
    def config(self) -> BotConfiguration:
        """Get current configuration with validation"""
        if not self._config:
            raise RuntimeError("DataManager not loaded. Call load() first.")
        return self._config
    
    async def update_config(self, **kwargs) -> None:
        """
        Update configuration fields with validation
        
        Args:
            **kwargs: Configuration fields to update
        """
        async with self._lock:
            updated_fields = []
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                    updated_fields.append(key)
                else:
                    logger.warning(f"Attempted to update unknown config field: {key}")
            
            if updated_fields:
                self._dirty = True
                logger.info(f"Updated config fields: {', '.join(updated_fields)}")
    
    async def get_combos(self, category: str, starter: str) -> List[ComboEntry]:
        """
        Get combos for a category/starter combination
        
        Args:
            category: Combo category
            starter: Starter name
            
        Returns:
            List of ComboEntry objects
        """
        try:
            combos_data = self._combo_data.get(category, {}).get(starter, {}).get("combos", [])
            return [ComboEntry(**c) for c in combos_data]
        except Exception as e:
            logger.error(f"Error loading combos for {category}/{starter}: {e}")
            return []
    
    async def update_combos(self, category: str, starter: str, 
                          combos: List[ComboEntry], note: str = "") -> None:
        """
        Update combos for a category/starter combination
        
        Args:
            category: Combo category
            starter: Starter name
            combos: List of ComboEntry objects
            note: Optional note about the combo set
        """
        async with self._lock:
            if category not in self._combo_data:
                self._combo_data[category] = {}
            
            # Validate combo entries
            validated_combos = []
            for combo in combos:
                try:
                    # Re-create to trigger validation
                    validated_combo = ComboEntry(
                        notation=combo.notation,
                        notes=combo.notes,
                        link=combo.link
                    )
                    validated_combos.append(asdict(validated_combo))
                except ValueError as e:
                    logger.warning(f"Invalid combo skipped: {e}")
            
            self._combo_data[category][starter] = {
                "note": note or f"Combos for {starter}",
                "combos": validated_combos
            }
            self._dirty = True
            logger.info(f"Updated {len(validated_combos)} combos for {category}/{starter}")
    
    async def get_resources(self) -> Tuple[str, List[ResourceEntry]]:
        """
        Get all resources
        
        Returns:
            Tuple of (note, list of ResourceEntry objects)
        """
        try:
            note = self._resources.get("note", "")
            resources_data = self._resources.get("resources", [])
            resources = []
            
            for r_data in resources_data:
                try:
                    resources.append(ResourceEntry(**r_data))
                except Exception as e:
                    logger.warning(f"Invalid resource skipped: {e}")
            
            return note, resources
        except Exception as e:
            logger.error(f"Error loading resources: {e}")
            return "", []
    
    async def add_resource(self, resource: ResourceEntry) -> None:
        """
        Add a new resource
        
        Args:
            resource: ResourceEntry object to add
        """
        async with self._lock:
            try:
                # Validate resource
                validated_resource = ResourceEntry(
                    name=resource.name,
                    type=resource.type,
                    link=resource.link,
                    credit=resource.credit
                )
                
                self._resources.setdefault("resources", []).append(asdict(validated_resource))
                self._dirty = True
                logger.info(f"Added resource: {resource.name}")
                
            except ValueError as e:
                logger.error(f"Invalid resource rejected: {e}")
                raise
    
    async def add_starter(self, category: str, starter: str) -> None:
        """
        Add a starter to a category
        
        Args:
            category: Category name
            starter: Starter name
        """
        async with self._lock:
            if category not in self._config.starters:
                self._config.starters[category] = []
            
            if starter not in self._config.starters[category]:
                self._config.starters[category].append(starter)
                self._dirty = True
                logger.info(f"Added starter '{starter}' to category '{category}'")
    
    async def remove_starter(self, category: str, starter: str) -> Tuple[bool, bool]:
        """
        Remove a starter and its associated data
        
        Args:
            category: Category name
            starter: Starter name
            
        Returns:
            Tuple of (removed_from_config, removed_combo_data)
        """
        async with self._lock:
            removed_config = False
            removed_data = False
            
            # Remove from config
            if (category in self._config.starters and 
                starter in self._config.starters[category]):
                self._config.starters[category].remove(starter)
                removed_config = True
            
            # Remove combo data
            if (category in self._combo_data and 
                starter in self._combo_data[category]):
                del self._combo_data[category][starter]
                removed_data = True
            
            if removed_config or removed_data:
                self._dirty = True
                logger.info(f"Removed starter '{starter}' from '{category}' "
                          f"(config: {removed_config}, data: {removed_data})")
            
            return removed_config, removed_data
    
    async def get_combo_count(self, category: str, starter: str) -> int:
        """
        Get the number of combos for a specific starter
        
        Args:
            category: Category name
            starter: Starter name
            
        Returns:
            Number of combos
        """
        try:
            combos = await self.get_combos(category, starter)
            return len(combos)
        except Exception:
            return 0
    
    async def cleanup(self) -> None:
        """Cleanup method to ensure data is saved on shutdown"""
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        await self.save(force=True)
        logger.info("DataManager cleanup completed")
