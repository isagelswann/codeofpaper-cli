"""Manage API key authentication."""

from typing import Optional

import typer

from codeofpaper_cli import config


def auth(
    action: str = typer.Argument(..., help="Action: setup, status, or clear."),
    key: Optional[str] = typer.Argument(None, help="API key (for setup action)."),
) -> None:
    """Manage API key authentication (setup, status, clear)."""
    action = action.lower()

    if action == "setup":
        if not key:
            typer.echo("Error: API key required for setup. Usage: codeofpaper auth setup <KEY>")
            raise typer.Exit(code=1)
        config.set_key("api_key", key)
        typer.echo(f"API key saved to {config.get_config_path()}")
        raise typer.Exit(code=0)

    if action == "status":
        cfg = config.load_config()
        stored_key = cfg.get("api_key")
        path = config.get_config_path()
        typer.echo(f"Config file: {path}")
        if stored_key:
            masked = stored_key[:8] + "..." + stored_key[-4:] if len(stored_key) > 12 else "***"
            typer.echo(f"API key:     {masked}")
        else:
            typer.echo("API key:     (not set)")
        typer.echo(f"API URL:     {cfg.get('api_url', config.DEFAULTS['api_url'])}")
        typer.echo(f"Format:      {cfg.get('default_format', config.DEFAULTS['default_format'])}")
        raise typer.Exit(code=0)

    if action == "clear":
        config.delete_key("api_key")
        typer.echo("API key cleared.")
        raise typer.Exit(code=0)

    typer.echo(f"Unknown action: {action}. Use: setup, status, or clear.")
    raise typer.Exit(code=1)
