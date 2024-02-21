from asyncio import sleep
from pathlib import Path
from typing import Callable, cast

import httpx

from fgoapi.fgoapi import FgoApi
from fgoapi.schemas.common import AuthSaveData, Region, UserData
from fgoapi.schemas.entities import UserLoginEntity
from fgoapi.schemas.response import FResponseData

from .logger import logger
from .schemas.config import UserConfig
from .schemas.data import AccountStatData, LoginResultData
from .utils import dump_json, load_json, send_discord_msg


CampaignBonusData_ = dict
UserPresentBoxEntity_ = dict


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
            seq_login_msg = post_process(toplogin.raw_resp.json(), file_saver)
            await agent.home_top()
            return seq_login_msg
        except httpx.HTTPError as e:
            count += 1
            logger.exception("http error")
            await sleep(60)
            continue
    raise Exception(f"Failed after max {max_retry} retries")


def post_process(src_data: dict, file_saver: "FileSaver") -> str:
    save_toplogin(src_data, file_saver.nid_fp("login_top"))
    try:
        resp = FResponseData.model_validate(src_data)
        logger.info(src_data.get("response") or "no response found")

        stat_fp = Path(file_saver.stat_data())
        stat_data = AccountStatData.model_validate_json(stat_fp.read_bytes())

        save_user_entity(stat_data, resp)
        save_login_result(stat_data.loginResult, resp)

        dump_json(stat_data.model_dump(), stat_fp, indent=False)

        userLogin = resp.cache.get_model("userLogin", UserLoginEntity)[0]
        return f"{userLogin.seqLoginCount}/{userLogin.totalLoginCount}"
    except Exception as e:
        logger.exception("post process failed")
        send_discord_msg(f"post process failed: {e}")
        return "failed"


def save_user_entity(account_data: AccountStatData, resp: FResponseData) -> None:
    fields: list[
        tuple[list[dict], str, Callable[[dict], str | int], Callable[[dict], str | int]]
    ] = [
        (
            account_data.userPresentBox,
            "userPresentBox",
            lambda x: x["presentId"],
            lambda x: x["presentId"],
        ),
    ]

    for item_list, key_name, key_getter, sort_key in fields:
        new_items: list[dict] = resp.cache.get(key_name)
        item_map = {key_getter(x): x for x in item_list}
        for item in new_items:
            item_map[key_getter(item)] = dict(item)
        all_items = [item_map[key] for key in sorted(item_map.keys())]
        all_items.sort(key=sort_key)
        before_count, after_count = len(item_list), len(all_items)
        item_list.clear()
        item_list.extend(all_items)
        if after_count != before_count:
            logger.info(
                f"Insert {len(new_items)} {key_name}, "
                f"total {before_count} -> {after_count} ({after_count-before_count} added)"
            )


def save_login_result(login_data: LoginResultData, resp: FResponseData) -> None:
    login_result = resp.get_response("login")
    if not login_result:
        logger.warning("no login result found")
        return

    t0 = resp.cache.serverTime

    def get_t(x: dict, t: int | None) -> int | str:
        return x["updatedAt"] if t is None else t

    fields: list[tuple[list[dict], str, Callable[[dict, int | None], str | int]]] = [
        (login_data.loginMessages, "loginMessages", get_t),
        (login_data.totalLoginBonus, "totalLoginBonus", get_t),
        (
            login_data.loginFortuneBonus,
            "loginFortuneBonus",
            lambda x, t: f"{x['eventId']}_{get_t(x,t)}",
        ),
        (
            login_data.campaignbonus,
            "campaignbonus",
            lambda x, t: f"{x['eventId']}_{x['day']}_{x['name']}_{get_t(x,t)}",
        ),
        (login_data.campaignDirectBonus, "campaignDirectBonus", get_t),
    ]

    for item_list, key_name, key_getter in fields:
        new_items: list[dict] = login_result.success.get(key_name, [])
        item_map = {key_getter(x, None): x for x in item_list}
        for item in new_items:
            item = dict(item)
            item["updatedAt"] = t0
            if (
                key_name == "totalLoginBonus"
                and not item.get("items")
                and not item.get("script")
            ):
                continue
            item_map[key_getter(item, t0)] = item
        all_items = [item_map[key] for key in sorted(item_map.keys())]
        all_items.sort(key=lambda x: x["updatedAt"])
        before_count, after_count = len(item_list), len(all_items)
        item_list.clear()
        item_list.extend(all_items)
        if after_count != before_count:
            logger.info(
                f"Insert {len(new_items)} {key_name}, "
                f"total {before_count} -> {after_count} ({after_count-before_count} added)"
            )


def replace_cache_value(cache: dict, mst: str, key: str, value):
    for changed in ["updated", "deleted", "replaced"]:
        if mst in cache[changed]:
            items = cache[changed][mst]
            for item in items:
                if key in item:
                    item[key] = value


def replace_response_detail(resp: dict, key: str, value, delete=False):
    details: list[dict] = resp.get("response", [])
    if not details:
        return
    for detail in details:
        success: dict = cast(dict, detail).get("success", {})
        if not success:
            continue
        if key in success:
            if delete:
                success.pop(key)
            else:
                success[key] = value


def save_toplogin(new_toplogin: dict, fp: Path):
    from copy import deepcopy

    new_toplogin = deepcopy(new_toplogin)
    new_cache = new_toplogin["cache"]

    # replace_response_detail(new_toplogin, "obfuscatedAccountId", None, delete=True)
    replace_response_detail(new_toplogin, "addFriendPoint", None, delete=True)
    replace_response_detail(new_toplogin, "addFollowFriendPoint", None, delete=True)
    replace_response_detail(new_toplogin, "topAddFriendPointSvt", None, delete=True)
    replace_response_detail(new_toplogin, "topAddFriendPointSvtEQ", None, delete=True)

    replace_cache_value(new_cache, "userSvtLeader", "updatedAt", 0)
    replace_cache_value(new_cache, "userEvent", "updatedAt", 0)
    replace_cache_value(new_cache, "userEvent", "createdAt", 0)

    def get_dump(data: dict):
        data = deepcopy(data)
        cache = data["cache"]
        if "serverTime" in cache:
            cache["serverTime"] = 0

        replace_cache_value(cache, "userLogin", "lastLoginAt", 0)
        return dump_json(data)

    if fp.exists():
        prev_toplogin = load_json(fp)
        if get_dump(prev_toplogin) == get_dump(new_toplogin):
            logger.info("toplogin cache almost same, skip saving")
            return
    dump_json(new_toplogin, fp, indent=False)


class FileSaver:
    def __init__(self, data_folder: str | Path, region: Region, user_id: str) -> None:
        self.root = Path(data_folder).resolve() / f"{region}_{user_id}"
        self.stats = self.root / "_stats"

    def nid_fp(self, nid: str):
        return self.root / nid / f"{nid}.json"

    def save_nid(self, nid: str, data: dict):
        fp = self.nid_fp(nid)
        fp.parent.mkdir(parents=True, exist_ok=True)
        dump_json(data, fp, indent=False)

    def stat_data(self):
        return self.stats / "data.json"
