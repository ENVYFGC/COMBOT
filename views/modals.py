"""
Modal input forms for Discord UI
Handles all user input modals with proper data manager injection
"""

import logging
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

import discord
from discord.ui import Modal, TextInput

from utils import validate_url, validate_discord_color_hex
from data import ResourceEntry

if TYPE_CHECKING:
    from data import DataManager
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class BaseModal(Modal):
    """
    Base modal with improved error handling and data manager injection
    
    This fixes the issue mentioned in the review about using global data_manager
    """
    
    def __init__(self, data_manager: 'DataManager', title: str = "Input Form", timeout: float = 300.0):
        """
        Initialize base modal
        
        Args:
            data_manager: DataManager instance to use for operations
            title: Modal title
            timeout: Modal timeout in seconds
        """
        super().__init__(title=title, timeout=timeout)
        self.data_manager = data_manager
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors with logging and user feedback"""
        logger.error(f"Modal error in {self.__class__.__name__}: {error}", exc_info=True)
        
        error_message = "❌ An error occurred while processing your input. Please try again."
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as follow_error:
            logger.error(f"Failed to send modal error message: {follow_error}")


class SetupModal(BaseModal, title="Bot Setup"):
    """
    Initial bot setup modal with comprehensive validation
    
    Features:
    - Character name configuration
    - Thumbnail URL validation
    - Color hex validation
    - Info section title configuration
    """
    
    def __init__(self, data_manager: 'DataManager', current_config: 'BotConfiguration'):
        """
        Initialize setup modal
        
        Args:
            data_manager: DataManager instance
            current_config: Current bot configuration
        """
        super().__init__(data_manager, "Bot Setup")
        
        self.char_name = TextInput(
            label="Character Name",
            placeholder="e.g., Carmine, Sol Badguy, Ryu",
            default=current_config.character_name,
            required=True,
            max_length=50
        )
        
        self.thumbnail = TextInput(
            label="Thumbnail URL (optional)",
            placeholder="https://i.imgur.com/example.png",
            default=current_config.thumbnail_url,
            required=False,
            max_length=500
        )
        
        self.color = TextInput(
            label="Embed Color (hex, without #)",
            placeholder="FF0000 for red, 00FF00 for green",
            default=current_config.main_embed_color_hex.replace("0x", ""),
            required=False,
            max_length=6
        )
        
        self.ender_title = TextInput(
            label="Ender Info Section Title (blank to hide)",
            placeholder="📑 Ender Optimization",
            default=current_config.info_section_ender_title,
            required=False,
            max_length=50
        )
        
        self.routes_title = TextInput(
            label="Routes Section Title (blank to hide)",
            placeholder="✨ Special Routes",
            default=current_config.info_section_routes_title,
            required=False,
            max_length=50
        )
        
        self.add_item(self.char_name)
        self.add_item(self.thumbnail)
        self.add_item(self.color)
        self.add_item(self.ender_title)
        self.add_item(self.routes_title)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle setup form submission with validation"""
        try:
            # Validate character name
            char_name = self.char_name.value.strip()
            if not char_name:
                await interaction.response.send_message(
                    "❌ Character name is required.",
                    ephemeral=True
                )
                return
            
            # Validate thumbnail URL
            thumbnail = self.thumbnail.value.strip()
            if thumbnail and not validate_url(thumbnail):
                await interaction.response.send_message(
                    "❌ Invalid thumbnail URL. Please provide a valid HTTP/HTTPS URL.",
                    ephemeral=True
                )
                return
            
            # Validate color hex
            color = self.color.value.strip()
            normalized_color = None
            if color:
                normalized_color = validate_discord_color_hex(color)
                if not normalized_color:
                    await interaction.response.send_message(
                        "❌ Invalid color hex value. Please use 6-digit hex format (e.g., FF0000).",
                        ephemeral=True
                    )
                    return
            
            # Update configuration
            updates = {
                'character_name': char_name,
                'info_section_ender_title': self.ender_title.value.strip(),
                'info_section_routes_title': self.routes_title.value.strip()
            }
            
            if thumbnail:
                updates['thumbnail_url'] = thumbnail
            
            if normalized_color:
                updates['main_embed_color_hex'] = normalized_color
            
            await self.data_manager.update_config(**updates)
            await self.data_manager.save(force=True)
            
            logger.info(f"Bot setup completed for character: {char_name}")
            
            await interaction.response.send_message(
                f"✅ Bot configured successfully for **{char_name}**!\n"
                f"Use `/combos` to see your new setup.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in setup modal: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while saving the configuration. Please try again.",
                ephemeral=True
            )


