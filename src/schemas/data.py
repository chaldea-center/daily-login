from typing import Any

from typing_extensions import TypedDict

from fgoapi.schemas.common import BaseModelExtra, Region


class AccountInfo(BaseModelExtra):
    userId: int
    friendCode: str
    region: Region
    name: str
    start: int
    startSeqLoginCount: int
    startTotalLoginCount: int


class CampaignBonusDataX(TypedDict):
    name: str
    detail: str
    addDetail: str
    isDeemedLogin: bool
    items: list[dict]  # name: str, num: int
    script: dict[str, Any]
    eventId: int
    day: int
    updatedAt: int | None  # manually added, use login time


class UserPresentBoxEntityX(TypedDict):
    receiveUserId: int
    presentId: int
    messageRefType: int
    messageId: int
    message: str
    fromType: int
    giftType: int
    objectId: int
    num: int
    flag: int
    createdAt: int


class AccountStatData(BaseModelExtra):
    info: AccountInfo
    userPresentBox: list[dict]
    campaignbonus: list[dict]
