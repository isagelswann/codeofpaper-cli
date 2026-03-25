"""Exit code mapping for CLI commands.

Agents parse exit codes programmatically. These are stable and documented.

| Code | Meaning                      | Agent action              |
|------|------------------------------|---------------------------|
| 0    | Success                      | Parse stdout              |
| 1    | General/unknown error        | Log and report            |
| 2    | Connection/network error     | Retry with backoff        |
| 3    | Not found (404)              | Skip or try different ID  |
| 4    | Rate limited (429)           | Wait and retry            |
| 5    | Auth required/invalid (401/403) | Run `codeofpaper auth setup` |
"""

SUCCESS = 0
GENERAL_ERROR = 1
CONNECTION_ERROR = 2
NOT_FOUND = 3
RATE_LIMITED = 4
AUTH_ERROR = 5

# HTTP status code → CLI exit code
HTTP_STATUS_MAP: dict[int, int] = {
    401: AUTH_ERROR,
    403: AUTH_ERROR,
    404: NOT_FOUND,
    429: RATE_LIMITED,
}


def exit_code_from_status(status_code: int) -> int:
    """Map an HTTP status code to a CLI exit code."""
    if 200 <= status_code < 300:
        return SUCCESS
    return HTTP_STATUS_MAP.get(status_code, GENERAL_ERROR)


# Human-readable descriptions for error messages
EXIT_CODE_HINTS: dict[int, str] = {
    CONNECTION_ERROR: "Check your network connection or try again later.",
    NOT_FOUND: "The requested resource was not found. Check the ID and try again.",
    RATE_LIMITED: "Rate limited. Wait a moment and retry.",
    AUTH_ERROR: "Authentication failed. Run 'codeofpaper auth setup' to configure your API key.",
}
