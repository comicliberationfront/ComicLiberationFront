import re
import os.path
import pprint
import progressbar
from flask.ext.script import prompt, prompt_pass
from auth import UserAccount, get_service_classes, get_service_class
from clf import app, manager, cache_dir
from cbz import CbzBuilder, CbzLibrary
from downloader import DownloadProgress


# Command functions

@manager.command
def services(available=False):
    ''' Lists connected or available services.
    '''
    account = _get_account()
    if available:
        app.logger.info("Available services:")
        for c in get_service_classes():
            if c.service_name in account.services:
                app.logger.info("%s (connected)" % c.service_label)
            else:
                app.logger.info(c.service_label)
    else:
        app.logger.info("Connected services:")
        for s in account.services:
            app.logger.info("%s (logged in as %s)" % (
                    account.services[s].service_label, 
                    account.services[s].username))

@manager.command
def login(username=None, password=None, service=None):
    ''' Logs into a comicbook store provider (e.g. Comixology).
    '''
    try:
        service_class = _get_service_class_safe(service, message="Choose a service to log into:")
    except Exception as e:
        app.logger.error(e)
        return 1

    if username is None:
        username = prompt('username (on %s)' % str(service_class.service_label))
    if password is None:
        password = prompt_pass('password (on %s)' % str(service_class.service_label))

    try:
        service_account = service_class(username)
        service_account.login(password)
    except Exception as e:
        app.logger.error("Error authenticating with %s" % service_class.service_label)
        app.logger.error(e)
        return 1

    account = _get_account()
    account.services[service_class.service_name] = service_account
    account.save()


@manager.option('query', nargs='?', default=None)
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-i', '--id', dest='series_id', default=None)
@manager.option('-v', '--vid', dest='volume_id', default=None)
@manager.option('-p', '--path', dest='print_path', default=False, action='store_true')
def list(query=None, service_name=None, series_id=None, volume_id=None, print_path=False):
    ''' Lists series or issues.
    '''
    service = _get_service_safe(service_name)
    account = _get_account()
    library = CbzLibrary(account.library_path)

    def print_paths(parent):
        if print_path:
            for issue in parent.get_issues():
                app.logger.info(" > %s" % library.get_issue_path(issue))

    if series_id is not None:
        vols = _get_filtered_volumes(service, query, series_id)
        vols = sorted(vols, key=lambda s: s.title)
        for vol in vols:
            app.logger.info("[%s] %s" % (vol.volume_id, vol.get_display_title()))
            print_paths(vol)
    elif volume_id is not None:
        issues = _get_filtered_issues(service, query, volume_id=volume_id)
        issues = sorted(issues, key=lambda s: s.title)
        for issue in issues:
            app.logger.info("[%s] %s" % (issue.comic_id, issue.get_display_title()))
            print_paths(issue)
    else:
        series = _get_filtered_series(service, query)
        series = sorted(series, key=lambda s: s.title)
        for s in series:
            app.logger.info("[%s] %s (%s issues)" % (s.series_id, s.get_display_title(), s.issue_count))
            print_paths(s)


@manager.option('query', nargs='?', default=None)
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-i', '--id', dest='series_id', default=None)
def price(query=None, service_name=None, series_id=None):
    ''' Gives the total price of the specified series or issues.
    '''
    service = _get_service_safe(service_name)
    issues = _get_filtered_issues(service, query, series_id)

    total_price = 0
    paid_count = 0
    free_count = 0
    for issue in issues:
        if issue.price:
            total_price += issue.price
            paid_count += 1
        else:
            free_count += 1

    app.logger.info("$%f out of %d paid issues." % (total_price, paid_count))
    app.logger.info("%d free issues." % (free_count))
    

@manager.option('issue_id')
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-o', '--output', dest='output', default=None)
@manager.option('--metadata-only', dest='metadata_only', default=False, action='store_true')
def download(issue_id, service_name=None, output=None, metadata_only=False):
    ''' Downloads comicbook issues.
    '''
    service = _get_service_safe(service_name)

    issue = service.get_issue(issue_id)
    app.logger.info("[%s] %s" % (issue.comic_id, issue.get_display_title()))
    
    if output is None:
        account = _get_account()
        library = CbzLibrary(account.library_path)
        output = library.get_issue_path(issue)
    out_path = output.strip('\'" ')

    builder = CbzBuilder(service, subscriber=CliDownloadProgress(), temp_folder=cache_dir)
    builder.username = service.username
    if metadata_only:
        builder.update(issue, out_path=out_path)
        app.logger.info("Issue updated at: %s" % out_path)
    else:
        builder.save(issue, out_path=out_path)
        app.logger.info("Issue saved at: %s" % out_path)


