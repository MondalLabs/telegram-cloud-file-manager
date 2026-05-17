"""
utils/pagination.py
─────────────────────────────────────────────────────────────────────────────
Generic paginator used across folder listings, user listings, etc.

All page numbers are 1-indexed (as displayed to users).
"""

from __future__ import annotations

from typing import TypeVar, Generic

T = TypeVar("T")


class Page(Generic[T]):
    """Result container for a single page of items."""

    def __init__(
        self,
        items: list[T],
        page: int,
        total_pages: int,
        total_items: int,
    ):
        self.items = items
        self.page = page
        self.total_pages = total_pages
        self.total_items = total_items

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def prev_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.total_pages, self.page + 1)

    def __repr__(self) -> str:
        return (
            f"<Page {self.page}/{self.total_pages} "
            f"items={len(self.items)}/{self.total_items}>"
        )


def paginate(items: list[T], page: int, per_page: int) -> Page[T]:
    """
    Slice a list into a Page object.

    Args:
        items:    The full list to paginate.
        page:     1-indexed current page number.
        per_page: Items per page (from settings.items_per_page = 15).

    Returns:
        A Page[T] with the sliced items and navigation metadata.

    The page number is clamped to [1, total_pages] so out-of-range
    callback_data values never cause IndexError.
    """
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)

    # Clamp to valid range
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    return Page(
        items=page_items,
        page=page,
        total_pages=total_pages,
        total_items=total_items,
    )
