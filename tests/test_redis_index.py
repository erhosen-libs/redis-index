from unittest import mock

import pytest
from redis_index import BaseFilter, RedisFiltering, RedisIndex, __version__


class RegionFilter(BaseFilter):
    def get_ids(self, region, **kwargs):
        return [1, 2, 3, 4, 5, 6, 7, 8, 9]


class CurrencyFilter(BaseFilter):
    def get_ids(self, currency, **kwargs):
        return [4, 5, 6]


class EmptyFiler(BaseFilter):
    def get_ids(self, **kwargs):
        return []


@pytest.mark.parametrize(
    "search_ids, expected", [([1, 2, 3, 4, 5, 6, 7, 8, 9], [4, 5, 6]), ([5, 6, 7], [5, 6]), ([1, 2, 3], [])]
)
def test_one_filter(redis_connection, search_ids, expected):
    filtering = RedisFiltering(redis_connection)
    result = filtering.filter(search_ids, [CurrencyFilter("USD")])
    assert sorted(result) == sorted(expected)


@pytest.mark.parametrize(
    "search_ids, expected", [([1, 2, 3, 4, 5, 6, 7, 8, 9], [4, 5, 6]), ([5, 6, 7], [5, 6]), ([1, 2, 3], [])]
)
def test_multiple_filters(redis_connection, statsd_client, search_ids, expected):
    filtering = RedisFiltering(redis_connection, statsd_client)
    result = filtering.filter(search_ids, [RegionFilter("US"), CurrencyFilter("USD")])
    assert sorted(result) == sorted(expected)
    assert len(statsd_client.mock_calls) == 6


def test_empty_filter(redis_connection):
    filtering = RedisFiltering(redis_connection)
    result = filtering.filter([1, 2, 3], [EmptyFiler()])
    assert not result


def test_already_warmed_filter(redis_connection):
    filtering = RedisFiltering(redis_connection)
    region_filter_us = RegionFilter("US")
    filtering.warm_filters([region_filter_us])
    result = filtering.filter([1, 2, 3], [region_filter_us])
    assert sorted(result) == [1, 2, 3]


@pytest.mark.parametrize(
    "db_ids",
    [
        [1, 2, 3, 4, 5, 6, 7, 8],  # remove one element
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # add one element
        [2, 3, 4, 5, 6, 7, 8, 9, 10],  # add and remove one element
    ],
)
def test_warm_filters(redis_connection, statsd_client, db_ids):
    filtering = RedisFiltering(redis_connection, statsd_client)
    region_filter_us = RegionFilter("US")
    filtering.warm_filters([region_filter_us])
    with mock.patch("redis_index.redis_index.BaseFilter.ids", new_callable=mock.PropertyMock) as _mocked_ids:
        _mocked_ids.return_value = db_ids
        filtering.warm_filters([region_filter_us])

    hot_filter = RedisIndex(region_filter_us, redis_connection)
    assert set(hot_filter.get_hot_ids()) == {str(_id) for _id in db_ids}
    assert len(statsd_client.mock_calls) == 4


def test_version():
    assert __version__ == "0.1.0"
