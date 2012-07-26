import os
import os.path
import datetime
import logging


class Cache(object):
    def __init__(self, cache_dir=None, default_lifetime=None, logger=None):
        if not default_lifetime:
            default_lifetime = datetime.timedelta(minutes=60)
        if not logger:
            logger = logging.getLogger('cache')
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.cache_dir = cache_dir
        self.default_lifetime = default_lifetime
        self.items = {}
        self.logger = logger

    def has(self, key):
        return key in self.items

    def get(self, key, raise_on_miss=False):
        if not key in self.items:
            if raise_on_miss:
                raise Exception("Cache miss, key not found: %s" % key)
            self.logger.debug('Cache miss (reason: not found): %s' % key)
            return None
        item = self.items[key]
        if item['end_time'] < datetime.datetime.now():
            self.logger.debug('Cache miss (reason: outdated): %s' % key)
            self.items.pop(key)
            return None
        self.logger.debug('Cache hit: %s' % key)
        return item['data']

    def set(self, key, data, lifetime=None):
        if not lifetime:
            lifetime = self.default_lifetime
        self.items[key] = {
                'end_time': datetime.datetime.now() + lifetime,
                'data': data
                }
        self.logger.debug('Cached: %s' % key)

