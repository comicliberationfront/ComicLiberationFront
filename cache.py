import os
import os.path
import json
import time
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
        if key in self.items:
            return True
        path = self._get_item_path(key)
        if path and os.path.isfile(path):
            return True
        return False

    def get(self, key, raise_on_miss=False):
        item = self._get_item(key)
        if item is None:
            if raise_on_miss:
                raise Exception("Cache miss, key not found: %s" % key)
            self.logger.debug('Cache miss (reason: not found): %s' % key)
            return None
        if item['end_time'] < time.time():
            self.logger.debug('Cache miss (reason: outdated): %s' % key)
            self.items.pop(key)
            path = self._get_item_path(key)
            if path and os.path.isfile(path):
                os.delete(path)
            return None
        self.logger.debug('Cache hit: %s' % key)
        return item['data']

    def set(self, key, data, lifetime=None):
        if not lifetime:
            lifetime = self.default_lifetime
        item = {
                'end_time': time.time() + lifetime.total_seconds(),
                'data': data
                }
        self.items[key] = item
        path = self._get_item_path(key)
        if path:
            with open(path, 'w') as f:
                json.dump(item, f)
        self.logger.debug('Cached: %s' % key)

    def _get_item_path(self, key):
        if not self.cache_dir:
            return None
        return os.path.join(self.cache_dir, '%s.json' % key)

    def _get_item(self, key):
        if not key in self.items:
            path = self._get_item_path(key)
            if path and os.path.isfile(path):
                self.logger.debug('Loading from disk cache: ' % key)
                with open(path, 'r') as f:
                    item = json.load(f)
                    self.items[key] = item
                    return item
        if key in self.items:
            return self.items[key]
        return None

