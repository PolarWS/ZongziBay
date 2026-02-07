from typing import List, Optional
from pydantic import BaseModel

class MagnetFile(BaseModel):
    name: str
    path: str
    size: int

class MagnetParseResponse(BaseModel):
    files: List[MagnetFile]

class MagnetRequest(BaseModel):
    magnet_link: str

class MagnetDownloadRequest(BaseModel):
    magnet_link: str
    save_path: Optional[str] = None