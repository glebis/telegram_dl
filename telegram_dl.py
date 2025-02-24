import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from telethon.errors import FloodWaitError
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

import typer
from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from telethon import TelegramClient
from telethon.tl.types import Dialog, User, Chat, Channel
from telethon.tl.functions.messages import SearchRequest

from config import (
    load_config,
    save_config,
    get_session_path,
    is_configured
)

app = typer.Typer()
console = Console()

async def ensure_client() -> TelegramClient:
    """Ensure we have a configured client."""
    if not is_configured():
        console.print("First-time setup required!", style="bold yellow")
        api_id = IntPrompt.ask("Please enter your Telegram api_id")
        api_hash = Prompt.ask("Please enter your Telegram api_hash")
        save_config({"api_id": api_id, "api_hash": api_hash})
    
    config = load_config()
    client = TelegramClient(str(get_session_path()), config["api_id"], config["api_hash"])
    await client.start()
    return client

def sanitize_filename(name: str) -> str:
    """Create a safe filename from chat name."""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name).strip()

async def get_all_chats(client: TelegramClient, search_term: Optional[str] = None) -> List[Dialog]:
    """Get all chats, optionally filtered by search term."""
    chats = await client.get_dialogs()
    if search_term:
        search_term = search_term.lower()
        chats = [
            chat for chat in chats
            if search_term in chat.name.lower()
        ]
    return sorted(chats, key=lambda x: x.date, reverse=True)

def display_chats(chats: List[Dialog], selected_indices: Optional[List[int]] = None) -> Table:
    """Display chats in a rich table."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim")
    table.add_column("Selected", style="bold green")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Last Message", style="dim")

    for idx, chat in enumerate(chats, 1):
        chat_type = (
            "Private" if isinstance(chat.entity, User) else
            "Group" if isinstance(chat.entity, Chat) else
            "Channel" if isinstance(chat.entity, Channel) else
            "Unknown"
        )
        last_msg_date = chat.date.strftime("%Y-%m-%d %H:%M")
        selected = "✓" if selected_indices and (idx-1) in selected_indices else " "
        table.add_row(
            str(idx),
            selected,
            chat.name,
            chat_type,
            last_msg_date
        )
    
    return table

def interactive_select_chats(chats: List[Dialog]) -> List[int]:
    """Interactively select chats to export."""
    selected_indices: List[int] = []
    current_page = 0
    page_size = 10
    total_pages = (len(chats) + page_size - 1) // page_size

    while True:
        console.clear()
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(chats))
        page_chats = chats[start_idx:end_idx]

        # Display current page of chats
        table = display_chats(page_chats, 
                            [i - start_idx for i in selected_indices if start_idx <= i < end_idx])
        console.print(table)

        # Navigation and selection info
        console.print(f"\nPage {current_page + 1} of {total_pages}")
        console.print("\nCommands:")
        console.print("- Enter chat number to toggle selection")
        console.print("- 'n' for next page")
        console.print("- 'p' for previous page")
        console.print("- 'd' when done")
        console.print(f"\nSelected: {len(selected_indices)} chats")

        choice = Prompt.ask("Enter command").lower()

        if choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'd':
            if not selected_indices:
                if not Confirm.ask("No chats selected. Do you want to exit anyway?"):
                    continue
            break
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(page_chats):
                    global_idx = start_idx + idx
                    if global_idx in selected_indices:
                        selected_indices.remove(global_idx)
                    else:
                        selected_indices.append(global_idx)
                else:
                    console.print("[red]Invalid chat number[/red]")
            except ValueError:
                console.print("[red]Invalid command[/red]")

    return sorted(selected_indices)

class RateLimiter:
    def __init__(self, messages_per_second: float = 1.0):
        self.messages_per_second = messages_per_second
        self.last_message_time = 0
        self.message_count = 0
        self.window_start = time.time()
    
    async def wait(self):
        current_time = time.time()
        
        # Wait for rate limit
        time_since_last = current_time - self.last_message_time
        if time_since_last < (1.0 / self.messages_per_second):
            await asyncio.sleep((1.0 / self.messages_per_second) - time_since_last)
        
        self.last_message_time = time.time()

async def handle_rate_limit_error(error: FloodWaitError):
    """Handle Telegram's FloodWaitError by waiting the required time."""
    wait_time = error.seconds
    console.print(f"\n[yellow]Rate limit exceeded. Waiting for {wait_time} seconds...[/yellow]")
    await asyncio.sleep(wait_time)

