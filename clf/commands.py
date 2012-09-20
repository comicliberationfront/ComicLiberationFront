import json
import os.path
import pprint
import re
import sys
from flask.ext.script import prompt, prompt_pass
from clf import manager
from cbz import CbzBuilder, CbzLibrary, get_issue_version
from comixology import ComicsAccount, get_display_title


@manager.command
def login(username, password=None):
    ''' Logs into a comicbook store provider (e.g. Comixology).
    '''
    if username is None:
        username = prompt('Username:')
    if password is None:
        password = prompt_pass('Password:')
    account = ComicsAccount(username)
    account.login(password)
    cookie = account.get_cookie()
    with open(os.path.expanduser('~/.clf_session'), 'w') as f:
        f.write(json.dumps(cookie))


@manager.command
def list(query=None, series_id=None):
    ''' Lists series or issues.
    '''
    account = _get_account()
    pattern = None
    if query:
        pattern = query.strip('\'" ')

    if series_id:
        series = account.get_series(series_id)
        for issue in series:
            if pattern and not re.search(pattern, issue['title'], re.IGNORECASE):
                continue
            print "[%s] %s" % (issue['comic_id'], get_display_title(issue))
    else:
        collection = account.get_collection()
        for series in collection:
            series_title = get_display_title(series)
            if pattern and not re.search(pattern, series_title, re.IGNORECASE):
                continue
            print "[%s] %s (%s)" % (series['series_id'], series_title, series['issue_count'])


@manager.command
def download(issue_id, output, metadata_only=False):
    ''' Downloads comicbook issues.
    '''
    account = _get_account()
    issue = account.get_issue(issue_id)
    print "[%s] %s" % (issue['comic_id'], get_display_title(issue))
    
    builder = CbzBuilder(account)
    out_path = output.strip('\'" ')
    if metadata_only:
        builder.update(out_path, issue)
    else:
        builder.save(out_path, issue, subscriber=_print_progress)


@manager.command
def update(lib_dir, series_id=None, metadata_only=False):
    ''' Updates the local comicbook library.
    '''
    out_path = lib_dir.strip('\'" ')
    library = CbzLibrary(out_path)
    account = _get_account()
    builder = CbzBuilder(account)

    issues = account.get_all_issues(series)
    for issue in issues:
        prefix = "[%s] %s" % (issue['comic_id'], get_display_title(issue))
        path = library.get_issue_path(issue)
        if os.path.isfile(path):
            local_version = int(get_issue_version(path))
            remote_version = int(issue['version'])
            if remote_version > local_version:
                print "%s: updating issue (%d[remote] > %d[local])" % (prefix, remote_version, local_version)
                if metadata_only:
                    print "(metadata only)"
                    builder.update(out_path, issue, add_folder_structure=True)
                else:
                    os.rename(path, path + '.old')
                    builder.save(out_path, issue, subscriber=_print_progress, add_folder_structure=True)
                    os.remove(path + '.old')
            else:
                print "%s: up-to-date (%d[remote] <= %d[local])" % (prefix, remote_version, local_version)
        else:
            print "%s: downloading" % prefix
            builder.save(out_path, issue, subscriber=_print_progress, add_folder_structure=True)

@manager.command
def purchases():
    ''' Lists recent purchases in registered comicbook stores.
    '''
    account = _get_account()
    purchases = account.get_recent_purchases()
    for p in purchases:
        print "[%s] %s #%s" % (p['comic_id'], p['title'], p['num'])


@manager.command
def print_issue(issue_id):
    ''' Prints information about a comicbook issue.
    '''
    account = _get_account()
    issue = account.get_issue(args.issue_id)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(issue)


def _get_account(path=os.path.expanduser('~/.clf_session')):
    with open(path, 'r') as f:
        cookie_str = f.read()
    cookie = json.loads(cookie_str)
    return ComicsAccount.from_cookie(cookie)


def _print_progress(value):
    if value < 100:
        sys.stdout.write("\r%02d%%" % value)
    else:
        sys.stdout.write("\r100%\n")
    sys.stdout.flush()

