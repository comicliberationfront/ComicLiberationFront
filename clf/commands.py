import json
import os.path
import pprint
import re
import sys
from flask import g
from flask.ext.script import prompt, prompt_pass
from auth import UserAccount, get_service_class
from clf import manager
from cbz import CbzBuilder, CbzLibrary, get_issue_version


# Command functions

@manager.command
def login(username, password=None, service='comixology'):
    ''' Logs into a comicbook store provider (e.g. Comixology).
    '''
    if service is None:
        service = prompt('service')
    if username is None:
        username = prompt('username (on %s)' % str(service))
    if password is None:
        password = prompt_pass('password (on %s)' % str(service))
    service_class = get_service_class(service)
    service_account = service_class(username)
    service_account.login(password)

    account = _get_account()
    account.services[service] = service_account
    account.save()


@manager.command
def use(service=None):
    ''' Switches all commands to another service
    '''
    account = _get_account()
    if service is None:
        print "Using: %s" % account.current_service_name
    else:
        account.current_service_name = service
        print "Switched to: %s" % service


@manager.command
def list(query=None, series_id=None):
    ''' Lists series or issues.
    '''
    account = _get_current_service()
    pattern = None
    if query:
        pattern = query.strip('\'" ')

    if series_id:
        series = account.get_series(series_id)
        for issue in series:
            if pattern and not re.search(pattern, issue.title, re.IGNORECASE):
                continue
            print "[%s] %s" % (issue.comic_id, issue.display_title)
    else:
        collection = account.get_collection()
        for series in collection:
            series_title = series.display_title
            if pattern and not re.search(pattern, series_title, re.IGNORECASE):
                continue
            print "[%s] %s (%s)" % (series.series_id, series_title, series.issue_count)


@manager.command
def download(issue_id, output, metadata_only=False):
    ''' Downloads comicbook issues.
    '''
    account = _get_current_service()
    issue = account.get_issue(issue_id)
    print "[%s] %s" % (issue.comic_id, issue.display_title)
    
    builder = CbzBuilder()
    builder.set_watermark(account.service_name, account.username)
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
    account = _get_current_service()
    builder = CbzBuilder()
    builder.set_watermark(account.service_name, account.username)

    issues = account.get_all_issues(series)
    for issue in issues:
        prefix = "[%s] %s" % (issue.comic_id, issue.display_title)
        path = library.get_issue_path(issue)
        if os.path.isfile(path):
            local_version = int(get_issue_version(path))
            remote_version = int(issue.version)
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
    ''' Lists recent purchases in the current comicbook store.
    '''
    account = _get_current_service()
    purchases = account.get_recent_purchases()
    for p in purchases:
        print "[%s] %s" % (p.comic_id, p.display_title)


@manager.command
def print_issue(issue_id):
    ''' Prints information about a comicbook issue.
    '''
    account = _get_current_service()
    issue = account.get_issue(args.issue_id)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(issue)


# Helper functions

def _get_account():
    try:
        return UserAccount.load()
    except:
        print "Creating new CLF session."
        return UserAccount()


def _get_current_service():
    u = _get_account()
    return u.current_service


def _print_progress(value):
    if value < 100:
        sys.stdout.write("\r%02d%%" % value)
    else:
        sys.stdout.write("\r100%\n")
    sys.stdout.flush()

