from typing import Optional

from pydantic import BaseModel


class PirateBayTorrent(BaseModel):
    """海盗湾种子信息"""
    id: str
    name: str
    info_hash: str
    leechers: str
    seeders: str
    size: str
    num_files: str
    username: str
    added: str
    status: str
    category: str
    imdb: Optional[str] = None
    magnet: Optional[str] = None
