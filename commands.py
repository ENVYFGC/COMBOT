"""
Discord bot commands for Combot
All slash commands and admin functionality
"""

import logging
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from config import env_config
from views.main_menu import MainMenuView
from views.modals import SetupModal, ResourceModal, PlayerModal
from youtube import YouTubeService

if TYPE_CHECKING:
    from data import DataManager

logger = logging.getLogger(__name__)


class CombotCommands(commands.Cog):
    """
    Main command cog for Combot with improved error handling and validation
    """
    
    def __init__(self, bot: commands.Bot, data_manager: 'DataManager', youtube_service: YouTubeService):
        """
        Initialize commands cog
        
        Args:
            bot: Discord bot instance
            data_manager: DataManager instance
            youtube_service: YouTubeService instance
        """
        self.bot = bot
        self.data_manager = data_manager
        self.youtube_service = youtube_service
    
    @app_commands.command(name="combos", description="Show character combo menu")
    async def combos_command(self, interaction: discord.Interaction):
        """Main combo menu command with state validation"""
        try:
            # Check if data manager is ready
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Create and show main menu
            view = MainMenuView(interaction.user, self.data_manager.config, self.data_manager)
            await interaction.response.send_message(
                embed=view.create_embed(),
                view=view,
                ephemeral=True
            )
            view.message = await interaction.original_response()
            
            logger.info(f"Combo menu opened by {interaction.user} ({interaction.user.id})")
            
        except Exception as e:
            logger.error(f"Error in combos command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to open combo menu. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="update", description="Update combos or add resources")
    @app_commands.describe(
        category="Category to update (or 'resources' for adding resources)",
        playlist_or_url="YouTube playlist ID/URL or resource URL",
        starter="Starter name (required for combo categories)"
    )
    async def update_command(self, interaction: discord.Interaction, 
                           category: str, 
                           playlist_or_url: str,
                           starter: Optional[str] = None):
        """
        Update combos or add resources with comprehensive validation
        """
        try:
            # Check authorization
            if interaction.user.id not in env_config.owner_ids:
                await interaction.response.send_message(
                    "❌ You don't have permission to use this command.",
                    ephemeral=True
                )
                return
            
            # Check if data manager is ready
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Handle resources
            if category.lower() == "resources":
                modal = ResourceModal(self.data_manager, link=playlist_or_url)
                await interaction.response.send_modal(modal)
                return
            
            # Validate category for combos
            if category not in self.data_manager.config.combo_categories:
                valid_categories = ", ".join(self.data_manager.config.combo_categories)
                await interaction.response.send_message(
                    f"❌ Invalid category **{category}**.\n"
                    f"Valid categories: {valid_categories}",
                    ephemeral=True
                )
                return
            
            # Check starter requirement
            if not starter:
                await interaction.response.send_message(
                    "❌ Starter name is required for combo categories.\n"
                    f"Usage: `/update {category} <playlist_url> <starter_name>`",
                    ephemeral=True
                )
                return
            
            # Validate starter exists
            if starter not in self.data_manager.config.starters.get(category, []):
                available_starters = self.data_manager.config.starters.get(category, [])
                if available_starters:
                    starters_list = ", ".join(available_starters)
                    await interaction.response.send_message(
                        f"❌ Invalid starter **{starter}** for {category}.\n"
                        f"Available starters: {starters_list}",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ No starters configured for {category}.\n"
                        f"Use `/admin add_starter` to add starters first.",
                        ephemeral=True
                    )
                return
            
            # Extract and validate playlist ID
            playlist_id = self.youtube_service.extract_playlist_id(playlist_or_url)
            if not playlist_id:
                await interaction.response.send_message(
                    "❌ Invalid YouTube playlist URL or ID.\n"
                    "Please provide a valid YouTube playlist URL like:\n"
                    "`https://www.youtube.com/playlist?list=PLxxxxxx`",
                    ephemeral=True
                )
                return
            
            # Defer for long operation
            await interaction.response.defer(ephemeral=True)
            
            # Fetch playlist data
            try:
                playlist_data = await self.youtube_service.fetch_playlist(playlist_id)
                
                # Convert to combo entries
                from data import ComboEntry
                combos = []
                for video in playlist_data["videos"]:
                    try:
                        combo = ComboEntry(
                            notation=video["notation"],
                            notes=video["notes"],
                            link=video["link"]
                        )
                        combos.append(combo)
                    except ValueError as ve:
                        logger.warning(f"Invalid combo data skipped: {ve}")
                        continue
                
                if not combos:
                    await interaction.followup.send(
                        f"⚠️ No valid combos found in playlist **{playlist_data.get('title', playlist_id)}**.\n"
                        f"Please ensure the playlist contains videos with proper notation in descriptions.",
                        ephemeral=True
                    )
                    return
                
                # Update data
                await self.data_manager.update_combos(
                    category,
                    starter,
                    combos,
                    playlist_data["note"]
                )
                await self.data_manager.save(force=True)
                
                # Success message
                playlist_title = playlist_data.get('title', 'Unknown Playlist')
                await interaction.followup.send(
                    f"✅ **Successfully updated {category} → {starter}**\n\n"
                    f"📜 **Playlist:** {playlist_title}\n"
                    f"🎯 **Combos Added:** {len(combos)}\n"
                    f"📝 **Note:** {playlist_data['note']}\n\n"
                    f"Use `/combos` to view the updated combos!",
                    ephemeral=True
                )
                
                logger.info(f"Updated {category}/{starter} with {len(combos)} combos by {interaction.user}")
                
            except ValueError as e:
                await interaction.followup.send(
                    f"❌ **Error fetching playlist:**\n{str(e)}",
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Update command error: {e}", exc_info=True)
                await interaction.followup.send(
                    "❌ An unexpected error occurred while updating. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in update command: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing the update command.",
                    ephemeral=True
                )


class AdminCommands(commands.Cog):
    """
    Admin command group with comprehensive management features
    """
    
    def __init__(self, bot: commands.Bot, data_manager: 'DataManager'):
        """
        Initialize admin commands cog
        
        Args:
            bot: Discord bot instance
            data_manager: DataManager instance
        """
        self.bot = bot
        self.data_manager = data_manager
    
    def _check_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in env_config.owner_ids
    
    @app_commands.command(name="setup", description="Initial bot setup")
    async def admin_setup(self, interaction: discord.Interaction):
        """Setup bot configuration with validation"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            modal = SetupModal(self.data_manager, self.data_manager.config)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in admin setup: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to open setup form. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="add_starter", description="Add a starter to a category")
    @app_commands.describe(
        category="Combo category",
        starter="Starter name"
    )
    async def admin_add_starter(self, interaction: discord.Interaction, 
                              category: str, starter: str):
        """Add a starter to a category with validation"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Validate category
            if category not in self.data_manager.config.combo_categories:
                valid_categories = ", ".join(self.data_manager.config.combo_categories)
                await interaction.response.send_message(
                    f"❌ Invalid category **{category}**.\n"
                    f"Valid categories: {valid_categories}",
                    ephemeral=True
                )
                return
            
            # Validate starter name
            starter = starter.strip()
            if not starter:
                await interaction.response.send_message(
                    "❌ Starter name cannot be empty.",
                    ephemeral=True
                )
                return
            
            # Check if already exists
            if starter in self.data_manager.config.starters.get(category, []):
                await interaction.response.send_message(
                    f"❌ Starter **{starter}** already exists in {category}.",
                    ephemeral=True
                )
                return
            
            # Add starter
            await self.data_manager.add_starter(category, starter)
            await self.data_manager.save(force=True)
            
            await interaction.response.send_message(
                f"✅ Added starter **{starter}** to {category}.\n"
                f"Use `/update {category} <playlist_url> {starter}` to add combos.",
                ephemeral=True
            )
            
            logger.info(f"Added starter {starter} to {category} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error adding starter: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to add starter. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="remove_starter", description="Remove a starter from a category")
    @app_commands.describe(
        category="Combo category",
        starter="Starter name to remove"
    )
    async def admin_remove_starter(self, interaction: discord.Interaction, 
                                 category: str, starter: str):
        """Remove a starter and its data with confirmation"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Validate inputs
            if category not in self.data_manager.config.combo_categories:
                await interaction.response.send_message(
                    f"❌ Invalid category: {category}",
                    ephemeral=True
                )
                return
            
            if starter not in self.data_manager.config.starters.get(category, []):
                await interaction.response.send_message(
                    f"❌ Starter **{starter}** not found in {category}.",
                    ephemeral=True
                )
                return
            
            # Remove starter
            removed_config, removed_data = await self.data_manager.remove_starter(category, starter)
            
            if removed_config or removed_data:
                await self.data_manager.save(force=True)
                
                result_msg = f"✅ Removed starter **{starter}** from {category}"
                if removed_data:
                    result_msg += " and deleted its combo data"
                result_msg += "."
                
                await interaction.response.send_message(result_msg, ephemeral=True)
                logger.info(f"Removed starter {starter} from {category} by {interaction.user}")
            else:
                await interaction.response.send_message(
                    f"⚠️ Starter **{starter}** was not found to remove.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error removing starter: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to remove starter. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="add_category", description="Add a new combo category")
    @app_commands.describe(name="Category name")
    async def admin_add_category(self, interaction: discord.Interaction, name: str):
        """Add a new combo category with validation"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Validate category name
            name = name.strip()
            if not name:
                await interaction.response.send_message(
                    "❌ Category name cannot be empty.",
                    ephemeral=True
                )
                return
            
            if name in self.data_manager.config.combo_categories:
                await interaction.response.send_message(
                    f"❌ Category **{name}** already exists.",
                    ephemeral=True
                )
                return
            
            # Add category
            self.data_manager.config.combo_categories.append(name)
            self.data_manager.config.starters[name] = []
            await self.data_manager.save(force=True)
            
            await interaction.response.send_message(
                f"✅ Added category **{name}**.\n"
                f"Use `/admin add_starter {name} <starter_name>` to add starters.",
                ephemeral=True
            )
            
            logger.info(f"Added category {name} by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error adding category: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to add category. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="add_player", description="Add a notable player")
    async def admin_add_player(self, interaction: discord.Interaction):
        """Add a notable player using modal"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            modal = PlayerModal(self.data_manager)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in add player: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to open add player form. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="remove_player", description="Remove a notable player")
    @app_commands.describe(name="Player name to remove")
    async def admin_remove_player(self, interaction: discord.Interaction, name: str):
        """Remove a notable player with validation"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            # Find and remove player
            name = name.strip()
            original_count = len(self.data_manager.config.notable_players)
            
            self.data_manager.config.notable_players = [
                p for p in self.data_manager.config.notable_players
                if p.get("name", "").lower() != name.lower()
            ]
            
            if len(self.data_manager.config.notable_players) < original_count:
                await self.data_manager.save(force=True)
                await interaction.response.send_message(
                    f"✅ Removed player **{name}**.",
                    ephemeral=True
                )
                logger.info(f"Removed player {name} by {interaction.user}")
            else:
                await interaction.response.send_message(
                    f"❌ Player **{name}** not found.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error removing player: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to remove player. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="config", description="View current bot configuration")
    async def admin_config(self, interaction: discord.Interaction):
        """View current bot configuration with detailed information"""
        try:
            if not self._check_admin(interaction.user.id):
                await interaction.response.send_message(
                    "❌ You don't have permission to use admin commands.",
                    ephemeral=True
                )
                return
            
            if not self.data_manager:
                await interaction.response.send_message(
                    "⏳ Bot is still initializing. Please try again in a moment.",
                    ephemeral=True
                )
                return
            
            config = self.data_manager.config
            
            embed = discord.Embed(
                title="⚙️ Bot Configuration",
                color=config.embed_color
            )
            
            # Basic info
            embed.add_field(
                name="🎮 Basic Info",
                value=f"**Character:** {config.character_name}\n"
                      f"**Color:** {config.main_embed_color_hex}\n"
                      f"**Timeout:** {config.view_timeout_seconds}s",
                inline=False
            )
            
            # Categories and starters
            categories_info = []
            for category in config.combo_categories:
                starter_count = len(config.starters.get(category, []))
                categories_info.append(f"**{category}:** {starter_count} starters")
            
            embed.add_field(
                name="📂 Categories",
                value="\n".join(categories_info) if categories_info else "None configured",
                inline=False
            )
            
            # Page sizes
            embed.add_field(
                name="📄 Page Sizes",
                value=f"Starters: {config.page_sizes.starters}\n"
                      f"Combos: {config.page_sizes.combos}\n"
                      f"Players: {config.page_sizes.players}\n"
                      f"Resources: {config.page_sizes.resources}",
                inline=True
            )
            
            # Info sections
            embed.add_field(
                name="ℹ️ Info Sections",
                value=f"Ender: {config.info_section_ender_title or 'Hidden'}\n"
                      f"Routes: {config.info_section_routes_title or 'Hidden'}",
                inline=True
            )
            
            # Stats
            total_starters = sum(len(starters) for starters in config.starters.values())
            embed.add_field(
                name="📊 Stats",
                value=f"Total Starters: {total_starters}\n"
                      f"Notable Players: {len(config.notable_players)}",
                inline=True
            )
            
            embed.set_thumbnail(url=config.thumbnail_url)
            embed.set_footer(text=f"Configuration for {config.character_name}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in config command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Failed to load configuration. Please try again.",
                ephemeral=True
            )


def setup_commands(bot: commands.Bot, data_manager: 'DataManager', youtube_service: YouTubeService):
    """
    Setup all bot commands
    
    Args:
        bot: Discord bot instance
        data_manager: DataManager instance
        youtube_service: YouTubeService instance
    """
    try:
        # Add main commands
        main_cog = CombotCommands(bot, data_manager, youtube_service)
        
        # Add admin commands as a group
        admin_cog = AdminCommands(bot, data_manager)
        
        # Create admin command group
        admin_group = app_commands.Group(
            name="admin",
            description="Admin configuration commands"
        )
        
        # Add admin commands to group
        admin_group.add_command(admin_cog.admin_setup)
        admin_group.add_command(admin_cog.admin_add_starter)
        admin_group.add_command(admin_cog.admin_remove_starter)
        admin_group.add_command(admin_cog.admin_add_category)
        admin_group.add_command(admin_cog.admin_add_player)
        admin_group.add_command(admin_cog.admin_remove_player)
        admin_group.add_command(admin_cog.admin_config)
        
        # Add commands to bot
        bot.tree.add_command(main_cog.combos_command)
        bot.tree.add_command(main_cog.update_command)
        bot.tree.add_command(admin_group)
        
        logger.info("Commands setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error setting up commands: {e}", exc_info=True)
        raise
