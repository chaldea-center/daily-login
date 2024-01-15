from fgoapi.schemas.common import NACountry, Region
from pydantic import BaseModel


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
