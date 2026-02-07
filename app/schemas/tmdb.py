from typing import List, Optional, Any
from pydantic import BaseModel

class TMDBBaseItem(BaseModel):
    id: int
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    original_language: Optional[str] = None

class TMDBMovie(TMDBBaseItem):
    title: Optional[str] = None
    original_title: Optional[str] = None
    release_date: Optional[str] = None

class TMDBTV(TMDBBaseItem):
    name: Optional[str] = None
    original_name: Optional[str] = None
    first_air_date: Optional[str] = None

class TMDBSuggestionResponse(BaseModel):
    suggestions: List[str]

class TMDBMovieListResponse(BaseModel):
    total: int
    items: List[TMDBMovie]

class TMDBTVListResponse(BaseModel):
    total: int
    items: List[TMDBTV]
