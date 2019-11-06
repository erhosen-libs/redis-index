import fakeredis
import pytest


@pytest.fixture(scope="function", autouse=True)
def redis_connection():
    search_redis_client = fakeredis.FakeRedis(decode_responses=True)  # strings instead b''
    yield search_redis_client
    search_redis_client.flushall()