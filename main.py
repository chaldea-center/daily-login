import asyncio
import datetime
import os
from pathlib import Path

from src.login import start_login
from src.schemas.config import config


async def main():
    if not config.users:
        print("No user")
        return
    data_folder = Path(config.data_folder or os.environ.get("DATA_FOLDER") or "data")
    jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    commit_msgs: list[str] = []
    for user in config.users:
        if not user.enabled:
            print(f"account {user.region}-{user.name} disabled, skip")
            continue
        msg = await start_login(user, data_folder)
        commit_msgs.append(msg)
    commit_msg = ", ".join(commit_msgs)
    commit_msg = "[JST " + jst.strftime("%Y-%m-%d %H:%M") + "] " + commit_msg
    Path(__file__).parent.joinpath("commit-msg.txt").write_text(commit_msg.strip())


if __name__ == "__main__":
    asyncio.run(main())
