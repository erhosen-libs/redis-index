from unittest import mock

import fakeredis
import pytest


@pytest.fixture(scope="function", autouse=True)
def redis_connection():
    search_redis_client = fakeredis.FakeRedis(decode_responses=True)  # strings instead b''
    yield search_redis_client
    search_redis_client.flushall()


@pytest.fixture(scope="function", autouse=True)
def statsd_client():
    class FakeStatsdClient:
        def gauge(self, *args, **kwargs):
            pass

        def incr(self, *args, **kwargs):
            pass

    return mock.Mock(return_value=FakeStatsdClient())
