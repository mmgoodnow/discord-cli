"""Data commands — export, purge, analyze, summary."""

import json

import click
from rich.console import Console

from ..db import MessageDB

console = Console()


@click.group("data", invoke_without_command=True)
def data_group():
    """Data management commands (registered at top-level)."""
    pass


@data_group.command("export")
@click.argument("channel")
@click.option("-f", "--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("-o", "--output", "output_file", help="Output file path")
@click.option("--hours", type=int, help="Only export last N hours")
def export(channel: str, fmt: str, output_file: str | None, hours: int | None):
    """Export messages from CHANNEL to text or JSON."""
    db = MessageDB()
    channel_id = db.resolve_channel_id(channel)

    if channel_id is None:
        console.print(f"[red]Channel '{channel}' not found in database.[/red]")
        db.close()
        return

    if hours:
        msgs = db.get_recent(channel_id=channel_id, hours=hours, limit=100000)
    else:
        msgs = db.get_recent(channel_id=channel_id, hours=None, limit=100000)
    db.close()

    if not msgs:
        console.print(f"[yellow]No messages found for '{channel}'.[/yellow]")
        return

    if fmt == "json":
        content = json.dumps(msgs, ensure_ascii=False, indent=2, default=str)
    else:
        lines = []
        for msg in msgs:
            ts = (msg.get("timestamp") or "")[:19]
            sender = msg.get("sender_name") or "Unknown"
            text = msg.get("content") or ""
            lines.append(f"[{ts}] {sender}: {text}")
        content = "\n".join(lines)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        console.print(f"[green]✓[/green] Exported {len(msgs)} messages to {output_file}")
    else:
        console.print(content)


@data_group.command("purge")
@click.argument("channel")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
def purge(channel: str, yes: bool):
    """Delete all stored messages for CHANNEL."""
    db = MessageDB()
    channel_id = db.resolve_channel_id(channel)

    if channel_id is None:
        console.print(f"[red]Channel '{channel}' not found in database.[/red]")
        db.close()
        return

    if not yes:
        count = db.count(channel_id)
        if not click.confirm(f"Delete {count} messages from channel {channel_id}?"):
            db.close()
            return

    deleted = db.delete_channel(channel_id)
    db.close()
    console.print(f"[green]✓[/green] Deleted {deleted} messages")


@data_group.command("analyze")
@click.argument("channel")
@click.option("--hours", type=int, default=24, help="Analyze last N hours")
@click.option("-p", "--prompt", help="Custom analysis prompt")
def analyze(channel: str, hours: int, prompt: str | None):
    """Analyze channel messages with AI (Claude)."""
    from ..analyzer import analyze_messages

    db = MessageDB()
    channel_id = db.resolve_channel_id(channel)

    if channel_id is None:
        console.print(f"[red]Channel '{channel}' not found.[/red]")
        db.close()
        return

    channels = db.get_channels()
    ch_name = next((c["channel_name"] for c in channels if c["channel_id"] == channel_id), channel)

    msgs = db.get_recent(channel_id=channel_id, hours=hours)
    db.close()

    if not msgs:
        console.print(f"[yellow]No messages in last {hours}h.[/yellow]")
        return

    console.print(f"[dim]Analyzing {len(msgs)} messages from #{ch_name}...[/dim]")
    result = analyze_messages(msgs, prompt=prompt, chat_name=ch_name)
    console.print(result)


@data_group.command("summary")
@click.option("-c", "--channel", help="Filter by channel name (default: all)")
@click.option("--hours", type=int, help="Summarize last N hours (default: today)")
def summary(channel: str | None, hours: int | None):
    """AI summary of today's messages (or last N hours)."""
    from collections import defaultdict

    from ..analyzer import analyze_messages

    db = MessageDB()

    if hours:
        channel_id = db.resolve_channel_id(channel) if channel else None
        msgs = db.get_recent(channel_id=channel_id, hours=hours)
    else:
        channel_id = db.resolve_channel_id(channel) if channel else None
        msgs = db.get_today(channel_id=channel_id)

    db.close()

    if not msgs:
        console.print("[yellow]No messages to summarize.[/yellow]")
        return

    grouped: dict[str, list[dict]] = defaultdict(list)
    for m in msgs:
        grouped[m.get("channel_name") or "Unknown"].append(m)

    console.print(f"[dim]Summarizing {len(msgs)} messages from {len(grouped)} channels...[/dim]")

    parts = []
    for ch_name, ch_msgs in sorted(grouped.items(), key=lambda x: -len(x[1])):
        parts.append(f"\n### #{ch_name} ({len(ch_msgs)} 条)")
        for m in ch_msgs:
            ts = (m.get("timestamp") or "")[:19]
            sender = m.get("sender_name") or "Unknown"
            content = m.get("content") or ""
            parts.append(f"[{ts}] {sender}: {content}")

    combined_prompt = f"""请总结以下 {len(grouped)} 个 Discord 频道的消息：

1. **每个频道的核心话题** — 简明扼要
2. **值得关注的信息** — 有价值的链接、项目、工具、观点
3. **整体概览** — 今天社区的整体讨论趋势

请用中文回答，按频道分别总结，保持简洁有深度。"""

    result = analyze_messages(msgs, prompt=combined_prompt)
    console.print(result)
