"""
Base view classes for Discord UI components
Provides common functionality and improved error handling
"""

import logging
from typing import Any, List, Optional, TYPE_CHECKING

import discord
from discord.ui import View, Button

if TYPE_CHECKING:
    from data import DataManager
    from config import BotConfiguration

logger = logging.getLogger(__name__)


class BaseView(View):
    """
    Base view with improved error handling and common functionality
    
    Features:
    - User permission checking
    - Automatic timeout handling
    - Error logging and user feedback
    - Message cleanup on timeout
    """
    
    def __init__(self, user: discord.User, timeout: float = 180.0):
        """
        Initialize base view
        
        Args:
            user: Discord user who can interact with this view
            timeout: View timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.user = user
        self.message: Optional[discord.Message] = None
        self._is_finished = False
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Check if interaction user is authorized
        
        Args:
            interaction: Discord interaction
            
        Returns:
            True if authorized, False otherwise
        """
        if interaction.user.id != self.user.id:
            try:
                await interaction.response.send_message(
                    "❌ This menu belongs to someone else.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                try:
                    await interaction.followup.send(
                        "❌ This menu belongs to someone else.",
                        ephemeral=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to send unauthorized message: {e}")
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Handle view timeout with proper cleanup"""
        if self._is_finished:
            return
        
        self._is_finished = True
        
        if self.message:
            try:
                # Try to edit the message to show timeout
                await self.message.edit(
                    content="⏰ *This menu has timed out and is no longer active.*",
                    view=None,
                    embed=None
                )
                logger.debug(f"View timed out for user {self.user.id}")
            except discord.NotFound:
                # Message was deleted
                pass
            except discord.Forbidden:
                # No permission to edit
                logger.warning("No permission to edit timed out message")
            except Exception as e:
                logger.error(f"Error handling view timeout: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """
        Handle view errors with logging and user feedback
        
        Args:
            interaction: Discord interaction that caused the error
            error: Exception that occurred
            item: UI item that caused the error
        """
        logger.error(f"View error in {self.__class__.__name__}: {error}", exc_info=True)
        
        error_message = "❌ An unexpected error occurred. Please try again."
        
        # Provide more specific error messages for common issues
        if isinstance(error, discord.Forbidden):
            error_message = "❌ I don't have permission to perform this action."
        elif isinstance(error, discord.NotFound):
            error_message = "❌ The requested item was not found."
        elif isinstance(error, discord.HTTPException):
            error_message = "❌ There was a problem communicating with Discord."
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as follow_error:
            logger.error(f"Failed to send error message: {follow_error}")
    
    def stop(self) -> None:
        """Stop the view and mark as finished"""
        self._is_finished = True
        super().stop()


class PaginatedView(BaseView):
    """
    Base paginated view with navigation controls
    
    Features:
    - Automatic pagination calculation
    - Navigation button management
    - Flexible page item addition
    - Error handling for page operations
    """
    
    def __init__(self, user: discord.User, items: List[Any], 
                 per_page: int = 10, timeout: float = 180.0):
        """
        Initialize paginated view
        
        Args:
            user: Discord user who can interact with this view
            items: List of items to paginate
            per_page: Items per page
            timeout: View timeout in seconds
        """
        super().__init__(user, timeout)
        self.items = items or []
        self.per_page = max(1, per_page)  # Ensure at least 1 item per page
        self.current_page = 0
    
    @property
    def max_pages(self) -> int:
        """Get total number of pages"""
        if not self.items:
            return 1
        return max(1, (len(self.items) - 1) // self.per_page + 1)
    
    @property
    def current_items(self) -> List[Any]:
        """Get items for current page"""
        if not self.items:
            return []
        
        start = self.current_page * self.per_page
        end = start + self.per_page
        return self.items[start:end]
    
    def update_buttons(self) -> None:
        """Update navigation buttons based on current page"""
        try:
            self.clear_items()
            
            # Add page-specific buttons first
            self._add_page_items()
            
            # Add navigation buttons
            self._add_navigation_buttons()
            
            # Add utility buttons
            self._add_utility_buttons()
            
        except Exception as e:
            logger.error(f"Error updating buttons in {self.__class__.__name__}: {e}")
            # Clear items to prevent broken state
            self.clear_items()
    
    def _add_page_items(self) -> None:
        """Override this method to add page-specific buttons"""
        pass
    
    def _add_navigation_buttons(self) -> None:
        """Add previous/next navigation buttons"""
        if self.max_pages <= 1:
            return
        
        # Previous page button
        if self.current_page > 0:
            prev_btn = Button(
                label="◀️ Previous",
                style=discord.ButtonStyle.secondary,
                custom_id="nav_prev"
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)
        
        # Next page button
        if self.current_page < self.max_pages - 1:
            next_btn = Button(
                label="Next ▶️",
                style=discord.ButtonStyle.secondary,
                custom_id="nav_next"
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)
    
    def _add_utility_buttons(self) -> None:
        """Add utility buttons like back/close"""
        back_btn = Button(
            label="↩️ Back",
            style=discord.ButtonStyle.danger,
            custom_id="nav_back"
        )
        back_btn.callback = self._go_back
        self.add_item(back_btn)
    
    async def _prev_page(self, interaction: discord.Interaction) -> None:
        """Navigate to previous page"""
        try:
            old_page = self.current_page
            self.current_page = max(0, self.current_page - 1)
            
            if self.current_page != old_page:
                self.update_buttons()
                embed = await self.create_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error in previous page navigation: {e}")
            await self._handle_navigation_error(interaction, "previous page")
    
    async def _next_page(self, interaction: discord.Interaction) -> None:
        """Navigate to next page"""
        try:
            old_page = self.current_page
            self.current_page = min(self.max_pages - 1, self.current_page + 1)
            
            if self.current_page != old_page:
                self.update_buttons()
                embed = await self.create_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error in next page navigation: {e}")
            await self._handle_navigation_error(interaction, "next page")
    
    async def _go_back(self, interaction: discord.Interaction) -> None:
        """Handle back button - override in subclasses"""
        try:
            self.stop()
            await interaction.response.edit_message(
                content="↩️ *Returned to previous menu.*",
                view=None,
                embed=None
            )
        except Exception as e:
            logger.error(f"Error in back navigation: {e}")
            await self._handle_navigation_error(interaction, "go back")
    
    async def _handle_navigation_error(self, interaction: discord.Interaction, action: str) -> None:
        """Handle navigation errors with user feedback"""
        error_message = f"❌ Failed to {action}. Please try again."
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception:
            logger.error(f"Failed to send navigation error message")
    
    async def create_embed(self) -> discord.Embed:
        """Override this method to create the embed for current page"""
        raise NotImplementedError("Subclasses must implement create_embed method")
    
    def get_page_info(self) -> str:
        """Get formatted page information string"""
        if not self.items:
            return "No items"
        
        start = self.current_page * self.per_page + 1
        end = min((self.current_page + 1) * self.per_page, len(self.items))
        
        return f"Showing {start}-{end} of {len(self.items)}"
    
    def set_page(self, page: int) -> bool:
        """
        Set current page with validation
        
        Args:
            page: Page number (0-indexed)
            
        Returns:
            True if page was changed, False if invalid
        """
        if 0 <= page < self.max_pages:
            old_page = self.current_page
            self.current_page = page
            return old_page != page
        return False


class ConfirmationView(BaseView):
    """
    Simple confirmation dialog view
    
    Features:
    - Yes/No buttons with customizable labels
    - Callback functions for each option
    - Automatic cleanup after selection
    """
    
    def __init__(self, user: discord.User, timeout: float = 60.0,
                 confirm_label: str = "✅ Yes", cancel_label: str = "❌ No"):
        """
        Initialize confirmation view
        
        Args:
            user: Discord user who can interact with this view
            timeout: View timeout in seconds
            confirm_label: Label for confirm button
            cancel_label: Label for cancel button
        """
        super().__init__(user, timeout)
        self.result: Optional[bool] = None
        self.confirmed = False
        
        # Add confirm button
        confirm_btn = Button(
            label=confirm_label,
            style=discord.ButtonStyle.success,
            custom_id="confirm"
        )
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)
        
        # Add cancel button
        cancel_btn = Button(
            label=cancel_label,
            style=discord.ButtonStyle.danger,
            custom_id="cancel"
        )
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)
    
    async def _confirm(self, interaction: discord.Interaction) -> None:
        """Handle confirm button press"""
        self.result = True
        self.confirmed = True
        self.stop()
        await self.on_confirm(interaction)
    
    async def _cancel(self, interaction: discord.Interaction) -> None:
        """Handle cancel button press"""
        self.result = False
        self.stop()
        await self.on_cancel(interaction)
    
    async def on_confirm(self, interaction: discord.Interaction) -> None:
        """Override this method to handle confirmation"""
        await interaction.response.edit_message(
            content="✅ Confirmed!",
            view=None,
            embed=None
        )
    
    async def on_cancel(self, interaction: discord.Interaction) -> None:
        """Override this method to handle cancellation"""
        await interaction.response.edit_message(
            content="❌ Cancelled.",
            view=None,
            embed=None
        )
