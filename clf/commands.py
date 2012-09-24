import json
import os.path
import pprint
import re
import sys
from flask import g
from flask.ext.script import prompt, prompt_pass
from auth import UserAccount, get_service_classes, get_service_class
from clf import manager, cache_dir
from cbz import CbzBuilder, CbzLibrary, get_issue_version


# Command functions

@manager.command
def services(available=False):
    ''' Lists connected or available services.
    '''
    account = _get_account()
    if available:
        print "Available services:"
        for c in get_service_classes():
            if c.service_name in account.services:
                print "%s (connected)" % c.service_label
            else:
                print c.service_label
    else:
        print "Connected services:"
        for s in account.services:
            print "%s (logged in as %s)" % (
                    account.services[s].service_label, 
                    account.services[s].username)

@manager.command
def login(username=None, password=None, service=None):
    ''' Logs into a comicbook store provider (e.g. Comixology).
    '''
    try:
        service_class = _get_service_class_safe(service, message="Choose a service to log into:")
    except Exception as e:
        print e
        return 1

    if username is None:
        username = prompt('username (on %s)' % str(service_class.service_label))
    if password is None:
        password = prompt_pass('password (on %s)' % str(service_class.service_label))

    try:
        service_account = service_class(username)
        service_account.login(password)
    except Exception as e:
        print "Error authenticating with %s" % service_class.service_label
        print e
        return 1

    account = _get_account()
    account.services[service] = service_account
    account.save()


@manager.option('query', nargs='?', default=None)
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-i', '--id', dest='series_id', default=None)
def list(query=None, service_name=None, series_id=None):
    ''' Lists series or issues.
    '''
    service = _get_service_safe(service_name)

    pattern = None
    if query:
        pattern = query.strip('\'" ')

    if series_id:
        series = service.get_series(series_id)
        for issue in series:
            if pattern and not re.search(pattern, issue.title, re.IGNORECASE):
                continue
            print "[%s] %s" % (issue.comic_id, issue.display_title)
    else:
        collection = service.get_collection()
        for series in collection:
            series_title = series.display_title
            if pattern and not re.search(pattern, series_title, re.IGNORECASE):
                continue
            print "[%s] %s (%s)" % (series.series_id, series_title, series.issue_count)


@manager.command
def download(service_name, issue_id, output, metadata_only=False):
    ''' Downloads comicbook issues.
    '''
    service = _get_service_safe(service_name)

    issue = service.get_issue(issue_id)
    print "[%s] %s" % (issue.comic_id, issue.display_title)
    
    builder = CbzBuilder()
    builder.set_watermark(service.service_name, service.username)
    builder.set_progress_subscriber(_print_download_progress)
    builder.set_temp_folder(cache_dir)
    out_path = output.strip('\'" ')
    if metadata_only:
        builder.update(issue, out_path=path)
    else:
        builder.save(issue, out_path=out_path, subscriber=_print_sync_progress)


@manager.option('query', nargs='?', default=None)
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-i', '--id', dest='series_id', default=None)
@manager.option('-m', '--metadata-only', dest='metadata_only', default=False, action='store_true')
@manager.option('--library_dir', dest='lib_dir', default=None)
def sync(query=None, service_name=None, series_id=None, metadata_only=False, lib_dir=None):
    ''' Synchronizes the local comicbook library with the connected or specified services.
    '''
    if query is not None and series_id is not None:
        raise Exception("Can't specify both a query and a series ID.")

    service = _get_service_safe(service_name)

    if lib_dir is None:
        account = _get_account()
        lib_dir = account.library_path
    out_path = lib_dir.strip('\'" ')
    library = CbzLibrary(out_path)

    if series_id is None:
        if query is None:
            print "Getting all issues from %s..." % service.service_label
            issues = service.get_all_issues()
        else:
            issues = []
            query = query.strip('\'" ')
            collection = service.get_collection()
            for series in collection:
                if not re.search(query, series.display_title, re.IGNORECASE):
                    continue
                print "Getting issues from %s for: %s" % (service.service_label, series.display_title)
                issues += service.get_all_issues(series.series_id)
    else:
        print "Getting issues from %s for series ID %s" % (service.service_label, series_id)
        issues = service.get_all_issues(series_id)

    print "Syncing issues..."
    builder = CbzBuilder()
    builder.set_watermark(service.service_name, service.username)
    builder.set_progress_subscriber(_print_download_progress)
    builder.set_temp_folder(cache_dir)
    library.sync_issues(builder, issues, 
            metadata_only=metadata_only, 
            subscriber=_print_sync_progress) 


@manager.command
def purchases(service_name=None):
    ''' Lists recent purchases in the current comicbook store.
    '''
    service = _get_service_safe(service_name)
    purchases = service.get_recent_purchases()
    for p in purchases:
        print "[%s] %s" % (p.comic_id, p.display_title)


@manager.command
def print_issue(issue_id, service_name=None):
    ''' Prints information about a comicbook issue.
    '''
    service = _get_service_safe(service_name)
    issue = service.get_issue(issue_id)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(issue.__dict__)


# Helper functions

def _get_account():
    try:
        return UserAccount.load()
    except:
        print "Creating new CLF session."
        return UserAccount()


def _get_service_class_safe(service_name, message="Choose the service for this command:"):
    if service_name is None:
        print message
        default_service_name = None
        for i, c in enumerate(get_service_classes()):
            if i == 0:
                default_service_name = c.service_name
                print " - %s [default]" % c.service_name
            else:
                print " - %s" % c.service_name
        service_name = prompt('service', default=default_service_name)

    try:
        return get_service_class(service_name)
    except:
        raise Exception("No such service: %s" % service_name)


def _get_service_safe(service_name, message="Choose the service for this command:"):
    account = _get_account()
    if service_name is None:
        print message
        default_service_name = None
        for i, c in enumerate(account.services):
            if i == 0:
                default_service_name = c
                print " - %s [default]" % c
            else:
                print " - %s" % c
        service_name = prompt('service', default=default_service_name)

    try:
        return account.services[service_name]
    except KeyError:
        raise Exception("No such service: %s" % service_name)


def _filter_series(service, query, series_id):

    pass


def _print_download_progress(value=None, message=None, error=None):
    if error is not None:
        print "ERROR: %s" % error
    if value is not None:
        sys.stdout.write("\r")
        if value < 100:
            sys.stdout.write(" %02d%% " % value)
        else:
            sys.stdout.write(" 100%\n")
        if message is not None:
            sys.stdout.write(message)
    sys.stdout.flush()


def _print_sync_progress(message=None, error=None):
    if error is not None:
        print "ERROR: %s" % error
    if message is not None:
        print message