class ResourceModal(BaseModal, title="Add Resource"):
    """
    Modal for adding general resources with validation
    
    Features:
    - Resource name and type specification
    - URL validation
    - Optional credit/source attribution
    """
    
    def __init__(self, data_manager: 'DataManager', link: str = ""):
        """
        Initialize resource modal
        
        Args:
            data_manager: DataManager instance
            link: Pre-filled link if available
        """
        super().__init__(data_manager, "Add Resource")
        
        self.name = TextInput(
            label="Resource Name",
            placeholder="e.g., Frame Data Guide, Combo Video",
            required=True,
            max_length=100
        )
        
        self.type = TextInput(
            label="Resource Type",
            placeholder="e.g., video, document, spreadsheet, guide",
            required=True,
            max_length=50
        )
        
        self.link = TextInput(
            label="Resource URL",
            placeholder="https://example.com/resource",
            default=link,
            required=True,
            max_length=500
        )
        
        self.credit = TextInput(
            label="Credit/Source (optional)",
            placeholder="e.g., Created by PlayerName, From FGC Wiki",
            required=False,
            max_length=100
        )
        
        self.add_item(self.name)
        self.add_item(self.type)
        self.add_item(self.link)
        self.add_item(self.credit)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle resource submission with validation"""
        try:
            # Validate inputs
            name = self.name.value.strip()
            resource_type = self.type.value.strip()
            link = self.link.value.strip()
            credit = self.credit.value.strip() if self.credit.value else None
            
            if not name:
                await interaction.response.send_message(
                    "❌ Resource name is required.",
                    ephemeral=True
                )
                return
            
            if not resource_type:
                await interaction.response.send_message(
                    "❌ Resource type is required.",
                    ephemeral=True
                )
                return
            
            if not validate_url(link):
                await interaction.response.send_message(
                    "❌ Invalid URL. Please provide a valid HTTP/HTTPS URL.",
                    ephemeral=True
                )
                return
            
            # Create and add resource
            resource = ResourceEntry(
                name=name,
                type=resource_type,
                link=link,
                credit=credit
            )
            
            await self.data_manager.add_resource(resource)
            await self.data_manager.save()
            
            logger.info(f"Resource added: {name} ({resource_type})")
            
            await interaction.response.send_message(
                f"✅ Resource **{name}** ({resource_type}) added successfully!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error adding resource: {e}")
            await interaction.response.send_message(
                "❌ Failed to add resource. Please check your input and try again.",
                ephemeral=True
            )


class PlayerModal(BaseModal, title="Add Notable Player"):
    """
    Modal for adding notable players with comprehensive validation
    
    Features:
    - Player name and region specification
    - Social media link validation
    - Character image URL validation
    - Multi-line description support
    """
    
    def __init__(self, data_manager: 'DataManager'):
        """
        Initialize player modal
        
        Args:
            data_manager: DataManager instance
        """
        super().__init__(data_manager, "Add Notable Player", timeout=600.0)  # Longer timeout for complex form
        
        self.name = TextInput(
            label="Player Name",
            placeholder="e.g., Daigo, SonicFox, Tokido",
            required=True,
            max_length=50
        )
        
        self.region = TextInput(
            label="Region Emoji",
            placeholder="🇺🇸 🇯🇵 🇰🇷 etc.",
            required=True,
            max_length=10
        )
        
        self.social = TextInput(
            label="Social Media Link",
            placeholder="https://twitter.com/player or https://youtube.com/@player",
            required=True,
            max_length=200
        )
        
        self.image = TextInput(
            label="Character Image URL",
            placeholder="https://i.imgur.com/character.png",
            required=True,
            max_length=500
        )
        
        self.desc = TextInput(
            label="Description (use \\n for line breaks)",
            placeholder="Famous for X combo\\nWon Y tournament\\nKnown for Z playstyle",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=800
        )
        
        self.add_item(self.name)
        self.add_item(self.region)
        self.add_item(self.social)
        self.add_item(self.image)
        self.add_item(self.desc)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle player submission with validation"""
        try:
            # Validate inputs
            name = self.name.value.strip()
            region_emoji = self.region.value.strip()
            social_link = self.social.value.strip()
            image_url = self.image.value.strip()
            description = self.desc.value.strip() if self.desc.value else ""
            
            if not name:
                await interaction.response.send_message(
                    "❌ Player name is required.",
                    ephemeral=True
                )
                return
            
            if not region_emoji:
                await interaction.response.send_message(
                    "❌ Region emoji is required.",
                    ephemeral=True
                )
                return
            
            # Validate URLs
            if not validate_url(social_link):
                await interaction.response.send_message(
                    "❌ Invalid social media URL. Please provide a valid HTTP/HTTPS URL.",
                    ephemeral=True
                )
                return
            
            if not validate_url(image_url):
                await interaction.response.send_message(
                    "❌ Invalid image URL. Please provide a valid HTTP/HTTPS URL.",
                    ephemeral=True
                )
                return
            
            # Check for duplicate players
            existing_players = self.data_manager.config.notable_players
            if any(p.get("name", "").lower() == name.lower() for p in existing_players):
                await interaction.response.send_message(
                    f"❌ Player **{name}** already exists in the database.",
                    ephemeral=True
                )
                return
            
            # Process description
            description_lines = []
            if description:
                # Split by \\n for line breaks
                lines = description.split('\\n')
                description_lines = [line.strip() for line in lines if line.strip()]
            
            # Create player data
            player_data = {
                "name": name,
                "region_emoji": region_emoji,
                "social_link": social_link,
                "image_url": image_url,
                "description_lines": description_lines,
                "color_footer": f"{name}'s playstyle"
            }
            
            # Add player to configuration
            self.data_manager.config.notable_players.append(player_data)
            await self.data_manager.save(force=True)
            
            logger.info(f"Notable player added: {name} ({region_emoji})")
            
            await interaction.response.send_message(
                f"✅ Notable player **{name}** {region_emoji} added successfully!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error adding player: {e}")
            await interaction.response.send_message(
                "❌ Failed to add player. Please check your input and try again.",
                ephemeral=True
            )


