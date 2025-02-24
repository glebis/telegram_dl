# Telegram Chat Downloader

A Python-based utility for downloading Telegram chat history using the Telethon library. This tool provides a user-friendly interface to browse your Telegram chats and export conversations in either JSON or Markdown format, with built-in rate limiting and error handling.

## Features

- Interactive chat browsing and selection:
  - List all accessible chats, sorted by most recent activity
  - Search functionality with instant export capability
  - Multi-chat selection support
  - Paginated display (10 chats per page)

- Smart export options:
  - JSON format for data processing
  - Markdown format for human readability
  - Username and user information inclusion (optional)
  - Configurable message limit per chat

- Rate Limiting and Error Handling:
  - Automatic rate limiting according to Telegram's rules
  - Smart handling of rate limit errors (429)
  - Auto-retry with appropriate waiting periods
  - Progress tracking with time estimates

- User Information:
  - Username lookup and caching
  - Full user details (first name, last name, username)
  - Option to disable username lookups

## Prerequisites

- Python 3.8 or higher
- Telegram API credentials (api_id and api_hash)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/telegram-dl.git
cd telegram-dl
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your Telegram API credentials:
   - Go to https://my.telegram.org/apps
   - Create a new application
   - Note down your `api_id` and `api_hash`

## Configuration

Before first use, you'll need to:
1. Configure your Telegram API credentials
2. Authenticate with your Telegram account

## Usage

### Listing and Searching Chats

1. List recent chats (default shows 30):
```bash
python telegram_dl.py list
```

2. List with custom limit:
```bash
python telegram_dl.py list --limit 50
```

3. Search for specific chats:
```bash
python telegram_dl.py list --search "chat name"
```

4. Search and export in one go:
```bash
python telegram_dl.py list --search "chat name" --export
```

### Exporting Chats

1. Interactive export (recommended):
```bash
python telegram_dl.py export
```

2. Export with specific format:
```bash
python telegram_dl.py export --format json  # or md for markdown
```

3. Export with custom message limit:
```bash
python telegram_dl.py export --limit 500  # default is 100
```

4. Export without usernames:
```bash
python telegram_dl.py export --no-usernames
```

5. Non-interactive export:
```bash
python telegram_dl.py export --no-interactive
```

### Export Formats

#### JSON Format
```json
{
  "chat_name": "Example Chat",
  "chat_id": 123456789,
  "export_date": "2024-02-24T17:30:00",
  "messages": [
    {
      "id": 1,
      "date": "2024-02-24T17:00:00",
      "text": "Hello world",
      "from_user": {
        "id": 987654321,
        "username": "john_doe",
        "first_name": "John",
        "last_name": "Doe"
      },
      "reply_to": null
    }
  ]
}
```

#### Markdown Format
```markdown
# Example Chat

Exported on: 2024-02-24T17:30:00

### 2024-02-24 17:00 [ID: 1234] - @john_doe (John Doe)

Hello world

*↪️ Reply to message [ID: 1233]*

---
```

### Rate Limits

The tool automatically handles Telegram's rate limits:

- Per Chat: 1 message per second
- User Info: 2 requests per second
- Automatic handling of rate limit errors (429)
- Progress tracking with time estimates

If you encounter a rate limit:
1. The tool will automatically pause
2. Display the required wait time
3. Resume automatically after waiting

## Export Formats

### JSON Format
The JSON export includes:
- Message text
- Timestamps
- Sender information
- Media references
- Replies and forwards

### Markdown Format
The Markdown export provides:
- Human-readable conversation format
- Formatted messages with sender names
- Timestamps
- Links to media files (if downloaded)
- Message IDs for reference and reply tracking

## Security and Data Storage

### Authentication
- First-time setup requires Telegram API credentials
- Interactive prompt for `api_id` and `api_hash`
- Credentials stored in `~/.telegram_dl/config.json`
- Session data stored in `~/.telegram_dl/user.session`

### Security Note
This tool requires authentication with your Telegram account. Your session data is stored locally and securely. Never share your:
- `api_id`
- `api_hash`
- Session files
- Configuration files

### Export Storage
- Exports are saved in the `exports/` directory
- Filenames include date and chat name: `YYYYMMDD_chatname.{json|md}`
- One file per chat for better organization

## License

MIT License - See LICENSE file for details
