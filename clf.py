#!/usr/bin/python
import os
import os.path
import sys
import re
import argparse
import json
import pprint
import cbz
from comics8 import ComicsAccount, get_display_title


class CLF:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
                description='The command-line interface for the Comics Liberation Front tool.'
                )
        subs = self.parser.add_subparsers()

        login_parser = subs.add_parser('login')
        login_parser.add_argument('username')
        login_parser.add_argument('password')
        login_parser.set_defaults(func=self.do_login)

        list_parser = subs.add_parser('list')
        list_parser.add_argument('series_id', nargs='?')
        list_parser.add_argument('-f', '--filter')
        list_parser.set_defaults(func=self.do_list)

        get_parser = subs.add_parser('get')
        get_parser.add_argument('issue_id')
        get_parser.add_argument('output')
        get_parser.add_argument('-u', '--update', action='store_true')
        get_parser.set_defaults(func=self.do_get)

        update_parser = subs.add_parser('update')
        update_parser.add_argument('output')
        update_parser.add_argument('-s', '--series')
        update_parser.add_argument('-m', '--metadata-only', action='store_true')
        update_parser.set_defaults(func=self.do_update)

        print_parser = subs.add_parser('print')
        print_parser.add_argument('issue_id')
        print_parser.set_defaults(func=self.do_print)

        recent_purchases_parser = subs.add_parser('recent_purchases')
        recent_purchases_parser.set_defaults(func=self.do_recent_purchases)

    def run(self):
        args = self.parser.parse_args()
        args.func(args)

    def do_login(self, args):
        account = ComicsAccount(args.username)
        account.login(args.password)
        cookie = account.get_cookie()
        with open(os.path.expanduser('~/.clf_session'), 'w') as f:
            f.write(json.dumps(cookie))

    def do_list(self, args):
        account = self._get_account()
        pattern = None
        if args.filter:
            pattern = args.filter.strip('\'" ')

        if args.series_id:
            series = account.get_series(args.series_id)
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

    def do_get(self, args):
        account = self._get_account()
        issue = account.get_issue(args.issue_id)
        print "[%s] %s" % (issue['comic_id'], get_display_title(issue))
        
        builder = cbz.CbzBuilder(account)
        out_path = args.output.strip('\'" ')
        if args.update:
            builder.update(out_path, issue)
        else:
            builder.save(out_path, issue, subscriber=CLF._print_progress)

    def do_update(self, args):
        out_path = args.output.strip('\'" ')
        library = cbz.CbzLibrary(out_path)
        account = self._get_account()
        builder = cbz.CbzBuilder(account)

        issues = account.get_all_issues(args.series)
        for issue in issues:
            prefix = "[%s] %s" % (issue['comic_id'], get_display_title(issue))
            path = library.get_issue_path(issue)
            if os.path.isfile(path):
                local_version = int(cbz.get_issue_version(path))
                remote_version = int(issue['version'])
                if remote_version > local_version:
                    print "%s: updating issue (%d[remote] > %d[local])" % (prefix, remote_version, local_version)
                    if args.metadata_only:
                        print "(metadata only)"
                        builder.update(out_path, issue)
                    else:
                        os.rename(path, path + '.old')
                        builder.save(out_path, issue, subscriber=CLF._print_progress)
                        os.remove(path + '.old')
                else:
                    print "%s: up-to-date (%d[remote] <= %d[local])" % (prefix, remote_version, local_version)
            else:
                print "%s: downloading" % prefix
                builder.save(out_path, issue, subscriber=CLF._print_progress)

    def do_print(self, args):
        account = self._get_account()
        issue = account.get_issue(args.issue_id)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(issue)

    def do_recent_purchases(self, args):
        account = self._get_account()
        purchases = account.get_recent_purchases()
        for p in purchases:
            print "[%s] %s #%s" % (p['comic_id'], p['title'], p['num'])

    def _get_account(self, path=os.path.expanduser('~/.clf_session')):
        with open(path, 'r') as f:
            cookie_str = f.read()
        cookie = json.loads(cookie_str)
        return ComicsAccount.from_cookie(cookie)

    @staticmethod
    def _print_progress(value):
        if value < 100:
            sys.stdout.write("\r%02d%%" % value)
        else:
            sys.stdout.write("\r100%\n")
        sys.stdout.flush()


if __name__ == '__main__':
    clf = CLF()
    clf.run()