class EditConfigModal(BaseModal, title="Edit Configuration"):
    """
    Modal for editing specific configuration values
    """
    
    def __init__(self, data_manager: 'DataManager', field_name: str, current_value: str, description: str = ""):
        """
        Initialize config edit modal
        
        Args:
            data_manager: DataManager instance
            field_name: Configuration field to edit
            current_value: Current value of the field
            description: Description of what this field does
        """
        super().__init__(data_manager, f"Edit {field_name.replace('_', ' ').title()}")
        self.field_name = field_name
        
        self.value_input = TextInput(
            label=field_name.replace('_', ' ').title(),
            placeholder=description or f"Enter new {field_name}",
            default=str(current_value),
            required=True,
            max_length=500
        )
        
        self.add_item(self.value_input)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle configuration edit submission"""
        try:
            new_value = self.value_input.value.strip()
            
            if not new_value:
                await interaction.response.send_message(
                    "❌ Value cannot be empty.",
                    ephemeral=True
                )
                return
            
            # Update configuration
            await self.data_manager.update_config(**{self.field_name: new_value})
            await self.data_manager.save(force=True)
            
            logger.info(f"Configuration updated: {self.field_name} = {new_value}")
            
            await interaction.response.send_message(
                f"✅ Updated **{self.field_name.replace('_', ' ').title()}** successfully!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            await interaction.response.send_message(
                "❌ Failed to update configuration. Please try again.",
                ephemeral=True
            )
