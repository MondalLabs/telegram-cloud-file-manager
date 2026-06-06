import pytest
from utils.callback_data import decode

def test_decode_typical_callback():
    """Test decoding a typical action:id:page string."""
    assert decode("nav:6a08ce62ae36ee491a35cd99:2") == ("nav", "6a08ce62ae36ee491a35cd99", "2")

def test_decode_single_action():
    """Test decoding a single action without arguments."""
    assert decode("cancel") == ("cancel",)

def test_decode_empty_string():
    """Test decoding an empty string."""
    assert decode("") == ("",)

def test_decode_multiple_separators():
    """Test decoding a string with multiple consecutive separators."""
    assert decode("action::arg2") == ("action", "", "arg2")

def test_decode_many_parts():
    """Test decoding a string with many arguments."""
    assert decode("action:arg1:arg2:arg3:arg4") == ("action", "arg1", "arg2", "arg3", "arg4")