async def get_user_info(client: TelegramClient, user_id: int, rate_limiter: RateLimiter) -> dict:
    """Get user information by user ID."""
    while True:
        try:
            await rate_limiter.wait()
            user = await client.get_entity(user_id)
            return {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        except FloodWaitError as e:
            await handle_rate_limit_error(e)
        except Exception:
            return None

async def export_chat(client: TelegramClient, chat: Dialog, format: str, limit: int = 100, include_usernames: bool = True):
    """Export chat messages."""
    messages = []
    message_count = 0
    user_cache = {}
    
    # Initialize rate limiters
    message_rate_limiter = RateLimiter(1.0)  # 1 message per second
    user_rate_limiter = RateLimiter(0.5)  # 2 user info requests per second (conservative)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        "•",
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task(f"Downloading messages from {chat.name}", total=limit)
        
        while True:
            try:
                async for message in client.iter_messages(chat):
                    if message_count >= limit:
                        break
                    
                    await message_rate_limiter.wait()
                    
                    msg_data = {
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text,
                        "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None,
                    }
                    
                    # Handle user information
                    if message.from_id and include_usernames:
                        user_id = message.from_id.user_id
                        if user_id not in user_cache:
                            user_cache[user_id] = await get_user_info(client, user_id, user_rate_limiter)
                        msg_data["from_user"] = user_cache[user_id]
                    elif message.from_id:
                        msg_data["from_id"] = message.from_id.user_id
                    
                    messages.append(msg_data)
                    message_count += 1
                    progress.update(task, advance=1)
                
                break  # Success, exit the retry loop
                
            except FloodWaitError as e:
                progress.stop()
                await handle_rate_limit_error(e)
                progress.start()
                continue
    
    # Create export directory if it doesn't exist
    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)
    
    # Create filename with date prefix and sanitized chat name
    date_prefix = datetime.now().strftime("%Y%m%d")
    safe_chat_name = sanitize_filename(chat.name)
    filename = export_dir / f"{date_prefix}_{safe_chat_name}.{format}"
    
    if format == "json":
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "chat_name": chat.name,
                "chat_id": chat.id,
                "export_date": datetime.now().isoformat(),
                "messages": messages
            }, f, indent=2, ensure_ascii=False)
    else:
        # Markdown format
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# {chat.name}\n\n")
            f.write(f"Exported on: {datetime.now().isoformat()}\n\n")
            for msg in reversed(messages):  # Show oldest messages first
                date = datetime.fromisoformat(msg["date"]).strftime("%Y-%m-%d %H:%M")
                
                # Build header with message ID and user information
                header_parts = [f"### {date} [ID: {msg['id']}]"]
                
                if "from_user" in msg and msg["from_user"]:
                    user = msg["from_user"]
                    username = user["username"] or "No username"
                    name = f"{user['first_name']} {user['last_name']}".strip() or "No name"
                    header_parts.append(f"@{username} ({name})")
                elif "from_id" in msg:
                    header_parts.append(f"User ID: {msg['from_id']}")
                
                f.write(" - ".join(header_parts) + "\n\n")
                
                if msg["text"]:
                    f.write(f"{msg['text']}\n\n")
                if msg["reply_to"]:
                    f.write(f"*↪️ Reply to message [ID: {msg['reply_to']}]*\n\n")
                f.write("---\n\n")
    
    console.print(f"Chat exported to [bold green]{filename}[/bold green]")

@app.command()
def list(
    search: str = typer.Option(None, "--search", "-s", help="Search term to filter chats"),
    limit: int = typer.Option(30, "--limit", "-l", help="Number of chats to display (default: 30)"),
    export: bool = typer.Option(False, "--export", "-e", help="Enable interactive selection and export after listing")
):
    """List and search through your Telegram chats.
    
    Shows most recent chats by default, with options to search and export.
    Use --export to select and download chats directly from search results.
    """
    async def _list():
        client = await ensure_client()
        chats = await get_all_chats(client, search)
        displayed_chats = chats[:limit]
        
        if export:
            console.print("[bold]Select chats to export:[/bold]")
            selected_indices = interactive_select_chats(displayed_chats)
            
            if selected_indices:
                # Ask for export format if not specified
                export_format = Prompt.ask(
                    "Select export format",
                    choices=["json", "md"],
                    default="json"
                )
                
                # Ask for message limit
                msg_limit = IntPrompt.ask(
                    "Enter maximum messages per chat",
                    default=100
                )
                
                for idx in selected_indices:
                    chat = displayed_chats[idx]
                    console.print(f"\nExporting chat: [bold]{chat.name}[/bold] (limit: {msg_limit} messages)")
                    await export_chat(client, chat, export_format, limit=msg_limit)
                
                console.print("\n[green]Export completed![/green]")
            else:
                console.print("No chats selected for export")
        else:
            table = display_chats(displayed_chats)
            console.print(table)
            if len(chats) > limit:
                console.print(f"\n[yellow]Showing {limit} of {len(chats)} chats. Use --limit option to show more.[/yellow]")
            console.print("\n[blue]Tip: Use --export flag to select and export chats directly from search results[/blue]")
        
        await client.disconnect()
    
    asyncio.run(_list())

@app.command()
def export(
    format: str = typer.Option(None, "--format", "-f", help="Export format: 'json' or 'md' (markdown)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-n", help="Use interactive chat selection (default: true)"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of messages per chat (default: 100)"),
    include_usernames: bool = typer.Option(True, "--usernames/--no-usernames", "-u/-nu", help="Include username information in export (default: true)")
):
    """Export chat history with rate limiting and error handling.
    
    Downloads messages with automatic rate limiting (1 msg/sec) and username resolution.
    Handles rate limit errors (429) automatically with smart retrying.
    Exports are saved to the 'exports' directory with date-prefixed filenames.
    """
    async def _export():
        client = await ensure_client()
        chats = await get_all_chats(client)

        if interactive:
            selected_indices = interactive_select_chats(chats)
            if not selected_indices:
                console.print("No chats selected for export")
                await client.disconnect()
                return
        else:
            # If not interactive, export all chats
            selected_indices = list(range(len(chats)))

        # If format is not specified, ask for it
        export_format = format
        if not export_format:
            export_format = Prompt.ask(
                "Select export format",
                choices=["json", "md"],
                default="json"
            )

        for idx in selected_indices:
            chat = chats[idx]
            console.print(f"\nExporting chat: [bold]{chat.name}[/bold] (limit: {limit} messages, usernames: {include_usernames})")
            await export_chat(client, chat, export_format, limit=limit, include_usernames=include_usernames)

        console.print("\n[green]Export completed![/green]")
        await client.disconnect()
    
    asyncio.run(_export())

if __name__ == "__main__":
    app()
