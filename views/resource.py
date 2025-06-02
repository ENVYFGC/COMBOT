"""
Resource menu and list views for managing general resources
"""

import logging
from typing import List, TYPE_CHECKING

import discord
from discord.ui import Button

from views.base import BaseView, PaginatedView

if TYPE_CHECKING:
    from data import DataManager, ResourceEntry
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class ResourceMenuView(BaseView):
    """
    Resource category menu for accessing different types of resources
    
    Features:
    - General resources access
    - Notable players access (if configured)
    - Navigation back to main menu
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize resource menu view
        
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
        """Add resource category buttons"""
        try:
            # General resources button
            general_btn = Button(
                label="🔗 General Resources",
                style=discord.ButtonStyle.primary,
                custom_id="general_resources"
            )
            general_btn.callback = self._show_general_resources
            self.add_item(general_btn)
            
            # Notable players button (if any exist)
            if self.config.notable_players:
                players_btn = Button(
                    label="✨ Notable Players",
                    style=discord.ButtonStyle.primary,
                    custom_id="notable_players"
                )
                players_btn.callback = self._show_notable_players
                self.add_item(players_btn)
            
            # Back to main menu button
            back_btn = Button(
                label="↩️ Main Menu",
                style=discord.ButtonStyle.danger,
                custom_id="back_main"
            )
            back_btn.callback = self._go_back
            self.add_item(back_btn)
            
        except Exception as e:
            logger.error(f"Error adding resource menu buttons: {e}")
    
    async def _show_general_resources(self, interaction: discord.Interaction) -> None:
        """Show general resources list"""
        try:
            # Get resources from data manager
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
            
        except Exception as e:
            logger.error(f"Error showing general resources: {e}")
            await interaction.response.send_message(
                "❌ Failed to load general resources. Please try again.",
                ephemeral=True
            )
    
    async def _show_notable_players(self, interaction: discord.Interaction) -> None:
        """Show notable players list"""
        try:
            from .player import PlayerListView
            
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
    
    def create_embed(self) -> discord.Embed:
        """Create resource menu embed"""
        try:
            embed = discord.Embed(
                title="📚 Resources",
                description="Select a resource category to explore:",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add resource statistics
            stats_text = ""
            
            # Count general resources (remove async call from sync method)
            try:
                # We'll just show that resources are available without counting
                # The actual count will be shown when the resources are loaded
                stats_text += "• General resources available\n"
            except Exception as e:
                logger.warning(f"Error checking resources: {e}")
                stats_text += "• General resources available\n"
            
            # Count notable players
            if self.config.notable_players:
                stats_text += f"• {len(self.config.notable_players)} notable players\n"
            
            if stats_text:
                embed.add_field(
                    name="📊 Available Resources",
                    value=stats_text.strip(),
                    inline=False
                )
            
            embed.set_footer(text="Use the buttons below to browse resources")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating resource menu embed: {e}")
            return discord.Embed(
                title="📚 Resources",
                description="Welcome to the resources section!",
                color=self.config.embed_color
            )


class ResourceListView(PaginatedView):
    """
    View for displaying general resources with pagination
    
    Features:
    - Paginated resource display
    - Individual resource detail viewing
    - Resource type categorization
    - Link access
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration',
                 data_manager: 'DataManager', resources: List['ResourceEntry'], note: str):
        """
        Initialize resource list view
        
        Args:
            user: Discord user who can interact with this view
            config: Bot configuration
            data_manager: DataManager instance
            resources: List of ResourceEntry objects
            note: General note about resources
        """
        super().__init__(user, resources, config.page_sizes.resources, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.note = note
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add resource selection buttons for current page"""
        try:
            for i, resource in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Create button label with resource name and type
                label = f"{global_index + 1}. {resource.name}"
                if len(label) > 70:  # Leave room for type indicator
                    label = f"{global_index + 1}. {resource.name[:60]}..."
                
                # Add type indicator
                type_indicator = f" ({resource.type})" if resource.type else ""
                if len(label + type_indicator) <= 80:
                    label += type_indicator
                
                btn = Button(
                    label=label,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"resource_{global_index}"
                )
                btn.callback = self._make_resource_callback(resource)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding resource buttons: {e}")
    
    def _make_resource_callback(self, resource: 'ResourceEntry'):
        """Create callback for resource detail button"""
        async def callback(interaction: discord.Interaction):
            try:
                # Create detailed resource message
                content = f"**Resource: {resource.name}**\n\n"
                content += f"**Type:** `{resource.type}`\n"
                
                if resource.credit:
                    content += f"**Credit:** {resource.credit}\n"
                
                content += f"\n🔗 **Link:** {resource.link}"
                
                # Add helpful description based on resource type
                type_descriptions = {
                    'video': '🎥 Video content',
                    'document': '📄 Text document',
                    'spreadsheet': '📊 Data spreadsheet',
                    'guide': '📖 Tutorial or guide',
                    'tool': '🔧 Utility or tool',
                    'website': '🌐 Website or web app'
                }
                
                type_desc = type_descriptions.get(resource.type.lower())
                if type_desc:
                    content += f"\n\n{type_desc}"
                
                await interaction.response.send_message(
                    content=content,
                    ephemeral=True,
                    suppress_embeds=False  # Allow link previews
                )
                
            except Exception as e:
                logger.error(f"Error showing resource details: {e}")
                await interaction.response.send_message(
                    f"❌ Failed to load resource details. Please try again.",
                    ephemeral=True
                )
        
        return callback
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Return to resource menu"""
        try:
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
                "❌ Failed to return to resource menu. Please try again.",
                ephemeral=True
            )
    
    async def create_embed(self) -> discord.Embed:
        """Create resource list embed"""
        try:
            embed = discord.Embed(
                title=f"🔗 General Resources (Page {self.current_page + 1}/{self.max_pages})",
                color=self.config.embed_color
            )
            embed.set_thumbnail(url=self.config.thumbnail_url)
            
            # Add general note if available
            description = ""
            if self.note:
                description = f"{self.note}\n\n"
            
            if not self.resources:
                description += "_No resources configured yet._"
            else:
                # List resources on current page
                for i, resource in enumerate(self.current_items):
                    global_index = self.current_page * self.per_page + i
                    description += f"**{global_index + 1}. {resource.name}** ({resource.type})\n"
                
                description += "\n**Select a resource for details and link.**"
            
            embed.description = description
            
            # Add resource type summary if there are resources
            if self.items:
                type_counts = {}
                for resource in self.items:
                    resource_type = resource.type.lower()
                    type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
                
                if type_counts:
                    type_summary = ", ".join([f"{count} {rtype}" for rtype, count in type_counts.items()])
                    embed.add_field(
                        name="📊 Resource Types",
                        value=type_summary,
                        inline=False
                    )
            
            embed.set_footer(text=self.get_page_info())
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating resource list embed: {e}")
            return discord.Embed(
                title="❌ Error Loading Resources",
                description="Failed to load resource list. Please try again.",
                color=discord.Color.red()
            )


