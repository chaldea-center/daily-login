import asyncio
import os
from pathlib import Path

from src.login import start_login
from src.schemas.config import Config


async def main():
    config = Config.model_validate_json(Path("config.json").read_bytes())
    if not config.users:
        print("No user")
        return
    data_folder = Path(config.data_folder or os.environ.get("DATA_FOLDER") or "data")
    for user in config.users:
        if not user.enabled:
            print(f"account {user.region}-{user.name} disabled, skip")
            continue
        await start_login(user, data_folder)


if __name__ == "__main__":
    asyncio.run(main())
