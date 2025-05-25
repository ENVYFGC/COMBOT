# Combot - Universal Fighting Game Combo Bot

A Discord bot for managing and displaying fighting game combos, resources, and player information. Built to be flexible enough for any fighting game character or community.

## Features

- **Dynamic Combo Management** - Organize combos by categories and starters
- **YouTube Playlist Integration** - Import combos directly from YouTube playlists
- **Notable Players Section** - Showcase top players with social links
- **Resource Management** - Share guides, spreadsheets, and other resources
- **Fully Customizable** - Configure for any fighting game character

## Prerequisites

Before setting up the bot, make sure you have:

- Python 3.9 or higher installed
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/docs/getting-started))
- A YouTube Data API Key ([Google Cloud Console](https://developers.google.com/youtube/v3/getting-started))
- Your Discord User ID (for admin permissions)

## Installation

### Step 1: Get the Code

Clone this repository or download the files:

```bash
git clone https://github.com/ENVYFGC/combot.git
cd combot
```

### Step 2: Install Dependencies

Install the required Python packages:

```bash
pip install discord.py python-dotenv google-api-python-client
```

### Step 3: Configure Environment Variables

Create a `.env` file in the bot directory with your credentials:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here
DISCORD_OWNER_IDS=your_discord_user_id_here
```

To find your Discord User ID:
1. Open Discord and go to User Settings
2. Navigate to Advanced settings
3. Enable Developer Mode
4. Right-click your username anywhere and select "Copy User ID"

### Step 4: Run the Bot

Start the bot with:

```bash
python combot.py
```

### Step 5: Initial Configuration

Once the bot is online in your Discord server, run the setup command:

```
/admin setup
```

You'll be prompted to enter:
- Character name (e.g., "Ryu", "Sol Badguy", "Kazuya")
- Thumbnail URL for your character (optional)
- Embed color in hex format (e.g., FF0000 for red)
- Section titles for ender info and routes (leave blank to hide these sections)

## Usage Guide

### Setting Up Combo Categories

The bot comes with "Midscreen" and "Corner" categories by default. You can add more categories based on your game's needs:

```
/admin add_category name:Counterhit
/admin add_category name:Anti-Air
/admin add_category name:Punish
```

### Adding Starters

Each category needs starter moves. Add them using:

```
/admin add_starter category:Midscreen starter:5A
/admin add_starter category:Midscreen starter:2B
/admin add_starter category:Corner starter:throw
```

### Importing Combos from YouTube

The bot can import combos from YouTube playlists. Here's how:

1. Create a YouTube playlist with your combo videos
2. Make sure each video's description follows the required format (see below)
3. Use the update command:

```
/update category:Midscreen playlist_or_url:https://youtube.com/playlist?list=YOUR_PLAYLIST_ID starter:5A
```

### YouTube Video Description Format

For the bot to correctly parse combos, video descriptions should follow this format:

```
Notation: 5A > 5B > 2C > 236A > 66 > 5B > j.C > j.B > j.C
Notes: Basic midscreen combo, 2500 damage, builds 1 bar
```

The word "Notation:" must appear on its own line, followed by the combo notation. The "Notes:" line is optional but recommended for adding damage values, meter usage, or other important details.

### Managing Resources

Add guides, spreadsheets, or other helpful resources:

```
/update category:Resources playlist_or_url:https://docs.google.com/your-guide starter:
```

When you run this command, a form will appear asking for:
- Resource name
- Resource type (video, document, spreadsheet, etc.)
- Link
- Credit/source (optional)

### Adding Notable Players

Showcase top players in your character's community:

```
/admin add_player
```

Fill in the form with:
- Player name
- Region emoji (like 🇺🇸 or 🇯🇵)
- Social media link (Twitter/X preferred)
- Character color/costume image URL
- Description (use \n for line breaks)

## Command Reference

### User Commands

| Command | Description |
|---------|-------------|
| `/combos` | Opens the main combo menu |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/admin setup` | Configure the bot for your character |
| `/admin config` | View current bot configuration |
| `/admin add_category` | Add a new combo category |
| `/admin add_starter` | Add a starter to a category |
| `/admin remove_starter` | Remove a starter from a category |
| `/admin add_player` | Add a notable player |
| `/admin remove_player` | Remove a player by name |
| `/update` | Import combos or add resources |

## Data Storage

The bot stores all data in a JSON file that's automatically created:
- Default filename: `character_bot_data.json`
- Contains all combos, resources, players, and configuration
- Make sure to back up this file regularly

## Troubleshooting

### Bot won't start
- Double-check your `.env` file contains valid tokens
- Ensure you're using Python 3.9 or higher
- Verify all dependencies are properly installed

### Commands don't appear in Discord
- Make sure the bot was invited with the `applications.commands` scope
- Commands can take a few minutes to sync
- Try typing `/` in Discord to refresh the command list

### YouTube import fails
- Check if you've exceeded the YouTube API daily quota (10,000 units)
- Ensure the playlist is public
- Verify video descriptions follow the correct format
- Double-check the playlist ID or URL

### "Unauthorized" error on admin commands
- Only Discord users whose IDs are in `DISCORD_OWNER_IDS` can use admin commands
- You can add multiple IDs separated by commas: `DISCORD_OWNER_IDS=123456789,987654321`

## Best Practices

1. **Organize your playlists** - Create separate playlists for each starter or category
2. **Use consistent notation** - Stick to one notation style across all combos
3. **Back up regularly** - Save copies of your `character_bot_data.json` file
4. **Test with small playlists** - Import a few videos first to ensure formatting is correct
5. **Monitor API usage** - YouTube API has daily quotas, so plan large imports accordingly

## Advanced Configuration

### Running Multiple Bots

If you need bots for multiple characters, you can run separate instances with different config files:

```python
# Create a wrapper script for each character
import os
os.environ["CONFIG_FILENAME"] = "ryu_data.json"
from combot import bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
```

### Custom Categories

While designed for fighting game combos, the category system is flexible. You can create categories for:
- Setups and okizeme
- Frame traps
- Reset situations
- Character-specific mechanics
- Matchup-specific strategies

## Contributing

Contributions are welcome! Some areas that could use improvement:
- Additional import sources beyond YouTube
- Combo damage and meter tracking
- Search functionality within combos
- Direct video embedding
- Frame data integration

## License

This project is available under the MIT License. Feel free to use and modify it for your community's needs.

---

Created for the fighting game community. If you find this useful, consider contributing back to help others!