class ResourceManagementView(PaginatedView):
    """
    Admin view for managing general resources
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize resource management view
        
        Args:
            user: Discord user (must be admin)
            config: Bot configuration
            data_manager: DataManager instance
        """
        self.resources = []  # Will be populated when needed
        
        super().__init__(user, self.resources, 5, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        self.update_buttons()
    
    def _add_page_items(self) -> None:
        """Add resource management buttons"""
        try:
            for i, resource in enumerate(self.current_items):
                global_index = self.current_page * self.per_page + i
                
                # Management button for each resource
                btn = Button(
                    label=f"📝 {global_index + 1}. {resource.name[:50]}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"manage_resource_{global_index}"
                )
                btn.callback = self._make_manage_callback(resource)
                self.add_item(btn)
                
        except Exception as e:
            logger.error(f"Error adding resource management buttons: {e}")
    
    def _make_manage_callback(self, resource: 'ResourceEntry'):
        """Create callback for resource management"""
        async def callback(interaction: discord.Interaction):
            try:
                # Show resource details with management options
                content = f"**Managing Resource: {resource.name}**\n\n"
                content += f"**Type:** {resource.type}\n"
                content += f"**Link:** {resource.link}\n"
                if resource.credit:
                    content += f"**Credit:** {resource.credit}\n"
                content += "\n_Resource editing and deletion will be implemented in a future update._"
                
                await interaction.response.send_message(
                    content=content,
                    ephemeral=True
                )
                
            except Exception as e:
                logger.error(f"Error in resource management callback: {e}")
                await interaction.response.send_message(
                    "❌ Failed to load resource for management.",
                    ephemeral=True
                )
        
        return callback
    
    async def create_embed(self) -> discord.Embed:
        """Create resource management embed"""
        try:
            embed = discord.Embed(
                title="⚙️ Resource Management",
                description="Manage general resources for the bot.",
                color=self.config.embed_color
            )
            
            if not self.items:
                embed.description = "_No resources to manage._"
            else:
                embed.add_field(
                    name="📊 Resource Stats",
                    value=f"**Total Resources:** {len(self.resources)}\n"
                          f"**Current Page:** {self.current_page + 1}/{self.max_pages}",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ Instructions",
                    value="Click a resource button to view details.\n"
                          "Use `/update resources` to add new resources.",
                    inline=False
                )
            
            embed.set_footer(text="Resource Management Interface")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error creating resource management embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load resource management interface.",
                color=discord.Color.red()
            )


class AddResourceView(BaseView):
    """
    View for adding new resources with a quick button
    """
    
    def __init__(self, user: discord.User, config: 'BotConfiguration', data_manager: 'DataManager'):
        """
        Initialize add resource view
        
        Args:
            user: Discord user (must be admin)
            config: Bot configuration
            data_manager: DataManager instance
        """
        super().__init__(user, config.view_timeout_seconds)
        self.config = config
        self.data_manager = data_manager
        
        # Add resource button
        add_btn = Button(
            label="➕ Add Resource",
            style=discord.ButtonStyle.success,
            custom_id="add_resource"
        )
        add_btn.callback = self._add_resource
        self.add_item(add_btn)
        
        # Cancel button
        cancel_btn = Button(
            label="❌ Cancel",
            style=discord.ButtonStyle.danger,
            custom_id="cancel"
        )
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)
    
    async def _add_resource(self, interaction: discord.Interaction) -> None:
        """Show add resource modal"""
        try:
            from .modals import ResourceModal
            
            modal = ResourceModal(self.data_manager)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error showing add resource modal: {e}")
            await interaction.response.send_message(
                "❌ Failed to open add resource form.",
                ephemeral=True
            )
    
    async def _cancel(self, interaction: discord.Interaction) -> None:
        """Cancel add resource"""
        self.stop()
        await interaction.response.edit_message(
            content="❌ *Add resource cancelled.*",
            view=None,
            embed=None
        )
    
    def create_embed(self) -> discord.Embed:
        """Create add resource embed"""
        embed = discord.Embed(
            title="➕ Add Resource",
            description="Click the button below to add a new resource to the bot.",
            color=self.config.embed_color
        )
        
        embed.add_field(
            name="📝 Resource Types",
            value="video, document, spreadsheet, guide, tool, website, etc.",
            inline=False
        )
        
        embed.set_thumbnail(url=self.config.thumbnail_url)
        return embed
