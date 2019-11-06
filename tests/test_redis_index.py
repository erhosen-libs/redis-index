import pytest

from redis_index import __version__
from redis_index import RedisFiltering, BaseFilter


class RegionFilter(BaseFilter):

    def get_ids(self, region, **kwargs):
        return [1, 2, 3, 4, 5, 6, 7, 8, 9]


class CurrencyFilter(BaseFilter):

    def get_ids(self, currency, **kwargs):
        return [4, 5, 6]


@pytest.mark.parametrize(
    'search_ids, expected',
    [
        ([1, 2, 3, 4, 5, 6, 7, 8, 9], [4, 5, 6]),
        ([5, 6, 7], [5, 6]),
        ([1, 2, 3], [])
    ]
)
def test_one_filter(redis_connection, search_ids, expected):
    filtering = RedisFiltering(redis_connection)
    result = filtering.filter(search_ids, [CurrencyFilter("USD")])
    assert sorted(result) == sorted(expected)


@pytest.mark.parametrize(
    'search_ids, expected',
    [
        ([1, 2, 3, 4, 5, 6, 7, 8, 9], [4, 5, 6]),
        ([5, 6, 7], [5, 6]),
        ([1, 2, 3], [])
    ]
)
def test_multiple_filters(redis_connection, search_ids, expected):
    filtering = RedisFiltering(redis_connection)
    result = filtering.filter(search_ids, [RegionFilter("US"), CurrencyFilter("USD")])
    assert sorted(result) == sorted(expected)


def test_version():
    assert __version__ == '0.1.0'
