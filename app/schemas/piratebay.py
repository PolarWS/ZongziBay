from pydantic import BaseModel
from typing import Optional

class PirateBayTorrent(BaseModel):
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
