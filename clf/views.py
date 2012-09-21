import json
import os.path
import thread
from flask import g, redirect, url_for, request, render_template, flash
from auth import UserAccount, get_service_class, login_required
from cache import Cache, DummyCache
from cbz import CbzLibrary, CbzBuilder
from clf import app


# Globals
cache = Cache(os.path.join(os.path.dirname(__file__), 'cache'))
active_downloads = {}
app.clf_data = { 'cache': cache, 'account': None }
try:
    app.clf_data['account'] = UserAccount.load()
except:
    app.clf_data['account'] = UserAccount()
app.clf_data['account'].current_service.cache = cache


# Request pre/post-processors
@app.before_request
def before_request():
    if request.args.get('nocache', False):
        app.clf_data['account'].current_service.cache = DummyCache()


# Views
@app.route('/')
@login_required
def index():
    collection = g.account.current_service.get_collection()
    for series in collection:
        series.small_logo_url = g.account.current_service.cdn.get_resized(series.logo_url, 170, 170)

    return render_template(
            'index.html', 
            title="Your Collection",
            username=g.account.current_service.username,
            collection=collection
            )


@app.route('/series/<int:series_id>')
@login_required
def series(series_id):
    series = g.account.current_service.get_series(series_id)
    collection = g.account.current_service.get_collection()
    series_info = find_series_in_collection(collection, str(series_id))
    if not series_info:
        raise Exception("Can't find series '%s' in collection." % series_id)

    lib = CbzLibrary(g.account.library_path)
    for issue in series:
        issue.series_title = series_info.title # Patch missing series_title from Comixology
        path = lib.get_issue_path(issue)
        if os.path.isfile(path):
            issue.downloaded = True

        issue.small_cover_url = g.account.current_service.cdn.get_resized(issue.cover_url, 170, 170)

    return render_template(
            'series.html',
            title="Your Collection",
            username=g.account.current_service.username,
            series_id=series_id,
            series=series
            )


@app.route('/download/<int:series_id>', defaults={'comic_id': None})
@app.route('/download/<int:series_id>/<int:comic_id>')
@login_required
def download(series_id, comic_id):
    app.logger.debug('Received download request for [%s]' % comic_id)
    if not comic_id in active_downloads:
        thread.start_new_thread(do_download, (comic_id, g.account))
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
        if series.series_id == series_id:
            return series
    return None

def do_download(comic_id, account):
    issue = account.current_service.get_issue(comic_id)
    active_downloads[comic_id] = {
            'title': '%s #%s' % (issue.title, issue.num),
            'progress': 0
            }

    def on_cbz_progress(progress):
        active_downloads[comic_id]['progress'] = progress

    try:
        builder = CbzBuilder()
        builder.set_watermark(account.current_service_name, account.current_service.username)
        app.logger.debug('Downloading %s [%s] to: %s' % (issue.title, comic_id, account.library_path))
        builder.save(account.library_path, issue, subscriber=on_cbz_progress, add_folder_structure=True)
    except Exception as e:
        app.logger.error('Error downloading comic: %s' % e)
    finally:
        active_downloads.pop(comic_id)

