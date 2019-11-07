import typing as t
from abc import ABC, abstractmethod

import inflection as inflection
from hot_redis import HotClient, Set
from statsd import StatsClient

__all__ = ("BaseFilter", "RedisFiltering", "RedisIndex")


def cast_to_str(lst: t.List) -> t.Set[str]:
    """
    Returns a set of strings, that can be compared with hot_redis.Set
    """
    return set(map(str, lst))


class BaseFilter(ABC):
    def __init__(self, arg: t.Union[str, int, bool] = None, **kwargs):
        self.arg = arg  # must be immutable type to prevent problems with caching
        self.kwargs = kwargs  # helpers, that will not be part of redis key
        super().__init__()

    @property
    def name(self) -> str:
        class_name = inflection.underscore(self.__class__.__name__)
        if self.arg:
            return f"{class_name}_{self.arg}"
        return class_name

    @property
    def ids(self) -> t.List[int]:
        if self.arg:
            return self.get_ids(self.arg, **self.kwargs)
        return self.get_ids(**self.kwargs)

    @abstractmethod
    def get_ids(self, *args, **kwargs) -> t.List[int]:
        raise NotImplementedError


class RedisIndex:
    def __init__(self, _filter: BaseFilter, redis_client: HotClient, statsd_client: StatsClient = None):
        self.filter = _filter
        self.redis_client = redis_client
        self.statsd_client = statsd_client
        # Initialize connection to redis, but don't fetch the value by _redis_key
        self._hot_ids = Set(key=self._redis_key, client=self.redis_client)

    @property
    def _redis_key(self) -> str:
        """
        The way it will be stored in Redis
        """
        return f"idx_{self.filter.name}"

    def warm(self, check_consistency: bool = True) -> None:
        # Get fresh db_ids from database
        db_ids = cast_to_str(self.filter.ids)
        if not db_ids:
            return

        # Are hot_ids already exists by that _redis_key?
        if self.is_warmed:
            new_ids = db_ids - self._hot_ids  # find such ids, that in db, but not in cache
            outdated_ids = self._hot_ids - db_ids  # find ids, that in cache, but already removed from db
            if outdated_ids:
                self._hot_ids.srem(*outdated_ids)  # remove outdated_ids from cache
            if new_ids:
                self._hot_ids.sadd(*new_ids)  # add fresh ids to cache
        else:
            # hot_ids is empty, and we initialize it with fresh db_ids
            self._hot_ids.value = db_ids
            new_ids = db_ids
            outdated_ids = []

        if check_consistency:
            assert not self._hot_ids ^ db_ids, "symmetric_difference is not empty!"

        self.send_metrics(len(new_ids), len(outdated_ids))

    def get_hot_ids(self) -> Set:
        """
        Returns the actual hot_redis.Set instance.
        """
        return self._hot_ids

    @property
    def is_warmed(self) -> bool:
        """
        Is hot_ids empty in Redis Cache?
        bool() actually calls `SCARD` Redis operation
        https://redis.io/commands/scard
        """
        return bool(self._hot_ids)

    def send_metrics(self, new_ids_count: int, outdated_ids_count: int) -> None:
        if not self.statsd_client:
            return None
        name = self.filter.name
        self.statsd_client.incr(f"redis_index.filtering.warm,action=add,filter={name}", count=new_ids_count)
        self.statsd_client.incr(
            f"redis_index.filtering.warm,action=remove,filter={name}", count=outdated_ids_count
        )


class RedisFiltering:
    def __init__(self, redis_client: HotClient, statsd_client: StatsClient = None):
        self.redis_client = redis_client
        self.statsd_client = statsd_client

    def send_metrics(self, state: str, filters: t.List[BaseFilter], value: int) -> None:
        """
        Sends metrics to statsd if `statsd_client` has been provided.
        """
        if not self.statsd_client:
            return
        filters_metric = "/".join(_filter.name for _filter in filters)
        self.statsd_client.gauge(
            stat=f"redis_index.filtering.io,state={state},filters={filters_metric}", value=value
        )

    def filter(self, search_ids: t.List[int], filters: t.List[BaseFilter]) -> t.List[int]:
        """
        Intersects provided search_ids with bunch of precalculated filters.
        """
        self.send_metrics("in", filters, len(search_ids))

        # Create Redis `Set` with random key, and fill it with search_ids.
        hot_search_ids = Set(initial=search_ids, client=self.redis_client)

        hot_filters = []
        # Initialize and warm (if necessary) all appropriate filters
        for _filter in filters:
            filter_index = RedisIndex(_filter, self.redis_client, self.statsd_client)
            if not filter_index.is_warmed:
                filter_index.warm(check_consistency=False)

            # Fill filters list with real _filter.hot_ids `Set`
            hot_filters.append(filter_index.get_hot_ids())

        # Intersect hot_search_ids `Set` with other hot_filters `Set`s
        filtered_ids = hot_search_ids.intersection(*hot_filters)
        hot_search_ids.clear()

        self.send_metrics("out", filters, len(filtered_ids))
        # Return result in appropriate format
        return list(map(int, filtered_ids))

    def warm_filters(self, filters: t.List[BaseFilter]) -> None:
        for _filter in filters:
            filter_index = RedisIndex(_filter, self.redis_client, self.statsd_client)
            filter_index.warm()
