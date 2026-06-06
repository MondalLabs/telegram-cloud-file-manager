import unittest
from utils.pagination import paginate, Page

class TestPagination(unittest.TestCase):
    def test_empty_list(self):
        items = []
        page = paginate(items, page=1, per_page=15)

        self.assertEqual(page.items, [])
        self.assertEqual(page.page, 1)
        self.assertEqual(page.total_pages, 1)
        self.assertEqual(page.total_items, 0)
        self.assertFalse(page.has_prev)
        self.assertFalse(page.has_next)
        self.assertEqual(page.prev_page, 1)
        self.assertEqual(page.next_page, 1)

    def test_single_page(self):
        items = [1, 2, 3, 4, 5]
        page = paginate(items, page=1, per_page=15)

        self.assertEqual(page.items, [1, 2, 3, 4, 5])
        self.assertEqual(page.page, 1)
        self.assertEqual(page.total_pages, 1)
        self.assertEqual(page.total_items, 5)
        self.assertFalse(page.has_prev)
        self.assertFalse(page.has_next)

    def test_multiple_pages_first_page(self):
        items = list(range(1, 35)) # 34 items
        page = paginate(items, page=1, per_page=10)

        self.assertEqual(page.items, list(range(1, 11)))
        self.assertEqual(page.page, 1)
        self.assertEqual(page.total_pages, 4)
        self.assertEqual(page.total_items, 34)
        self.assertFalse(page.has_prev)
        self.assertTrue(page.has_next)
        self.assertEqual(page.prev_page, 1)
        self.assertEqual(page.next_page, 2)

    def test_multiple_pages_middle_page(self):
        items = list(range(1, 35))
        page = paginate(items, page=2, per_page=10)

        self.assertEqual(page.items, list(range(11, 21)))
        self.assertEqual(page.page, 2)
        self.assertEqual(page.total_pages, 4)
        self.assertEqual(page.total_items, 34)
        self.assertTrue(page.has_prev)
        self.assertTrue(page.has_next)
        self.assertEqual(page.prev_page, 1)
        self.assertEqual(page.next_page, 3)

    def test_multiple_pages_last_page(self):
        items = list(range(1, 35))
        page = paginate(items, page=4, per_page=10)

        self.assertEqual(page.items, list(range(31, 35)))
        self.assertEqual(page.page, 4)
        self.assertEqual(page.total_pages, 4)
        self.assertEqual(page.total_items, 34)
        self.assertTrue(page.has_prev)
        self.assertFalse(page.has_next)
        self.assertEqual(page.prev_page, 3)
        self.assertEqual(page.next_page, 4)

    def test_page_bounds_negative(self):
        items = list(range(1, 35))
        page = paginate(items, page=-5, per_page=10)

        # Should clamp to page 1
        self.assertEqual(page.page, 1)
        self.assertEqual(page.items, list(range(1, 11)))

    def test_page_bounds_zero(self):
        items = list(range(1, 35))
        page = paginate(items, page=0, per_page=10)

        # Should clamp to page 1
        self.assertEqual(page.page, 1)
        self.assertEqual(page.items, list(range(1, 11)))

    def test_page_bounds_too_high(self):
        items = list(range(1, 35))
        page = paginate(items, page=100, per_page=10)

        # Should clamp to total_pages (4)
        self.assertEqual(page.page, 4)
        self.assertEqual(page.items, list(range(31, 35)))

    def test_page_repr(self):
        items = [1, 2, 3]
        page = paginate(items, page=1, per_page=10)
        expected_repr = "<Page 1/1 items=3/3>"
        self.assertEqual(repr(page), expected_repr)

if __name__ == "__main__":
    unittest.main()
