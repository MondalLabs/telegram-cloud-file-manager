import pytest
from utils.pagination import paginate

def test_paginate_zero_items():
    items = []
    page = paginate(items, page=1, per_page=10)
    assert page.items == []
    assert page.page == 1
    assert page.total_pages == 1
    assert page.total_items == 0
    assert not page.has_prev
    assert not page.has_next

def test_paginate_normal():
    items = list(range(25))
    page = paginate(items, page=2, per_page=10)
    assert page.items == list(range(10, 20))
    assert page.page == 2
    assert page.total_pages == 3
    assert page.total_items == 25
    assert page.has_prev
    assert page.has_next
    assert page.prev_page == 1
    assert page.next_page == 3

def test_paginate_out_of_bounds():
    items = list(range(25))
    # Negative page defaults to page 1
    page1 = paginate(items, page=-5, per_page=10)
    assert page1.page == 1
    assert page1.items == list(range(10))
    assert page1.has_next
    assert not page1.has_prev

    # Large page defaults to total_pages (3)
    page3 = paginate(items, page=100, per_page=10)
    assert page3.page == 3
    assert page3.items == list(range(20, 25))
    assert not page3.has_next
    assert page3.has_prev
