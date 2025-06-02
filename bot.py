"""
Main bot entry point for Combot
Handles initialization, events, and startup
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config import env_config
from data import DataManager
from youtube import YouTubeService
from commands import setup_commands

logger = logging.getLogger(__name__)


class Combot(commands.Bot):
    """
    Main bot class with improved initialization and state management
    
    Features:
    - Proper async initialization
    - State validation before command execution
    - Graceful shutdown handling
    - Error recovery and logging
    """
    
    def __init__(self):
        """Initialize bot with proper intents and configuration"""
        # Setup Discord intents
        intents = discord.Intents.default()
        intents.dm_messages = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",  # Prefix for legacy commands (not used)
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        # Service instances
        self.data_manager: DataManager = None
        self.youtube_service: YouTubeService = None
        
        # Bot state
        self._ready = False
        self._shutdown = False
    
    async def setup_hook(self):
        """
        Setup hook called before bot login
        Initialize services and commands here
        """
        try:
            logger.info("Starting bot initialization...")
            
            # Initialize data manager
            logger.info("Initializing data manager...")
            self.data_manager = DataManager(env_config.config_filename)
            await self.data_manager.load()
            
            # Initialize YouTube service
            logger.info("Initializing YouTube service...")
            self.youtube_service = YouTubeService(env_config.youtube_api_key)
            
            # Setup commands
            logger.info("Setting up commands...")
            setup_commands(self, self.data_manager, self.youtube_service)
            
            logger.info("Bot initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            raise
    
    async def on_ready(self):
        """Called when bot is ready and connected to Discord"""
        try:
            logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} servers")
            logger.info(f"Configured for character: {self.data_manager.config.character_name}")
            
            # Sync commands
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
                
                # Log command names for debugging
                command_names = [cmd.name for cmd in synced]
                logger.info(f"Available commands: {', '.join(command_names)}")
                
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
                # Don't raise here as bot can still function
            
            # Set bot as ready
            self._ready = True
            
            # Set bot status
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{self.data_manager.config.character_name} combos"
            )
            await self.change_presence(activity=activity)
            
            logger.info("Bot is ready and operational!")
            
        except Exception as e:
            logger.error(f"Error in on_ready: {e}", exc_info=True)
    
    async def on_error(self, event: str, *args, **kwargs):
        """Handle general bot errors"""
        logger.error(f"Bot error in event {event}: {sys.exc_info()}", exc_info=True)
    
    async def on_command_error(self, ctx, error):
        """Handle command errors (for legacy commands)"""
        logger.error(f"Command error: {error}", exc_info=True)
    
    async def on_guild_join(self, guild):
        """Called when bot joins a new server"""
        logger.info(f"Joined new server: {guild.name} (ID: {guild.id})")
        
        # Send welcome message to server owner if possible
        try:
            if guild.owner:
                embed = discord.Embed(
                    title=f"🎮 {self.data_manager.config.character_name} Combo Bot",
                    description=f"Thanks for adding me to **{guild.name}**!",
                    color=self.data_manager.config.embed_color
                )
                
                embed.add_field(
                    name="🚀 Getting Started",
                    value="Use `/combos` to explore combos\n"
                          "Admins can use `/admin setup` to configure the bot",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ Admin Setup",
                    value="Only users in the DISCORD_OWNER_IDS environment variable can use admin commands.",
                    inline=False
                )
                
                await guild.owner.send(embed=embed)
                
        except Exception as e:
            logger.warning(f"Failed to send welcome message to {guild.name}: {e}")
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a server"""
        logger.info(f"Left server: {guild.name} (ID: {guild.id})")
    
    async def on_application_command_error(self, interaction: discord.Interaction, error):
        """Handle application command errors"""
        logger.error(f"Application command error: {error}", exc_info=True)
        
        # Send user-friendly error message
        error_message = "❌ An unexpected error occurred. Please try again."
        
        # Provide specific error messages for common issues
        if isinstance(error, discord.errors.NotFound):
            error_message = "❌ The requested item was not found."
        elif isinstance(error, discord.errors.Forbidden):
            error_message = "❌ I don't have permission to perform this action."
        elif isinstance(error, discord.errors.HTTPException):
            error_message = "❌ There was a problem communicating with Discord."
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as follow_error:
            logger.error(f"Failed to send error message: {follow_error}")
    
    async def close(self):
        """Cleanup when bot shuts down"""
        logger.info("Bot shutdown initiated...")
        
        self._shutdown = True
        
        # Cleanup data manager
        if self.data_manager:
            try:
                await self.data_manager.cleanup()
                logger.info("Data manager cleanup completed")
            except Exception as e:
                logger.error(f"Error during data manager cleanup: {e}")
        
        # Clear YouTube service cache
        if self.youtube_service:
            try:
                self.youtube_service.clear_cache()
                logger.info("YouTube service cache cleared")
            except Exception as e:
                logger.error(f"Error clearing YouTube cache: {e}")
        
        # Call parent close
        await super().close()
        logger.info("Bot shutdown completed")
    
    @property
    def is_ready(self) -> bool:
        """Check if bot is fully ready"""
        return self._ready and not self._shutdown and self.data_manager is not None


# Global bot instance
bot = Combot()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        
        # Create task to close bot gracefully
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(bot.close())
        else:
            asyncio.run(bot.close())
        
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main entry point for the bot"""
    try:
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers()
        
        # Validate environment configuration
        logger.info("Validating environment configuration...")
        env_config.validate_setup()
        
        # Start the bot
        logger.info("Starting Combot...")
        await bot.start(env_config.discord_token)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure cleanup
        if not bot.is_closed():
            await bot.close()


def run():
    """
    Run the bot with proper error handling
    This is the main entry point for the application
    """
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error running bot: {e}", exc_info=True)
        sys.exit(1)


# Factory function for creating bot instances (for testing)
def create_bot(config_file: str = None) -> Combot:
    """
    Factory function to create a configured bot instance
    
    Args:
        config_file: Optional custom config file path
        
    Returns:
        Configured Combot instance
    """
    if config_file:
        # Override config filename
        import os
        os.environ["CONFIG_FILENAME"] = config_file
        
        # Reload env_config
        from .config import EnvConfig
        global env_config
        env_config = EnvConfig.from_env()
    
    return Combot()


# Version and metadata
__version__ = "2.0.0"
__author__ = "ENVYFGC"
__description__ = "Universal Fighting Game Combo Bot for Discord"


if __name__ == "__main__":
    run()
