"""discord-cli — CLI entry point."""

import click
from rich.console import Console
from rich.table import Table

from .data import data_group
from .discord_cmds import discord_group
from .query import query_group

console = Console()


@click.group()
@click.version_option(package_name="discord-cli")
def cli():
    """discord — CLI for fetching Discord chat history and searching messages."""
    pass


@cli.command("auth")
@click.option("--save", is_flag=True, help="Save found token to .env automatically")
def auth(save: bool):
    """Extract Discord token from local browser/Discord client."""
    import httpx

    from ..auth import find_tokens, save_token_to_env

    console.print("[dim]Scanning for Discord tokens...[/dim]")
    results = find_tokens()

    if not results:
        console.print("[red]No tokens found.[/red]")
        console.print(
            "[dim]Make sure Discord desktop app or browser is logged in.[/dim]"
        )
        return

    console.print(f"[dim]Found {len(results)} candidate token(s), validating...[/dim]")

    # Validate each token against the API
    valid_token = None
    valid_source = None
    user_info = None

    for r in results:
        token = r["token"]
        try:
            resp = httpx.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": token},
                timeout=10.0,
            )
            if resp.status_code == 200:
                user_info = resp.json()
                valid_token = token
                valid_source = r["source"]
                break
        except Exception:
            continue

    if not valid_token or not user_info:
        console.print("[red]No valid token found. All tokens returned 401.[/red]")
        console.print("[dim]Try logging into Discord in your browser and retry.[/dim]")
        return

    masked = f"{valid_token[:8]}...{valid_token[-8:]}"
    username = user_info.get("username", "?")
    global_name = user_info.get("global_name") or username
    console.print(
        f"[green]✓[/green] Valid token from [cyan]{valid_source}[/cyan]: {masked}"
    )
    console.print(
        f"  Logged in as: [bold]{global_name}[/bold] (@{username})"
    )

    if save:
        env_path = save_token_to_env(valid_token)
        console.print(f"[green]✓[/green] Saved to {env_path}")
    else:
        console.print(
            "\n[dim]Run with --save to auto-save to .env[/dim]"
        )


# Register sub-groups
cli.add_command(discord_group, "dc")

# Register top-level query commands
for name, cmd in query_group.commands.items():
    cli.add_command(cmd, name)

# Register top-level data commands
for name, cmd in data_group.commands.items():
    cli.add_command(cmd, name)
