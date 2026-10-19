from pydantic import BaseModel, Field

from app.common.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