@manager.option('query', nargs='?', default=None)
@manager.option('-s', '--service', dest='service_name', default=None)
@manager.option('-i', '--id', dest='series_id', default=None)
@manager.option('--new-only', dest='new_only', default=False, action='store_true')
@manager.option('--metadata-only', dest='metadata_only', default=False, action='store_true')
@manager.option('--library-dir', dest='lib_dir', default=None)
def sync(query=None, service_name=None, series_id=None, new_only=False, metadata_only=False, lib_dir=None):
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
            app.logger.info("Getting all issues from %s..." % service.service_label)
            issues = service.get_collection().get_issues()
        else:
            issues = []
            query = query.strip('\'" ')
            collection = service.get_collection()
            for series in collection:
                if not re.search(query, series.get_display_title(), re.IGNORECASE):
                    continue
                app.logger.info("Getting issues from %s for: %s" % (service.service_label, series.get_display_title()))
                issues += series.get_issues()
    else:
        app.logger.info("Getting issues from %s for series ID %s" % (service.service_label, series_id))
        issues = service.get_collection().get_series(series_id).get_issues()

    app.logger.info("Syncing issues...")
    builder = CbzBuilder(service, subscriber=CliDownloadProgress(), temp_folder=cache_dir)
    builder.username = service.username
    library.sync_issues(builder, issues, 
            new_only=new_only,
            metadata_only=metadata_only)


@manager.command
def purchases(service_name=None):
    ''' Lists recent purchases in the current comicbook store.
    '''
    service = _get_service_safe(service_name)
    purchases = service.get_recent_purchases()
    for p in purchases:
        app.logger.info("[%s] %s" % (p.comic_id, p.get_display_title()))


@manager.command
def print_issue(issue_id, service_name=None):
    ''' Prints information about a comicbook issue.
    '''
    service = _get_service_safe(service_name)
    issue = service.get_issue(issue_id)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(issue.__dict__)


# Helper functions

class CliDownloadProgress(DownloadProgress):
    def __init__(self):
        DownloadProgress.__init__(self)
        self.pbar = progressbar.ProgressBar()
        self.started = False

    def _doProgress(self, value, message=None):
        # sys.stdout.write("\r %02d%% " % value)
        # if message is not None:
        #     sys.stdout.write(message)
        # if value >= 100:
        #     sys.stdout.write("\n")
        # sys.stdout.flush()
        if not self.started:
            self.pbar.start()
        self.pbar.update(value)
        if value >= 100:
            self.pbar.finish()


def _get_account():
    try:
        ua = UserAccount.load()
    except Exception as e:
        app.logger.info("Creating new CLF session.")
        app.logger.info("(reason: %s)" % e)
        ua = UserAccount()
    ua.set_cache_dir(os.path.join(cache_dir, 'reqs'))
    return ua


def _prompt_index(message, default=1, min_val=1, max_val=10):
    choice = prompt(message, default=str(default))
    choice = int(choice)
    if choice < min_val or choice > max_val:
        raise Exception("Please choose one of the available options.")
    return choice

def _get_service_class_safe(service_name, message="Choose the service for this command:"):
    if service_name is None:
        app.logger.info(message)
        service_classes = list(get_service_classes())
        for i, c in enumerate(service_classes):
            if i == 0:
                app.logger.message(" - [%d] %s [default]" % (i+1, c.service_name))
            else:
                app.logger.message(" - [%d] %s" % (i+1, c.service_name))
        choice = _prompt_index('service', max_val=len(service_classes)+1)
        service_name = service_classes[choice-1].service_name

    try:
        return get_service_class(service_name)
    except:
        raise Exception("No such service: %s" % service_name)


def _get_service_safe(service_name, message="Choose the service for this command:"):
    account = _get_account()
    if service_name is None:
        app.logger.info(message)
        names = account.services.keys()
        for i, c in enumerate(account.services):
            if i == 0:
                app.logger.info(" - [%d] %s [default]" % (i+1, c))
            else:
                app.logger.info(" - [%d] %s" % (i+1, c))
        choice = _prompt_index('service', max_val=len(names)+1)
        service_name = names[choice-1]

    try:
        return account.services[service_name]
    except KeyError:
        raise Exception("No such service: %s" % service_name)


def _get_filtered_series(service, query=None):
    pattern = None
    if query:
        pattern = query.strip('\'" ')

    collection = service.get_collection()
    for series in collection:
        if pattern and not re.search(pattern, series.get_display_title(), re.IGNORECASE):
            continue
        yield series


def _get_filtered_volumes(service, query=None, series_id=None):
    pattern = None
    if query:
        pattern = query.strip('\'" ')

    collection = service.get_collection()
    if series_id:
        collection = filter(lambda s: s.series_id == series_id, collection)
    for series in collection:
        for vol in series.volumes:
            if pattern and not re.search(pattern, vol.get_display_title(), re.IGNORECASE):
                continue
            yield vol


def _get_filtered_issues(service, query=None, series_id=None, volume_id=None):
    pattern = None
    if query:
        pattern = query.strip('\'" ')

    collection = service.get_collection()
    if series_id:
        collection = filter(lambda s: s.series_id == series_id, collection)
    for series in collection:
        volumes = series.volumes
        if volume_id:
            volumes = filter(lambda v: v.volume_id == volume_id, volumes)
        for vol in volumes:
            for issue in vol.issues:
                if pattern and not re.search(pattern, issue.get_display_title(), re.IGNORECASE):
                    continue
                yield issue

