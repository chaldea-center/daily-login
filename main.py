import asyncio
import os
from datetime import datetime
from pathlib import Path

from src.login import start_login
from src.schemas.config import Config


async def main():
    config = Config.model_validate_json(Path("config.json").read_bytes())
    if not config.users:
        print("No user")
        return
    data_folder = Path(config.data_folder or os.environ.get("DATA_FOLDER") or "data")
    commit_msgs:list[str]=[datetime.now().strftime("%Y-%m-%d %H:%M")]
    for user in config.users:
        if not user.enabled:
            print(f"account {user.region}-{user.name} disabled, skip")
            continue
        msg = await start_login(user, data_folder)
        commit_msgs.append(msg)
    Path(__file__).parent.joinpath('commit-msg.txt').write_text(" / ".join(commit_msgs))

if __name__ == "__main__":
    asyncio.run(main())
