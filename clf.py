#!/usr/bin/python
import os.path
import argparse
import cbz
from comics8 import ComicsAccount


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
        list_parser.set_defaults(func=self.do_list)

        get_parser = subs.add_parser('get')
        get_parser.add_argument('issue_id')
        get_parser.add_argument('output')
        get_parser.set_defaults(func=self.do_get)

    def run(self):
        args = self.parser.parse_args()
        args.func(args)

    def do_login(self, args):
        account = ComicsAccount(args.username)
        account.login(args.password)
        account.save(os.path.expanduser('~/.clf_session'))

    def do_list(self, args):
        account = ComicsAccount.load(os.path.expanduser('~/.clf_session'))
        if args.series_id:
            series = account.get_series(args.series_id)
            for issue in series:
                print "[%s] %s #%s: %s" % (issue['comic_id'], issue['title'], issue['num'], issue['cover'])
        else:
            collection = account.get_collection()
            for series in collection:
                print "[%s] %s (%s)" % (series['series_id'], series['title'], series['issue_count'])

    def do_get(self, args):
        account = ComicsAccount.load(os.path.expanduser('~/.clf_session'))
        issue = account.get_issue(args.issue_id)
        print "[%s] %s #%s" % (issue['comic_id'], issue['title'], issue['num'])
        
        builder = cbz.CbzBuilder(account)
        out_path = args.output.strip('\'" ')
        print "Saving issue to %s" % out_path
        builder.save(out_path, issue)



if __name__ == '__main__':
    clf = CLF()
    clf.run()

