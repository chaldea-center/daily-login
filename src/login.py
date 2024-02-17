from asyncio import sleep
from pathlib import Path
from typing import cast

import httpx

from fgoapi.fgoapi import FgoApi
from fgoapi.schemas.common import AuthSaveData, Region, UserData
from fgoapi.schemas.entities import UserLoginEntity
from fgoapi.schemas.response import FResponseData

from .logger import logger
from .schemas.config import UserConfig
from .schemas.data import AccountStatData
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
            await sleep(5)
            continue
    raise Exception(f"Failed after max {max_retry} retries")


def post_process(src_data: dict, file_saver: "FileSaver") -> str:
    save_toplogin(src_data, file_saver.nid_fp("login_top"))
    try:
        resp = FResponseData.model_validate(src_data)
        logger.info(src_data.get("response") or "no response found")

        stat_fp = Path(file_saver.stat_data())
        stat_data = AccountStatData.model_validate_json(stat_fp.read_bytes())

        stat_data.userPresentBox = save_presents(stat_data.userPresentBox, resp)
        stat_data.campaignbonus = save_campaignbonus(stat_data.campaignbonus, resp)

        dump_json(stat_data.model_dump(), stat_fp, indent=False)

        userLogin = resp.cache.get_model("userLogin", UserLoginEntity)[0]
        return f"{userLogin.seqLoginCount}/{userLogin.totalLoginCount}"
    except Exception as e:
        logger.exception("post process failed")
        send_discord_msg(f"post process failed: {e}")
        return "failed"


def save_presents(
    all_presents: list[UserPresentBoxEntity_], resp: FResponseData
) -> list[UserPresentBoxEntity_]:
    key = "presentId"
    present_dict: dict[int, UserPresentBoxEntity_] = {
        present[key]: present for present in all_presents
    }
    before_count = len(present_dict)

    cur_presents = resp.cache.get("userPresentBox")
    for present in cur_presents:
        present_dict[present[key]] = present
    presents = list(present_dict.values())
    presents.sort(key=lambda x: x[key])
    after_count = len(present_dict)
    logger.info(
        f"Inserted {len(cur_presents)} presents, total {after_count} presents ({after_count-before_count} added)"
    )
    return presents


def save_campaignbonus(
    all_campaigns: list[CampaignBonusData_], resp: FResponseData
) -> list[CampaignBonusData_]:
    def get_campaign_key(campaign: CampaignBonusData_):
        return f"{campaign['eventId']}_{campaign['day']}_{campaign['name']}"

    login_result = resp.get_response("login")
    if not login_result:
        logger.warning("no login result found")
        return all_campaigns
    cur_campaigns: list[CampaignBonusData_] = login_result.success.get(
        "campaignbonus", []
    )

    if not cur_campaigns:
        logger.info("no new campaign bonus")
        return all_campaigns
    campaign_dict: dict[str, CampaignBonusData_] = {
        get_campaign_key(campaign): campaign for campaign in all_campaigns
    }
    before_count = len(campaign_dict)
    for campaign in cur_campaigns or []:
        campaign["updatedAt"] = resp.cache.serverTime
        campaign_dict[get_campaign_key(campaign)] = campaign
    campaigns = list(campaign_dict.values())
    campaigns.sort(key=lambda x: (x.get("updatedAt", 0), x["eventId"], x["day"]))
    after_count = len(campaign_dict)
    logger.info(
        f"Inserted {len(cur_campaigns)} campaigns, total {after_count} presents ({after_count-before_count} added)"
    )
    return campaigns


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
