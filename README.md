# Redis-index: Inverted Index using efficient Redis set

Redis-index helps to delegate part of the work from database to cache.
It is useful for highload projects, with complex serach logic underneath the hood.

[![Build Status](https://github.com/ErhoSen/redis-index/workflows/Build/badge.svg)](https://github.com/ErhoSen/redis-index/actions?query=workflow:Build)
[![codecov](https://codecov.io/gh/ErhoSen/redis-index/branch/master/graph/badge.svg)](https://codecov.io/gh/ErhoSen/redis-index)
![License](https://img.shields.io/pypi/pyversions/redis-index.svg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI](https://img.shields.io/github/license/erhosen/redis-index.svg)](https://pypi.org/project/redis-index/)

## Introduction

Suppose you have to implement a service that will fetch data for a given set of filters.

```http
GET /api/companies?region=US&currency=USD&search_ids=233,816,266,...
```

Filters may require a significant costs for the database: each of them involves joining multiple tables. By writing a solution on raw SQL, we have a risk of stumbling into database performance.

Such "heavy" queries can be precalculated, and put into redis SET.
We can intersect the resulting SETs with each other, thereby greatly simplifying our SQL.

```python
search_ids = {233, 816, 266, ...}
us_companies_ids = {266, 112, 643, ...}
usd_companies_ids = {816, 54, 8395, ...}

filtered_ids = search_ids & us_companies_ids & usd_companies_ids  # intersection
...
"SELECT * from companies whrere id in {filtered_ids}"
```

But getting such precalculated SETS from Redis to Python memory could be another bottleneck:
filters can be really large, and we don't want to transfer a lot of data between servers.

The solution is intersect these SETs directly in redis.
This is exactly what redis-index library does.

## Installation

Use `pip` to install `redis-index`.

```bash
pip install redis-index
```

## Usage

1) Declare your filters. They must inherit BaseFilter class.

```python
from redis_index import BaseFilter

class RegionFilter(BaseFilter):

    def get_ids(self, region, **kwargs) -> List[int]:
        """
        get_ids should return a precalculated list of ints.
        """
        with psycopg2.connect(...) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM companies WREHE region = %s', (region, ))
                return cursor.fetchall()

class CurrencyFilter(BaseFilter):

    def get_ids(self, currency, **kwargs):
        with psycopg2.connect(...) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM companies WREHE currency = %s', (currency, ))
                return cursor.fetchall()
```

2) Initialize Filtering object

```python
from redis_index import RedisFiltering
from hot_redis import HotClient

redis_clent = HotClient(host="localhost", port=6379)
filtering = RedisFiltering(redis_clent)
```

3) Now you can use `filtering` as a singleton in your project.
Simply call `filter()` method with specific filters, and your `search_ids`

```python
company_ids = request.GET["company_ids"]  # input list
result = filtering.filter(search_ids, [RegionFilter("US"), CurrencyFilter("USD")])
```

The result will be a list, that contains only ids, that are both satisfying RegionFilter and CurrencyFilter.

## How to warm the cache?

You can warm up the cache in various ways, for example, using the cron command
```crontab
*/5  *   *   *   *   python warm_filters
```

Inside such a command, you can use specific method `warm_filters`

```python
result = filtering.filter(search_ids, [RegionFilter("US"), CurrencyFilter("USD")])
```

Or directly RedisIndex class
```python
for _filter in [RegionFilter("US"), CurrencyFilter("USD")]:
    filter_index = RedisIndex(_filter, redis_client)
    filter_index.warm()
```

## Statsd integration

Redis-index optionally supports statsd-integration.

![Redis-Index performance](https://github.com/ErhoSen/redis-index/raw/master/images/redis_index_performance.png "Redis-Index performance")

![Redis-Index by filters](https://github.com/ErhoSen/redis-index/raw/master/images/redis_index_by_filters.png "Redis-Index by filters")

## Code of Conduct

Everyone interacting in the project's codebases, issue trackers, chat rooms, and mailing lists is expected to follow the [PyPA Code of Conduct](https://www.pypa.io/en/latest/code-of-conduct/).

## History

### [0.1.11] - 2019-11-08

#### Added

- Added code for initial release
