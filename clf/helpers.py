import json
import os.path
from functools import wraps
from flask import g, redirect, url_for
from comixology import ComicsAccount


# Custom decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'account'):
            path = os.path.expanduser('~/.clf_session')
            if os.path.isfile(path):
                with open(path, 'r') as fd:
                    cookie_str = fd.read()
                cookie = json.loads(cookie_str)
                g.settings = cookie
                g.account = ComicsAccount.from_cookie(cookie)
        if not hasattr(g, 'account'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


# Helper functions
def get_comicbooks_library_dir(settings):
    comics_dir = os.path.expanduser('~/Comicbooks')
    if settings and 'comics_dir' in settings:
        comics_dir = settings['comics_dir']
    return comics_dir

