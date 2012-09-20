import json
import os.path
import thread
from flask import g, redirect, url_for, request, render_template, flash
from cache import Cache, DummyCache
from cbz import CbzLibrary
from clf import app
from comixology import ComicsAccount, CDN, get_display_title
from helpers import login_required, get_comicbooks_library_dir


# Globals
cache = Cache(os.path.join(os.path.dirname(__file__), 'cache'))
active_downloads = {}


# Request pre/post-processors
@app.before_request
def before_request():
    g.cache = cache
    if request.args.get('nocache', False):
        g.cache = DummyCache()


# Views
@app.route('/')
@login_required
def index():
    collection = g.cache.get('collection')
    if not collection:
        collection = g.account.get_collection()
        g.cache.set('collection', collection)

    for series in collection:
        series['logo'] = CDN.get_resized(series['logo'], 170, 170)
        series['display_title'] = get_display_title(series)

    return render_template(
            'index.html', 
            title="Your Collection",
            username=g.account.username,
            collection=collection
            )


@app.route('/series/<int:series_id>')
@login_required
def series(series_id):
    series = g.cache.get('series_%d' % series_id)
    if not series:
        series = g.account.get_series(series_id)
        g.cache.set('series_%d' % series_id, series)

    collection = g.cache.get('collection')
    if not collection:
        collection = g.account.get_collection()
        g.cache.set('collection', collection)
    
    series_info = find_series_in_collection(collection, str(series_id))
    if not series_info:
        raise Exception("Can't find series '%s' in collection." % series_id)

    lib_root = get_comicbooks_library_dir(g.settings)
    lib = CbzLibrary(lib_root)
    for issue in series:
        path = lib.build_issue_path(
                series_info['title'], 
                issue['title'], 
                issue['num']
                )
        if os.path.isfile(path):
            issue['downloaded'] = True

        issue['cover'] = CDN.get_resized(issue['cover'], 170, 170)
        issue['display_title'] = get_display_title(issue)

    return render_template(
            'series.html',
            title="Your Collection",
            username=g.account.username,
            series_id=series_id,
            series=series
            )


@app.route('/download/<int:series_id>', defaults={'comic_id': None})
@app.route('/download/<int:series_id>/<int:comic_id>')
@login_required
def download(series_id, comic_id):
    app.logger.debug('Received download request for [%s]' % comic_id)
    if not comic_id in active_downloads:
        thread.start_new_thread(do_download, (comic_id, g.account, g.settings))
    return json.dumps({
        'status': 'ok'
        })


@app.route('/downloads')
@login_required
def downloads():
    return json.dumps(active_downloads)


@app.route('/settings', methods = ['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        pass
    return render_template(
            'settings.html',
            title="Settings"
            )


@app.route('/login', methods = ['GET', 'POST'])
def login(next=''):
    if request.method == 'POST':
        account = ComicsAccount(request.form['username'])
        account.login(request.form['password'])
        cache.set('account', account.get_cookie())
        flash("You were logged in as '%s'." % request.form['username'])
        if next:
            redirect(next)
        return redirect(url_for('index'))
    return render_template(
            'login.html',
            title="Login to Comixology"
            )


# Utility functions
def find_series_in_collection(collection, series_id):
    for series in collection:
        if series['series_id'] == series_id:
            return series
    return None

def do_download(comic_id, account, settings):
    issue = account.get_issue(comic_id)
    active_downloads[comic_id] = {
            'title': '%s #%s' % (issue['title'], issue['num']),
            'progress': 0
            }

    def on_cbz_progress(progress):
        active_downloads[comic_id]['progress'] = progress

    try:
        builder = cbz.CbzBuilder(account)
        comics_dir = get_comicbooks_library_dir(settings)
        app.logger.debug('Downloading %s [%s] to: %s' % (issue['title'], comic_id, comics_dir))
        builder.save(comics_dir, issue, subscriber=on_cbz_progress)
    except Exception as e:
        app.logger.error('Error downloading comic: %s' % e)
    finally:
        active_downloads.pop(comic_id)

