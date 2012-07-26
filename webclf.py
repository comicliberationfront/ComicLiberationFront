import os
import os.path
import thread
import logging
import json
from cache import Cache
import cbz
from comics8 import ComicsAccount
from flask import Flask, session, redirect, url_for, escape, request, render_template, flash

app = Flask(__name__)
app.secret_key = '$*^%&#53r3ret56$%@#Res'
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(logging.StreamHandler())

cache = Cache()
active_downloads = {}

@app.route('/')
def index():
    if not 'username' in session or not cache.has('account'):
        return redirect(url_for('login'))

    collection = cache.get('collection')
    if not collection:
        account = cache.get('account', True)
        collection = account.get_collection()
        cache.set('collection', collection)

    return render_template(
            'index.html', 
            title="Your Collection",
            username=session['username'],
            collection=collection
            )


@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        account = ComicsAccount(request.form['username'])
        account.login(request.form['password'])
        cache.set('account', account)
        session['username'] = request.form['username']
        flash("You were logged in as '%s'." % request.form['username'])
        return redirect(url_for('index'))
    return render_template(
            'login.html',
            title="Login to Comixology"
            )

@app.route('/series/<int:series_id>')
def series(series_id):
    if not 'username' in session or not cache.has('account'):
        return redirect(url_for('login'))

    series = cache.get('series_%d' % series_id)
    if not series:
        account = cache.get('account', True)
        series = account.get_series(series_id)
        cache.set('series_%d' % series_id, series)

    return render_template(
            'series.html',
            title="Your Collection",
            username=session['username'],
            series_id=series_id,
            series=series
            )

@app.route('/download/<int:series_id>', defaults={'comic_id': None})
@app.route('/download/<int:series_id>/<int:comic_id>')
def download(series_id, comic_id):
    if not 'username' in session or not cache.has('account'):
        return redirect(url_for('login'))

    app.logger.debug('Received download request for [%s]' % comic_id)
    if not comic_id in active_downloads:
        thread.start_new_thread(do_download, (comic_id,))
    return json.dumps({
        'status': 'ok'
        })

@app.route('/download_status/<int:comic_id>')
def get_download_status(comic_id):
    if not comic_id in active_downloads:
        return json.dumps({
            'title': '',
            'progress': -1
            })
    status = active_downloads[comic_id]
    return json.dumps(status)

def do_download(comic_id):
    account = cache.get('account', True)
    issue = account.get_issue(comic_id)
    active_downloads[comic_id] = {
            'title': '%s #%s' % (issue['title'], issue['num']),
            'progress': 0
            }

    def on_cbz_progress(progress):
        app.logger.debug('[%s] Downloading page %d...' % (comic_id, progress))
        active_downloads[comic_id]['progress'] = progress

    app.logger.debug('Starting download of %s [%s]' % (issue['title'], comic_id))
    builder = cbz.CbzBuilder(account)
    out_path = os.path.expanduser('~/Comicbooks')
    builder.save(out_path, issue, subscriber=on_cbz_progress)
    active_downloads.pop(comic_id)

if __name__ == "__main__":
    app.debug = True
    app.run()

