import base64
import json
import os.path
from functools import wraps
from flask import g, redirect, url_for
from clf import app
from comixology import ComicsAccount


SERVICE_CLASSES = { 'comixology': ComicsAccount }


def get_service_class(service):
    return SERVICE_CLASSES[service]


class UserAccount(object):
    def __init__(self):
        self.library_path = os.path.expanduser('~/Comicbooks')
        self.services = {}
        self._current_service_name = None

    @property
    def current_service(self):
        if self.current_service_name is None:
            return None
        return self.services[self.current_service_name]

    @property
    def current_service_name(self):
        if self._current_service_name is None:
            if len(self.services) == 0:
                return None
            self._current_service_name = self.services.keys()[0]
        return self._current_service_name

    @current_service_name.setter
    def current_service_name(self, value):
        if value not in self.services:
            raise Exception("No such service: %s" % value)
        self._current_service_name = value

    def save(self, path=None):
        account = { 'library_path': self.library_path, 'cookies': {} }
        for k, v in self.services.iteritems():
            account['cookies'][k] = base64.b64encode(json.dumps(v.get_cookie()))

        if path is None:
            path = os.path.expanduser('~/.clf_session')
        with open(path, 'w') as fd:
            json.dump(account, fd)

    def __getattr__(self, attr):
        if attr not in self.services:
            raise AttributeError("No such service: %s" % attr)
        return self.services[attr]

    def set_caches(self, cache):
        for n, s in self.services.iteritems():
            s.cache = cache

    def get_collections(self):
        for n, s in self.services.iteritems():
            c = {
                    'service': s,
                    'collection': s.get_collection()
                    }
            yield c

    @staticmethod
    def load(path=None):
        if path is None:
            path = os.path.expanduser('~/.clf_session')
        if not os.path.isfile(path):
            raise Exception("Invalid path: %s" % path)
        with open(path, 'r') as fd:
            account_str = fd.read()
        account = json.loads(account_str)
        u = UserAccount()
        if 'library_path' in account:
            u.library_path = account['library_path']
        if 'cookies' in account:
            for k, v in account['cookies'].iteritems():
                cookie = json.loads(base64.b64decode(v))
                u.services[k] = get_service_class(cookie['service']).from_cookie(cookie)
        return u


# Custom decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'account'):
            g.account = app.clf_data['account']
        return f(*args, **kwargs)
    return decorated_function

