"""
Combo list view for displaying combos within a starter
"""

import logging
from typing import List, TYPE_CHECKING

import discord
from discord.ui import Button

from views.base import PaginatedView, BaseView
from utils import truncate_text, format_combo_notation

if TYPE_CHECKING:
    from data import DataManager, ComboEntry
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class ComboListView(PaginatedView):
    """
    View for displaying combos for a specific starter
    
    Features:
    - Paginated combo display with formatted notation
    - Individual combo detail viewing
    - Video link access
    - Proper text truncation for Discord limits
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 category: str, starter: str, combos: List['ComboEntry']):
        """
        Initialize combo list view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            category: Combo category name
            starter: Starter name
            combos: List of ComboEntry objects
        """
        super().__init__(user, combos, config.page_sizes.combos, config.view_timeout_seconds)
        self.config = config
        self.category = category
        self.starter = starter
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add combo number buttons for current page"""
        try:
            for i, combo in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                btn = Button(
                    label=str(global_index + 1),
                    style=discord.ButtonStyle.primary,
                    custom_id=f"combo_{global_index}"
                )
                btn.callback = self._make_combo_callback(global_index, combo)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding combo buttons: {e}")
    
    def _make_combo_callback(self, index: int, combo: 'ComboEntry'):
        """Create callback for combo detail button"""
        async def callback(interaction: discord.Interaction):
            try:
                # Create detailed combo message
                content = f"**Combo #{index + 1} for {self.starter}**\n\n"
                
                # Add notation with formatting
                formatted_notation = format_combo_notation(combo.notation)
                # Truncate if too long for code block
                if len(formatted_notation) > 800:
                    formatted_notation = truncate_text(formatted_notation, 800)
                
                content += f"**Notation:**\n```{formatted_notation}```\n"
                
                # Add notes if available and meaningful
                if combo.notes and combo.notes.strip() and combo.notes != "No Notes Provided":
                    notes_text = truncate_text(combo.notes, 800)
                    content += f"**Notes:**\n{notes_text}\n"
                
                # Add video link
                content += f"\n🎥 **Video:** {combo.link}"
                
                # Ensure total content length is within Discord limits
                if len(content) > 2000:
                    content = truncate_text(content, 1997)  # Leave room for "..."
                
                await interaction.response.send_message(
                    content=content,
                    ephemeral=True,
                    suppress_embeds=False  # Allow video embeds
                )
                
            except Exception as e:
                logger.error(f"Error showing combo details: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to load details for combo #{index + 1}. Please try again.",
                    ephemeral=True
                )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Close combo list (as it's ephemeral)"""
        try:
            self.stop()
            await interaction.response.edit_message(
                content="↩️ *Combo list closed.*",
                view=None,
                embed=None
            )
            
        except Exception as e:
            logger.error(f"Error closing combo list: {e}")
            # Try to just remove the view if edit fails
            try:
                await interaction.response.edit_message(view=None)
            except:
                pass
    
    async def create_embed(self) -> discord.Embed:
        """Create combo list embed with formatted notation previews"""
        try:
            title = f"📜 {self.starter} Combos (Page {self.current_page + 1}/{self.max_pages})"
            embed = discord.Embed(
                title=title,
                description="Select a number for full details and video link.",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add combo fields for current page
            for i, combo in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Format and truncate notation for field name
                formatted_notation = format_combo_notation(combo.notation)
                field_name = f"{global_index + 1}. {truncate_text(formatted_notation, 200)}"
                
                # Create field value with notes
                field_value = "_No specific notes._"
                if combo.notes and combo.notes.strip() and combo.notes != "No Notes Provided":
                    notes_preview = truncate_text(combo.notes, 150)
                    field_value = f"**Note:** {notes_preview}"
                
                # Ensure field value isn't too long
                if len(field_value) > 1000:
                    field_value = truncate_text(field_value, 997)
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
            
            # Add footer with combo range info
            start = self.current_page * self.per_page + 1
            end = min((self.current_page + 1) * self.per_page, len(self.items))
            embed.set_footer(text=f"Showing combos {start}-{end} of {len(self.items)} • Category: {self.category}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating combo list embed: {e}")
            # Return a basic error embed
            return discord.Embed(
                title=f"❌ Error Loading {self.starter} Combos",
                description="Failed to load combo list. Please try again.",
                color=discord.Color.red()
            )


class ComboManagementView(PaginatedView):
    """
    Admin view for managing combos for a specific starter
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', category: str, starter: str):
        """
        Initialize combo management view
        
        Args:
            user: Discord user (must be admin)
            config: Bot configuration
            data_manager: DataManager instance
            category: Combo category
            starter: Starter name
        """
        self.category = category
        self.starter = starter
        self.data_manager = data_manager
        
        # Load combos (simplified to avoid async issues in __init__)
        combos = []  # Will be populated when needed
        
        super().__init__(user, combos, 5, config.view_timeout_seconds)
        self.config = config
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add combo management buttons"""
        try:
            for i, combo in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Truncate notation for button display
                notation_preview = truncate_text(format_combo_notation(combo.notation), 40)
                
                btn = Button(
                    label=f"📝 {global_index + 1}. {notation_preview}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"edit_combo_{global_index}"
                )
                btn.callback = self._make_edit_callback(global_index, combo)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding combo management buttons: {e}")
    
    def _make_edit_callback(self, index: int, combo: 'ComboEntry'):
        """Create callback for combo editing"""
        async def callback(interaction: discord.Interaction):
            try:
                # For now, just show combo details
                # In the future, this could open an edit modal
                content = f"**Combo #{index + 1} Management**\n\n"
                content += f"**Notation:** {combo.notation}\n"
                content += f"**Notes:** {combo.notes}\n"
                content += f"**Link:** {combo.link}\n\n"
                content += "_Combo editing via modal will be implemented in a future update._"
                
                await interaction.response.send_message(
                    content=truncate_text(content, 2000),
                    ephemeral=True
                )
                
            except Exception as e:
                logger.error(f"Error in combo edit callback: {e}")
                await interaction.response.send_message(
                    "❌ Failed to load combo for editing.",
                    ephemeral=True
                )
        
        return callback
    
    async def create_embed(self) -> discord.Embed:
        """Create combo management embed"""
        try:
            embed = discord.Embed(
                title=f"⚙️ Manage {self.starter} Combos",
                description=f"Managing combos for **{self.starter}** in {self.category}.",
                color=self.config.embed_color
            )
            
            if not self.items:
                embed.description = f"_No combos found for {self.starter}._"
            else:
                embed.add_field(
                    name="📊 Combo Stats",
                    value=f"**Total Combos:** {len(self.items)}\n"
                          f"**Current Page:** {self.current_page + 1}/{self.max_pages}",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ Instructions",
                    value="Click a combo button to view details.\n"
                          "Use `/update` command to refresh combos from YouTube.",
                    inline=False
                )
            
            embed.set_footer(text=f"Category: {self.category} • Starter: {self.starter}")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating combo management embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load combo management interface.",
                color=discord.Color.red()
            )


class ComboSearchView(BaseView):
    """
    View for searching combos across all categories and starters
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', search_term: str):
        """
        Initialize combo search view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
            search_term: Term to search for in combo notations and notes
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.search_term = search_term.lower()
        self.results = []
        
        # Add close button
        close_btn = Button(
            label="✖️ Close",
            style=discord.ButtonStyle.danger
        )
        close_btn.callback = self._close
        self.add_item(close_btn)
    
    async def search_combos(self) -> None:
        """Search for combos matching the search term"""
        try:
            self.results = []
            
            for category in self.config.combo_categories:
                starters = self.config.starters.get(category, [])
                
                for starter in starters:
                    combos = await self.data_manager.get_combos(category, starter)
                    
                    for i, combo in enumerate(combos):
                        # Search in notation and notes
                        if (self.search_term in combo.notation.lower() or 
                            self.search_term in combo.notes.lower()):
                            
                            self.results.append({
                                'category': category,
                                'starter': starter,
                                'combo_index': i + 1,
                                'combo': combo
                            })
            
        except Exception as e:
            logger.error(f"Error searching combos: {e}")
    
    async def _close(self, interaction: discord.Interaction) -> None:
        """Close search results"""
        self.stop()
        await interaction.response.edit_message(
            content="🔍 *Search closed.*",
            view=None,
            embed=None
        )
    
    async def create_embed(self) -> discord.Embed:
        """Create search results embed"""
        try:
            embed = discord.Embed(
                title=f"🔍 Combo Search Results",
                color=self.config.embed_color
            )
            
            if not self.results:
                embed.description = f"No combos found matching **{self.search_term}**."
            else:
                embed.description = f"Found **{len(self.results)}** combos matching **{self.search_term}**:"
                
                # Show first 10 results
                for i, result in enumerate(self.results[:10]):
                    combo = result['combo']
                    notation = truncate_text(format_combo_notation(combo.notation), 100)
                    
                    field_name = f"{i + 1}. {result['category']} → {result['starter']}"
                    field_value = f"**Combo #{result['combo_index']}:** {notation}"
                    
                    if combo.notes and combo.notes != "No Notes Provided":
                        notes = truncate_text(combo.notes, 100)
                        field_value += f"\n*{notes}*"
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=False
                    )
                
                if len(self.results) > 10:
                    embed.set_footer(text=f"Showing first 10 of {len(self.results)} results")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating search embed: {e}")
            return discord.Embed(
                title="❌ Search Error",
                description="Failed to display search results.",
                color=discord.Color.red()
            )
