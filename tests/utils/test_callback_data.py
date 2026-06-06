import pytest
from utils.callback_data import encode

def test_encode_happy_path():
    assert encode("nav", "6a08ce62ae36ee491a35cd99", 2) == "nav:6a08ce62ae36ee491a35cd99:2"

def test_encode_limit():
    # 64 bytes is the limit
    action = "nav"
    # Action = 3, separating colon = 1. We have 60 bytes left for args
    long_arg = "a" * 60
    assert encode(action, long_arg) == f"nav:{long_arg}"

def test_encode_exceeds_limit():
    action = "nav"
    long_arg = "a" * 61
    with pytest.raises(AssertionError, match="Callback data exceeds 64 bytes"):
        encode(action, long_arg)

def test_encode_no_args():
    assert encode("cancel") == "cancel"

def test_encode_multiple_args():
    assert encode("test", 1, 2, "3", 4) == "test:1:2:3:4"

def test_encode_unicode():
    assert encode("nav", "你好") == "nav:你好"
