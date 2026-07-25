from __future__ import annotations


class LocalChannel:
    """Simple local console messaging channel."""

    def send_message(self, to: str, subject: str, body: str) -> None:
        """Print a bot message to the local console."""
        print("\n=== BOT MESSAGE ===")
        if subject:
            print(f"主题: {subject}")
        print(body)
        print("=== END MESSAGE ===\n")
