"""
Player list and detail views with bug fixes
This addresses the PlayerListView instantiation bug mentioned in the review
"""

import logging
from typing import Dict, List, Any, TYPE_CHECKING

import discord
from discord.ui import Button

from views.base import PaginatedView, BaseView

if TYPE_CHECKING:
    from data import DataManager
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class PlayerListView(PaginatedView):
    """
    View for displaying notable players with pagination
    
    Fixed: Now properly accepts data_manager parameter as mentioned in review
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', players: List[Dict[str, Any]]):
        """
        Initialize player list view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
            players: List of player dictionaries
        """
        super().__init__(user, players, config.page_sizes.players, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add player selection buttons for current page"""
        try:
            for i, player in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                name = player.get('name', 'Unknown Player')
                emoji = player.get('region_emoji', '')
                
                # Create button label with length validation
                button_label = f"{global_index + 1}. {name} {emoji}"
                if len(button_label) > 80:  # Discord button label limit
                    button_label = f"{global_index + 1}. {name[:50]}... {emoji}"
                
                btn = Button(
                    label=button_label,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"player_{global_index}"
                )
                btn.callback = self._make_player_callback(global_index)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding player buttons: {e}")
    
    def _make_player_callback(self, index: int):
        """Create callback for player selection button"""
        async def callback(interaction: discord.Interaction):
            try:
                # Validate index
                if index >= len(self.items):
                    await interaction.response.send_message(
                        "❌ Invalid player selection.",
                        ephemeral=True
                    )
                    return
                
                # Create player detail view
                view = PlayerDetailView(
                    self.user,
                    self.config,
                    self.data_manager,  # Pass data_manager to fix the bug
                    self.items,
                    index
                )
                
                self.stop()
                await interaction.response.edit_message(
                    embed=view.create_embed(),
                    view=view
                )
                view.message = interaction.message
                
            except Exception as e:
                logger.error(f"Error in player callback: {e}")
                await interaction.response.send_message(
                    "❌ Failed to display player details. Please try again.",
                    ephemeral=True
                )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to resource menu"""
        try:
            from views.resource import ResourceMenuView
            
            self.stop()
            view = ResourceMenuView(self.user, self.config, self.data_manager)
            await interaction.response.edit_message(
                embed=view.create_embed(),
                view=view
            )
            view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error returning to resource menu: {e}")
            await interaction.response.send_message(
                "❌ Failed to return to menu. Please try again.",
                ephemeral=True
            )
    
    async def create_embed(self) -> discord.Embed:
        """Create player list embed"""
        try:
            embed = discord.Embed(
                title=f"✨ Notable Players (Page {self.current_page + 1}/{self.max_pages})",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            if not self.items:
                embed.description = "_No notable players configured yet._"
            else:
                descriptions = []
                for i, player in enumerate(self.current_items):
                    global_index = self.current_page * self.per_page + i
                    name = player.get('name', 'Unknown Player')
                    emoji = player.get('region_emoji', '')
                    descriptions.append(f"**{global_index + 1}. {name}** {emoji}")
                
                embed.description = "\n".join(descriptions) + "\n\n**Select a player for details.**"
            
            embed.set_footer(text=self.get_page_info())
            return embed
            
        except Exception as e:
            logger.error(f"Error creating player list embed: {e}")
            # Return a basic error embed
            return discord.Embed(
                title="❌ Error",
                description="Failed to load player list.",
                color=discord.Color.red()
            )


class PlayerDetailView(BaseView):
    """
    Player detail view with navigation between players
    
    Fixed: Now properly stores and uses data_manager parameter
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', all_players: List[Dict[str, Any]], current_index: int):
        """
        Initialize player detail view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance (FIXED: now properly stored)
            all_players: List of all player dictionaries
            current_index: Index of currently displayed player
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager  # FIXED: Store data_manager
        self.all_players = all_players
        self.current_index = max(0, min(current_index, len(all_players) - 1))
        self._update_buttons()
    
    def _update_buttons(self) -> None:
        """Update navigation buttons based on current position"""
        try:
            self.clear_items()
            
            # Previous player button
            if self.current_index > 0:
                prev_btn = Button(
                    label="◀️ Previous Player",
                    style=discord.ButtonStyle.primary,
                    custom_id="prev_player"
                )
                prev_btn.callback = self._prev_player
                self.add_item(prev_btn)
            
            # Next player button
            if self.current_index < len(self.all_players) - 1:
                next_btn = Button(
                    label="Next Player ▶️",
                    style=discord.ButtonStyle.primary,
                    custom_id="next_player"
                )
                next_btn.callback = self._next_player
                self.add_item(next_btn)
            
            # Back to list button
            back_btn = Button(
                label="↩️ Player List",
                style=discord.ButtonStyle.danger,
                custom_id="back_to_list"
            )
            back_btn.callback = self._back_to_list
            self.add_item(back_btn)
            
        except Exception as e:
            logger.error(f"Error updating player detail buttons: {e}")
    
    async def _prev_player(self, interaction: discord.Interaction) -> None:
        """Show previous player"""
        try:
            if self.current_index > 0:
                self.current_index -= 1
                self._update_buttons()
                await interaction.response.edit_message(
                    embed=self.create_embed(),
                    view=self
                )
            else:
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error navigating to previous player: {e}")
            await interaction.response.send_message(
                "❌ Failed to navigate to previous player.",
                ephemeral=True
            )
    
    async def _next_player(self, interaction: discord.Interaction) -> None:
        """Show next player"""
        try:
            if self.current_index < len(self.all_players) - 1:
                self.current_index += 1
                self._update_buttons()
                await interaction.response.edit_message(
                    embed=self.create_embed(),
                    view=self
                )
            else:
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error navigating to next player: {e}")
            await interaction.response.send_message(
                "❌ Failed to navigate to next player.",
                ephemeral=True
            )
    
    async def _back_to_list(self, interaction: discord.Interaction) -> None:
        """
        Return to player list
        
        FIXED: Now properly passes data_manager parameter as mentioned in review
        """
        try:
            self.stop()
            
            # FIXED: Pass data_manager parameter that was missing in original code
            view = PlayerListView(
                self.user, 
                self.config, 
                self.data_manager,  # FIXED: This was missing in the original code
                self.all_players
            )
            
            # Set the page to show the current player
            view.current_page = self.current_index // view.per_page
            view.update_buttons()
            
            await interaction.response.edit_message(
                embed=await view.create_embed(),
                view=view
            )
            view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error returning to player list: {e}")
            await interaction.response.send_message(
                "❌ Failed to return to player list. Please try again.",
                ephemeral=True
            )
    
    def create_embed(self) -> discord.Embed:
        """Create player detail embed"""
        try:
            if not self.all_players or self.current_index >= len(self.all_players):
                return discord.Embed(
                    title="❌ Error",
                    description="Player not found.",
                    color=discord.Color.red()
                )
            
            player = self.all_players[self.current_index]
            
            # Create title with name and region
            name = player.get('name', 'Unknown Player')
            region_emoji = player.get('region_emoji', '')
            title = f"{name} {region_emoji}".strip()
            
            # Create description from description lines
            description_lines = player.get('description_lines', [])
            if description_lines:
                description = "\n".join(description_lines)
            else:
                description = "_No description available._"
            
            # Create embed
            embed = discord.Embed(
                title=title,
                description=description,
                color=self.config.embed_color,
                url=player.get('social_link')
            )
            
            # Add character image if available
            image_url = player.get('image_url')
            if image_url:
                embed.set_image(url=image_url)
            
            # Add footer with player position and custom footer
            color_footer = player.get('color_footer', '')
            position_info = f"Player {self.current_index + 1} of {len(self.all_players)}"
            
            if color_footer:
                footer_text = f"{color_footer} • {position_info}"
            else:
                footer_text = position_info
            
            embed.set_footer(text=footer_text)
            
            # Add social link field if available
            social_link = player.get('social_link')
            if social_link:
                # Extract platform name from URL for display
                platform = "Social Media"
                if "twitter.com" in social_link or "x.com" in social_link:
                    platform = "Twitter/X"
                elif "youtube.com" in social_link:
                    platform = "YouTube"
                elif "twitch.tv" in social_link:
                    platform = "Twitch"
                elif "instagram.com" in social_link:
                    platform = "Instagram"
                
                embed.add_field(
                    name=f"🔗 {platform}",
                    value=f"[Visit Profile]({social_link})",
                    inline=False
                )
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating player detail embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load player details.",
                color=discord.Color.red()
            )


class PlayerManagementView(BaseView):
    """
    Admin view for managing notable players
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize player management view
        
        Args:
            user: Discord user (must be admin)
            config: Bot configuration
            data_manager: DataManager instance
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self._add_buttons()
    
    def _add_buttons(self) -> None:
        """Add management buttons"""
        # Add player button
        add_btn = Button(
            label="➕ Add Player",
            style=discord.ButtonStyle.success,
            custom_id="add_player"
        )
        add_btn.callback = self._add_player
        self.add_item(add_btn)
        
        # View players button
        if self.config.notable_players:
            view_btn = Button(
                label="👥 View Players",
                style=discord.ButtonStyle.primary,
                custom_id="view_players"
            )
            view_btn.callback = self._view_players
            self.add_item(view_btn)
        
        # Back button
        back_btn = Button(
            label="↩️ Back",
            style=discord.ButtonStyle.danger,
            custom_id="back"
        )
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    async def _add_player(self, interaction: discord.Interaction) -> None:
        """Show add player modal"""
        try:
            from views.modals import PlayerModal
            
            modal = PlayerModal(self.data_manager)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error showing add player modal: {e}")
            await interaction.response.send_message(
                "❌ Failed to open add player form.",
                ephemeral=True
            )
    
    async def _view_players(self, interaction: discord.Interaction) -> None:
        """Show player list"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error showing player list: {e}")
            await interaction.response.send_message(
                "❌ Failed to display player list.",
                ephemeral=True
            )
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Go back to previous menu"""
        self.stop()
        await interaction.response.edit_message(
            content="↩️ *Returned to previous menu.*",
            view=None,
            embed=None
        )
    
    def create_embed(self) -> discord.Embed:
        """Create management embed"""
        embed = discord.Embed(
            title="👥 Player Management",
            description="Manage notable players for the bot.",
            color=self.config.embed_color
        )
        
        embed.add_field(
            name="Current Players",
            value=f"{len(self.config.notable_players)} players configured",
            inline=False
        )
        
        embed.set_thumbnail(url=self.config.thumbnail_url)
        return embed
