import json
import os.path
import thread
from flask import g, redirect, url_for, request, render_template, flash
from auth import UserAccount, get_service_class
from cache import Cache, DummyCache
from cbz import CbzLibrary, CbzBuilder
from clf import app


# Globals
cache = Cache(os.path.join(os.path.dirname(__file__), 'cache'))
active_downloads = {}


# Request pre/post-processors
@app.before_request
def before_request():
    try:
        g.account = UserAccount.load()
    except:
        ua = UserAccount()
        ua.save()
        g.account = ua

    if request.args.get('nocache', False):
        g.account.set_caches(DummyCache())
    else:
        g.account.set_caches(cache)


# Views
@app.route('/')
def index():
    collections = list(g.account.get_collections())
    for collection in collections:
        service = collection['service']
        collection['service_name'] = service.service_name
        collection['service_label'] = service.service_label
        collection['username'] = service.username
        for series in collection['collection']:
            series.small_logo_url = service.cdn.get_resized(series.logo_url, 170, 170)

    return render_template(
            'index.html', 
            title="Your Collection",
            collections=collections
            )


@app.route('/series/<service_name>/<int:series_id>')
def series(service_name, series_id):
    service = g.account.services[service_name]
    series = service.get_series(series_id)
    collection = service.get_collection()
    series_info = find_series_in_collection(collection, str(series_id))
    if not series_info:
        raise Exception("Can't find series '%s' in collection." % series_id)

    lib = CbzLibrary(g.account.library_path)
    for issue in series:
        issue.series_title = series_info.title # Patch missing series_title from Comixology
        path = lib.get_issue_path(issue)
        issue.path = path
        if os.path.isfile(path):
            issue.downloaded = True

        issue.small_cover_url = service.cdn.get_resized(issue.cover_url, 170, 170)

    return render_template(
            'series.html',
            title="Your Collection: %s" % series_info.title,
            service_name=service.service_name,
            username=service.username,
            series_id=series_id,
            series=series
            )


@app.route('/download/<service_name>/<int:series_id>', defaults={'comic_id': None})
@app.route('/download/<service_name>/<int:series_id>/<int:comic_id>')
def download(service_name, series_id, comic_id):
    app.logger.debug('Received download request for [%s]' % comic_id)
    if not comic_id in active_downloads:
        thread.start_new_thread(do_download, (service_name, comic_id, g.account))
    return json.dumps({
        'status': 'ok'
        })


@app.route('/downloads')
def downloads():
    return json.dumps(active_downloads)


@app.route('/settings', methods = ['GET', 'POST'])
def settings():
    if request.method == 'POST':
        pass
    return render_template(
            'settings.html',
            title="Settings"
            )


@app.route('/settings', methods = ['GET', 'POST'])
def settings():
    if request.method == 'POST':
        g.account.library_path = request.form['library_path']
        g.account.save()
        flash("Successfully updated your preferences.")
        return redirect(url_for('settings'))
    return render_template(
            'settings.html',
            title="Settings",
            library_path=g.account.library_path,
            services=[n for n in g.account.services]
            )


@app.route('/services/login/<service_name>', methods = ['GET', 'POST'])
def service_login(service_name, next=''):
    if request.method == 'POST':
        account_class = get_service_class(service_name)
        account = account_class(request.form['username'])
        account.login(request.form['password'])
        g.account.services[service_name] = account
        g.account.save()
        flash("You were logged in with %s as '%s'." % (service_name, request.form['username']))
        if next:
            redirect(next)
        return redirect(url_for('index'))
    return render_template(
            'service_login.html',
            title=("Login to %s" % service_name)
            )


# Utility functions
def find_series_in_collection(collection, series_id):
    for series in collection:
        if series.series_id == series_id:
            return series
    return None

def do_download(service_name, comic_id, account):
    service = account.services[service_name]
    issue = service.get_issue(comic_id)
    active_downloads[comic_id] = {
            'title': '%s #%s' % (issue.title, issue.num),
            'progress': 0
            }

    def on_cbz_progress(progress):
        active_downloads[comic_id]['progress'] = progress

    try:
        builder = CbzBuilder()
        builder.set_watermark(service_name, service.username)
        app.logger.debug('Downloading %s [%s] to: %s' % (issue.title, comic_id, account.library_path))
        builder.save(account.library_path, issue, subscriber=on_cbz_progress, add_folder_structure=True)
    except Exception as e:
        app.logger.error('Error downloading comic: %s' % e)
    finally:
        active_downloads.pop(comic_id)

