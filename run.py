#!/usr/bin/env python3
"""
Simple run script for Combot
This script provides an easy way to start the bot with error handling
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# LOAD .ENV FILE FIRST!
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads your .env file before checking
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables")

def setup_logging():
    """Setup basic logging configuration"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce Discord.py logging noise
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)

def check_environment():
    """Check if required environment variables are set"""
    required_vars = ['DISCORD_BOT_TOKEN', 'YOUTUBE_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please create a .env file or set these environment variables.")
        print("   See .env.example for reference.")
        print(f"\n🔍 Current environment check:")
        print(f"   DISCORD_BOT_TOKEN: {'✅ Set' if os.getenv('DISCORD_BOT_TOKEN') else '❌ Missing'}")
        print(f"   YOUTUBE_API_KEY: {'✅ Set' if os.getenv('YOUTUBE_API_KEY') else '❌ Missing'}")
        return False
    
    return True

def main():
    """Main entry point"""
    print("🎮 Starting Combot v2.0...")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Check environment (AFTER loading .env)
    if not check_environment():
        sys.exit(1)
    
    # Check if .env file exists
    env_file = project_root / ".env"
    if env_file.exists():
        print("✅ Found .env file")
    else:
        print("⚠️  No .env file found (using system environment variables)")
    
    try:
        # Import and run the bot directly
        logger.info("Importing bot modules...")
        
        # Import the bot class directly from bot.py
        from bot import run as run_bot
        
        logger.info("Starting bot...")
        run_bot()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed: pip install -r requirements.txt")
        print("💡 Make sure all Python files are in the same directory as run.py")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
