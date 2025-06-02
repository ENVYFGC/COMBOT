"""
Starter list view for selecting combo starters within a category
"""

import logging
from typing import List, TYPE_CHECKING

import discord
from discord.ui import Button

from views.base import PaginatedView

if TYPE_CHECKING:
    from data import DataManager
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class StarterListView(PaginatedView):
    """
    View for selecting starters within a combo category
    
    Features:
    - Paginated starter display
    - Combo count display for each starter
    - Direct combo viewing
    - Category validation
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', category: str, starters: List[str]):
        """
        Initialize starter list view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
            category: Combo category name
            starters: List of starter names for this category
        """
        super().__init__(user, starters, config.page_sizes.starters, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.category = category
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add starter selection buttons for current page"""
        try:
            for i, starter in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Create button label with starter name and index
                button_label = f"{global_index + 1}. {starter}"
                if len(button_label) > 80:  # Discord button label limit
                    # Truncate starter name to fit
                    max_starter_len = 80 - len(f"{global_index + 1}. ") - 3  # 3 for "..."
                    button_label = f"{global_index + 1}. {starter[:max_starter_len]}..."
                
                btn = Button(
                    label=button_label,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"starter_{global_index}"
                )
                btn.callback = self._make_starter_callback(starter)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding starter buttons: {e}")
    
    def _make_starter_callback(self, starter: str):
        """Create callback for starter selection button with validation"""
        async def callback(interaction: discord.Interaction):
            try:
                # Validate starter still exists
                if starter not in self.config.starters.get(self.category, []):
                    await interaction.response.send_message(
                        f"❌ Starter '{starter}' is no longer available.",
                        ephemeral=True
                    )
                    return
                
                # Get combos for this starter
                combos = await self.data_manager.get_combos(self.category, starter)
                
                if not combos:
                    await interaction.response.send_message(
                        f"⚠️ No combos found for **{starter}** in {self.category}.\n"
                        f"Ask an admin to add combos using `/update {self.category} <playlist_url> {starter}`.",
                        ephemeral=True
                    )
                    return
                
                # Import here to avoid circular imports
                from views.combo_list import ComboListView
                
                view = ComboListView(
                    self.user,
                    self.config,
                    self.category,
                    starter,
                    combos
                )
                
                # Send combo list as ephemeral message (as in original)
                await interaction.response.send_message(
                    embed=await view.create_embed(),
                    view=view,
                    ephemeral=True
                )
                view.message = await interaction.original_response()
                
            except Exception as e:
                logger.error(f"Error in starter callback for '{starter}': {e}")
                await interaction.response.send_message(
                    f"❌ Failed to load combos for **{starter}**. Please try again.",
                    ephemeral=True
                )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to main menu"""
        try:
            from views.main_menu import MainMenuView
            
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
                "❌ Failed to return to main menu. Please try again.",
                ephemeral=True
            )
    
    async def create_embed(self) -> discord.Embed:
        """Create starter list embed with combo counts"""
        try:
            embed = discord.Embed(
                title=f"🔹 {self.category} Starters (Page {self.current_page + 1}/{self.max_pages})",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            if not self.items:
                embed.description = f"_No starters configured for {self.category} yet._"
            else:
                descriptions = []
                
                # Get combo counts for current page starters
                for i, starter in enumerate(self.current_items):
                    global_index = self.current_page * self.per_page + i
                    
                    try:
                        # Get combo count asynchronously
                        combo_count = await self.data_manager.get_combo_count(self.category, starter)
                        
                        if combo_count > 0:
                            note = f"{combo_count} combo{'s' if combo_count != 1 else ''}"
                        else:
                            note = "No combos yet"
                        
                        descriptions.append(f"**{global_index + 1}. {starter}** - _{note}_")
                        
                    except Exception as e:
                        logger.warning(f"Error getting combo count for {starter}: {e}")
                        descriptions.append(f"**{global_index + 1}. {starter}** - _Unknown_")
                
                embed.description = "\n".join(descriptions)
            
            # Add helpful footer
            embed.set_footer(text="Select a starter to view its combos")
            
            # Add category info field if there are starters
            if self.items:
                total_combos = 0
                try:
                    for starter in self.config.starters.get(self.category, []):
                        total_combos += await self.data_manager.get_combo_count(self.category, starter)
                except Exception as e:
                    logger.warning(f"Error calculating total combos: {e}")
                
                info_text = f"**Category:** {self.category}\n"
                info_text += f"**Total Starters:** {len(self.items)}\n"
                if total_combos > 0:
                    info_text += f"**Total Combos:** {total_combos}"
                
                embed.add_field(
                    name="📊 Category Info",
                    value=info_text,
                    inline=True
                )
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating starter list embed: {e}")
            # Return a basic error embed
            return discord.Embed(
                title=f"❌ Error Loading {self.category}",
                description="Failed to load starter list. Please try again.",
                color=discord.Color.red()
            )


class StarterManagementView(PaginatedView):
    """
    Admin view for managing starters within a category
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', category: str):
        """
        Initialize starter management view
        
        Args:
            user: Discord user (must be admin)
            config: Bot configuration
            data_manager: DataManager instance
            category: Category to manage
        """
        starters = config.starters.get(category, [])
        super().__init__(user, starters, 10, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.category = category
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add starter management buttons"""
        try:
            for i, starter in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Remove button for each starter
                btn = Button(
                    label=f"🗑️ {global_index + 1}. {starter[:50]}",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"remove_{global_index}"
                )
                btn.callback = self._make_remove_callback(starter)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding management buttons: {e}")
    
    def _make_remove_callback(self, starter: str):
        """Create callback for starter removal"""
        async def callback(interaction: discord.Interaction):
            try:
                # Confirm removal
                from .base import ConfirmationView
                
                confirm_view = ConfirmationView(
                    self.user,
                    timeout=30.0,
                    confirm_label="🗑️ Yes, Remove",
                    cancel_label="❌ Cancel"
                )
                
                async def on_confirm_remove(confirm_interaction):
                    try:
                        removed_config, removed_data = await self.data_manager.remove_starter(
                            self.category, starter
                        )
                        
                        if removed_config or removed_data:
                            await self.data_manager.save(force=True)
                            
                            result_msg = f"✅ Removed starter **{starter}**"
                            if removed_data:
                                result_msg += " and its combo data"
                            result_msg += "."
                        else:
                            result_msg = f"⚠️ Starter **{starter}** was not found."
                        
                        await confirm_interaction.response.edit_message(
                            content=result_msg,
                            view=None,
                            embed=None
                        )
                        
                        # Refresh the management view
                        self.items = self.config.starters.get(self.category, [])
                        if self.current_page >= self.max_pages:
                            self.current_page = max(0, self.max_pages - 1)
                        self.update_buttons()
                        
                    except Exception as e:
                        logger.error(f"Error removing starter: {e}")
                        await confirm_interaction.response.edit_message(
                            content="❌ Failed to remove starter. Please try again.",
                            view=None,
                            embed=None
                        )
                
                confirm_view.on_confirm = on_confirm_remove
                
                await interaction.response.send_message(
                    f"⚠️ **Are you sure you want to remove starter '{starter}'?**\n"
                    f"This will also delete all combo data for this starter.",
                    view=confirm_view,
                    ephemeral=True
                )
                
            except Exception as e:
                logger.error(f"Error in remove starter callback: {e}")
                await interaction.response.send_message(
                    "❌ Failed to initiate starter removal.",
                    ephemeral=True
                )
        
        return callback
    
    async def create_embed(self) -> discord.Embed:
        """Create management embed"""
        try:
            embed = discord.Embed(
                title=f"⚙️ Manage {self.category} Starters",
                description=f"Click a button to remove a starter from **{self.category}**.",
                color=self.config.embed_color
            )
            
            if not self.items:
                embed.description = f"_No starters in {self.category} to manage._"
            else:
                embed.add_field(
                    name="⚠️ Warning",
                    value="Removing a starter will also delete all its combo data!",
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating management embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load management interface.",
                color=discord.Color.red()
            )
