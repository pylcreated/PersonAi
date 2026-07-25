from __future__ import annotations

import logging

from personal_agent.bootstrap import create_application


def main() -> None:
    """Create and start the local application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    create_application().run()


if __name__ == "__main__":
    main()
