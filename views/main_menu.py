"""
Main menu view for category selection
Central hub for navigating to different bot features
"""

import logging
from urllib.parse import quote_plus
from typing import TYPE_CHECKING

import discord
from discord.ui import Button

from views.base import BaseView

if TYPE_CHECKING:
    from data import DataManager
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class MainMenuView(BaseView):
    """
    Main category selection menu with improved error handling
    
    Features:
    - Dynamic button creation based on configuration
    - Category validation before navigation
    - Resource and info section buttons
    - Proper error handling and user feedback
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize main menu view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self._add_buttons()
    
    def _add_buttons(self) -> None:
        """Add all menu buttons based on configuration"""
        try:
            # Add combo category buttons
            self._add_category_buttons()
            
            # Add resource buttons
            self._add_resource_buttons()
            
            # Add info section buttons
            self._add_info_buttons()
            
            # Add utility buttons
            self._add_utility_buttons()
            
        except Exception as e:
            logger.error(f"Error adding main menu buttons: {e}")
    
    def _add_category_buttons(self) -> None:
        """Add buttons for combo categories"""
        if not self.config.combo_categories:
            return
        
        # Button styles cycle for visual variety
        styles = [
            discord.ButtonStyle.primary,
            discord.ButtonStyle.success,
            discord.ButtonStyle.secondary
        ]
        
        for i, category in enumerate(self.config.combo_categories):
            try:
                # Validate category name for custom_id
                safe_category = quote_plus(category)[:90]  # Keep within Discord limits
                
                btn = Button(
                    label=category[:80],  # Discord button label limit
                    style=styles[i % len(styles)],
                    custom_id=f"cat_{safe_category}"
                )
                btn.callback = self._make_category_callback(category)
                self.add_item(btn)
                
            except Exception as e:
                logger.error(f"Error adding category button for '{category}': {e}")
    
    def _add_resource_buttons(self) -> None:
        """Add resources and notable players buttons"""
        # General resources button
        resources_btn = Button(
            label="📚 Resources",
            style=discord.ButtonStyle.secondary,
            custom_id="resources"
        )
        resources_btn.callback = self._show_resources
        self.add_item(resources_btn)
        
        # Notable players button (if any exist)
        if self.config.notable_players:
            players_btn = Button(
                label="✨ Notable Players",
                style=discord.ButtonStyle.secondary,
                custom_id="notable_players"
            )
            players_btn.callback = self._show_notable_players
            self.add_item(players_btn)
    
    def _add_info_buttons(self) -> None:
        """Add info section buttons if configured"""
        # Ender info button
        if self.config.info_section_ender_title:
            ender_btn = Button(
                label=self.config.info_section_ender_title[:80],
                style=discord.ButtonStyle.secondary,
                custom_id="ender_info"
            )
            ender_btn.callback = self._show_ender_info
            self.add_item(ender_btn)
        
        # Routes button
        if self.config.info_section_routes_title:
            routes_btn = Button(
                label=self.config.info_section_routes_title[:80],
                style=discord.ButtonStyle.secondary,
                custom_id="routes_info"
            )
            routes_btn.callback = self._show_routes
            self.add_item(routes_btn)
    
    def _add_utility_buttons(self) -> None:
        """Add utility buttons like close"""
        close_btn = Button(
            label="✖️ Close",
            style=discord.ButtonStyle.grey,
            custom_id="close"
        )
        close_btn.callback = self._close
        self.add_item(close_btn)
    
    def _make_category_callback(self, category: str):
        """Create callback for category button with validation"""
        async def callback(interaction: discord.Interaction):
            try:
                # Validate category exists
                if category not in self.config.combo_categories:
                    await interaction.response.send_message(
                        f"❌ Category '{category}' no longer exists.",
                        ephemeral=True
                    )
                    return
                
                # Get starters for category
                starters = self.config.starters.get(category, [])
                if not starters:
                    await interaction.response.send_message(
                        f"⚠️ No starters configured for **{category}**.\n"
                        f"Ask an admin to add starters using `/admin add_starter`.",
                        ephemeral=True
                    )
                    return
                
                # Import here to avoid circular imports
                from views.starter_list import StarterListView
                
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
                
            except Exception as e:
                logger.error(f"Error in category callback for '{category}': {e}")
                await interaction.response.send_message(
                    f"❌ Failed to load {category} starters. Please try again.",
                    ephemeral=True
                )
        
        return callback
    
    async def _show_resources(self, interaction: discord.Interaction) -> None:
        """Show resources menu"""
        try:
            from views.resource import ResourceMenuView
            
            view = ResourceMenuView(self.user, self.config, self.data_manager)
            
            self.stop()
            await interaction.response.edit_message(
                embed=view.create_embed(),
                view=view
            )
            view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error showing resources menu: {e}")
            await interaction.response.send_message(
                "❌ Failed to load resources menu. Please try again.",
                ephemeral=True
            )
    
    async def _show_notable_players(self, interaction: discord.Interaction) -> None:
        """Show notable players directly"""
        try:
            from views.player import PlayerListView
            
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
            logger.error(f"Error showing notable players: {e}")
            await interaction.response.send_message(
                "❌ Failed to load notable players. Please try again.",
                ephemeral=True
            )
    
    async def _show_ender_info(self, interaction: discord.Interaction) -> None:
        """Show ender info section"""
        try:
            embed = discord.Embed(
                title=self.config.info_section_ender_title,
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add ender info content
            if self.config.ender_info:
                description = "\n".join(self.config.ender_info)
                # Ensure description fits within Discord limits
                if len(description) > 4000:
                    description = description[:3997] + "..."
                embed.description = description
            else:
                embed.description = "_No ender information configured yet._"
            
            # Add credit footer if available
            if self.config.ender_info_credit:
                embed.set_footer(text=self.config.ender_info_credit)
            
            # Create simple back view
            back_view = self._create_back_view()
            
            self.stop()
            await interaction.response.edit_message(embed=embed, view=back_view)
            back_view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error showing ender info: {e}")
            await interaction.response.send_message(
                "❌ Failed to load ender information. Please try again.",
                ephemeral=True
            )
    
    async def _show_routes(self, interaction: discord.Interaction) -> None:
        """Show interesting routes section"""
        try:
            embed = discord.Embed(
                title=self.config.info_section_routes_title,
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add routes content
            if self.config.interesting_routes:
                # Format as bullet points
                routes_text = "\n".join(f"• {route}" for route in self.config.interesting_routes)
                # Ensure description fits within Discord limits
                if len(routes_text) > 4000:
                    routes_text = routes_text[:3997] + "..."
                embed.description = routes_text
            else:
                embed.description = "_No interesting routes configured yet._"
            
            # Create simple back view
            back_view = self._create_back_view()
            
            self.stop()
            await interaction.response.edit_message(embed=embed, view=back_view)
            back_view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error showing routes info: {e}")
            await interaction.response.send_message(
                "❌ Failed to load routes information. Please try again.",
                ephemeral=True
            )
    
    def _create_back_view(self) -> 'InfoBackView':
        """Create a simple back view for info sections"""
        return InfoBackView(self.user, self.config, self.data_manager)
    
    async def _close(self, interaction: discord.Interaction) -> None:
        """Close the main menu"""
        try:
            self.stop()
            await interaction.response.edit_message(
                content="✖️ *Menu closed. Use `/combos` to reopen.*",
                view=None,
                embed=None
            )
            
        except Exception as e:
            logger.error(f"Error closing main menu: {e}")
            # Try to edit without content if the above fails
            try:
                await interaction.response.edit_message(view=None, embed=None)
            except:
                pass
    
    def create_embed(self) -> discord.Embed:
        """Create main menu embed"""
        try:
            embed = discord.Embed(
                title=f"🎮 {self.config.character_name} Combos",
                description="Select a category to explore:",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add helpful information
            if self.config.combo_categories:
                categories_text = ", ".join(self.config.combo_categories)
                embed.add_field(
                    name="📂 Available Categories",
                    value=categories_text,
                    inline=False
                )
            
            # Add stats
            total_starters = sum(len(starters) for starters in self.config.starters.values())
            stats_text = f"• {len(self.config.combo_categories)} categories\n"
            stats_text += f"• {total_starters} total starters\n"
            stats_text += f"• {len(self.config.notable_players)} notable players"
            
            embed.add_field(
                name="📊 Bot Stats",
                value=stats_text,
                inline=True
            )
            
            embed.set_footer(text="Use the buttons below to navigate")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating main menu embed: {e}")
            # Return a basic embed if there's an error
            return discord.Embed(
                title="🎮 Combo Bot",
                description="Welcome! Use the buttons below to navigate.",
                color=discord.Color.blue()
            )


class InfoBackView(BaseView):
    """Simple view with just a back button for info sections"""
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize info back view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        
        # Add back button
        back_btn = Button(
            label="↩️ Back to Main Menu",
            style=discord.ButtonStyle.danger,
            custom_id="back_main"
        )
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to main menu"""
        try:
            self.stop()
            main_view = MainMenuView(self.user, self.config, self.data_manager)
            await interaction.response.edit_message(
                embed=main_view.create_embed(),
                view=main_view
            )
            main_view.message = interaction.message
            
        except Exception as e:
            logger.error(f"Error returning to main menu: {e}")
            await interaction.response.send_message(
                "❌ Failed to return to main menu. Please use `/combos` to restart.",
                ephemeral=True
            )
