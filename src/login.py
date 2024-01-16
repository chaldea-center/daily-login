from asyncio import sleep
from pathlib import Path

import httpx

from fgoapi.fgoapi import FgoApi
from fgoapi.schemas.common import AuthSaveData, Region, UserData
from fgoapi.schemas.entities import UserLoginEntity

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
            assert toplogin.data
            save_toplogin(toplogin.raw_resp.json(), file_saver.nid_fp("login_top"))

            save_presents(
                toplogin.data.cache.get("userPresentBox"),
                file_saver.stats / "userPresentBox.json",
            )

            userLogin = toplogin.data.cache.get_model("userLogin", UserLoginEntity)[0]

            await agent.home_top()

            return f"Seq:{userLogin.seqLoginCount} Total:{userLogin.totalLoginCount}"
        except httpx.HTTPError as e:
            count += 1
            print("http error", e)
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


def save_toplogin(new_toplogin: dict, fp: Path):
    from copy import deepcopy

    def get_dump(data: dict, idx: int):
        data = deepcopy(data["cache"])
        if "serverTime" in data:
            data["serverTime"] = 0

        def replace_value(mst: str, key: str, value):
            for changed in ["updated", "replaced"]:
                if mst in data[changed]:
                    items = data[changed][mst]
                    for item in items:
                        if key in item:
                            item[key] = value

        replace_value("userLogin", "lastLoginAt", 0)
        replace_value("userSvtLeader", "updatedAt", 0)
        replace_value("userEvent", "updatedAt", 0)
        replace_value("userEvent", "createdAt", 0)
        return dump_json(data, f"{idx}.json")

    if fp.exists():
        prev_toplogin = load_json(fp)
        if get_dump(prev_toplogin, 1) == get_dump(new_toplogin, 2):
            print("toplogin cache almost same, skip saving")
            return
    dump_json(new_toplogin, fp, indent=True)


class FileSaver:
    def __init__(self, data_folder: str | Path, region: Region, user_id: str) -> None:
        self.root = Path(data_folder).resolve() / f"{region}_{user_id}"
        self.stats = self.root / "_stats"

    def nid_fp(self, nid: str):
        return self.root / nid / f"{nid}.json"

    def save_nid(self, nid: str, data: dict):
        fp = self.nid_fp(nid)
        fp.parent.mkdir(parents=True, exist_ok=True)
        dump_json(data, fp, indent=True)
