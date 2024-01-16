from pydantic import BaseModel

from fgoapi.schemas.common import NACountry, Region


class UserConfig(BaseModel):
    name: str | None = None
    enabled: bool = True
    region: Region
    secret: str
    userAgent: str | None = None
    deviceInfo: str | None = None
    country: NACountry | None = None


class Config(BaseModel):
    users: list[UserConfig]
    data_folder: str | None = None
