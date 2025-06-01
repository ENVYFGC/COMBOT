## **Combot is a Discord bot designed for fighting game communities that imports combo data from YouTube playlists and presents it through interactive menus, allowing players to browse combos by category and starter while managing resources and notable player profiles.**

## Combot Installation Guide

## Prerequisites
- Python 3.8 or higher
- Discord Bot Token
- YouTube Data API v3 Key

## Quick Setup

### 1. Clone and Install
```bash
git clone https://github.com/ENVYFGC/combot.git
cd combot
pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
cp .env.example .env
```

Edit `.env` file with your credentials:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here
DISCORD_OWNER_IDS=your_discord_user_id
```

### 3. Get API Keys

**Discord Bot Token:**
1. Go to https://discord.com/developers/applications
2. Create new application → Bot section
3. Create bot and copy token
4. Enable Message Content Intent

**YouTube API Key:**
1. Go to https://console.cloud.google.com/
2. Create project → Enable YouTube Data API v3
3. Create Credentials → API Key
4. Restrict to YouTube Data API v3

**Discord User ID:**
1. Enable Developer Mode in Discord settings
2. Right-click your profile → Copy User ID

### 4. Run Bot
```bash
python run.py
```

## First Time Setup

1. Invite bot to server with appropriate permissions
2. Run `/admin setup` to configure character and colors
3. Add categories: `/admin add_category Midscreen`
4. Add starters: `/admin add_starter Midscreen "5P"`
5. Import combos: `/update Midscreen <youtube_playlist_url> "5P"`
6. Test with `/combos`

## File Structure
```
combot/
├── config.py              # Configuration management
├── data.py                 # Data models and persistence
├── youtube.py              # YouTube API service
├── commands.py             # Discord commands
├── bot.py                  # Main bot entry point
├── utils.py                # Utility functions
├── run.py                  # Execution script
└── views/                  # Discord UI components
    ├── base.py
    ├── modals.py
    ├── main_menu.py
    ├── starter_list.py
    ├── combo_list.py
    ├── resource.py
    └── player.py
```

## Commands

**User Commands:**
- `/combos` - Open main combo menu

**Admin Commands:**
- `/admin setup` - Initial configuration
- `/admin add_starter <category> <starter>` - Add starter
- `/admin add_category <name>` - Add category
- `/admin add_player` - Add notable player
- `/update <category> <playlist_url> <starter>` - Import combos
- `/update resources <url>` - Add resource

## Docker Deployment (Optional)
```bash
docker-compose up -d
```

## Troubleshooting

**"Missing environment variables":**
- Ensure .env file exists with correct values
- Check Discord token and YouTube API key are valid

**"Bot is loading":**
- Wait 30 seconds after startup
- Check logs for initialization errors

**Commands not appearing:**
- Verify bot has applications.commands scope
- Restart bot to re-sync commands

**YouTube API errors:**
- Check quota limits in Google Cloud Console
- Ensure playlist is public/unlisted
- Verify API key has YouTube Data API v3 enabled

**Permission errors:**
- Confirm Discord user ID is in DISCORD_OWNER_IDS
- Use Developer Mode to get correct user ID

## Support
- GitHub Issues: Report bugs or request features
- Check logs with: `export LOG_LEVEL=DEBUG && python run.py`
