from asyncio import sleep
from pathlib import Path

import httpx
from fgoapi.fgoapi import FgoApi
from fgoapi.schemas.common import AuthSaveData, Region, UserData

from .schemas.config import UserConfig
from .utils import dump_json, load_json


async def start_login(
    user_config: UserConfig, data_folder: Path, max_retry: int = 3
) -> str:
    auth = AuthSaveData.parse_secret(user_config.secret)
    user = UserData(
        region=user_config.region,
        auth=auth,
        userAgent=user_config.userAgent,
        deviceInfo=user_config.deviceInfo,
        country=user_config.country,
    )
    file_saver = FileSaver(data_folder, user_config.region, auth.userId)
    agent = FgoApi(user)
    count = 0
    while count < max_retry:
        try:
            await agent.gamedata_top()
            toplogin = await agent.login_top()
            await agent.home_top()
            assert toplogin.data
            toplogin.raw_resp.text
            file_saver.save_nid("login_top", toplogin.raw_resp.json())

            save_presents(
                toplogin.data.cache["replaced"]["userPresentBox"],
                file_saver.stats / "userPresentBox.json",
            )

            userLogin = toplogin.data.cache["updated"]["userLogin"][0]
            seqLoginCount = userLogin["seqLoginCount"]
            totalLoginCount = userLogin["totalLoginCount"]
            return f"Seq:{seqLoginCount} Total:{totalLoginCount}"
        except httpx.HTTPError as e:
            count += 1
            await sleep(5)
            continue
    raise Exception(f"Failed after max {max_retry} retries")


def save_presents(new_presents: list[dict], fp: Path):
    key = "presentId"
    if fp.exists():
        present_dict: dict[int, dict] = {
            present[key]: present for present in load_json(fp)
        }
    else:
        present_dict = {}
    before_count = len(present_dict)
    for present in new_presents:
        present_dict[present[key]] = present
    presents = list(present_dict.values())
    presents.sort(key=lambda x: x[key])
    after_count = len(present_dict)
    print(
        f"Inserted {len(new_presents)} presents, total {after_count} presents ({after_count-before_count} added)"
    )
    dump_json(presents, fp, indent=True)


class FileSaver:
    def __init__(self, data_folder: str | Path, region: Region, user_id: str) -> None:
        self.root = Path(data_folder).resolve() / f"{region}_{user_id}"
        self.stats = self.root / "_stats"

    def save_nid(self, nid: str, data: dict):
        fp = self.root / nid / f"{nid}.json"
        fp.parent.mkdir(parents=True, exist_ok=True)
        dump_json(data, fp, indent=True)
