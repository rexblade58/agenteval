import pytest

from app import calc_total


def test_no_discount_below_threshold():
    assert calc_total([{"price": 10}, {"price": 20}]) == 30


def test_discount_over_threshold():
    assert calc_total([{"price": 40}, {"price": 20}]) == 54.0


def test_discount_multi_item():
    assert calc_total([{"price": 20}, {"price": 20}, {"price": 20}]) == 54.0
