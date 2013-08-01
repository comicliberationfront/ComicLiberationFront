import os
import re
import requests
import simplejson as json
import os.path
from service import ServiceAccount
from comic import Collection, Series, Volume, Issue, IssueMetadata
from downloader import ArchiveIssueDownloader


DARKHORSE_API_URL = 'https://digital.darkhorse.com/api/v5/'


class DarkHorseIssueMetadata(IssueMetadata):
    def __init__(self):
        IssueMetadata.__init__(self)
        self.request_factory = None


class DarkHorseAccount(ServiceAccount):
    service_name = 'darkhorse'
    service_label = 'Dark Horse'

    def __init__(self, username=None, password=None):
        ServiceAccount.__init__(self, username)
        self.password = password
        self.friendlyname = None

    def login(self, password):
        print "Logging in as '%s'..." % self.username
        url = self._get_api_url('test_authentication')
        r = requests.get(url, auth=(self.username, password))
        r.raise_for_status()

        self.password = password
        self.friendlyname = r.text
        self.sessionid = r.headers['sessionid']
        print "...logged in as '%s'" % self.friendlyname

    def get_cookie(self):
        cookie = ServiceAccount.get_cookie(self)
        cookie.update({
                'password': self.password,
                'sessionid': self.sessionid,
                'friendlyname': self.friendlyname
                })
        return cookie

    def eat_cookie(self, cookie):
        ServiceAccount.eat_cookie(self, cookie)
        self.password = cookie['password']
        self.sessionid = cookie['sessionid']
        self.friendlyname = cookie['friendlyname']

    def get_collection(self):
        result = self.cache.get('get_collection')
        if result is None:
            url = self._get_api_url('collection/brands/')
            r = requests.get(url, params={'depth': 3}, auth=self._get_auth())
            r.raise_for_status()
            result = r.json()
            self.cache.set('get_collection', result)

        collection = Collection() 

        for item in result:
            for s in item['series']:
                series = Series()
                series.series_id = s['uuid']
                series.title = s['name']
                series.logo_url = s['cover_image']
                collection.series.append(series)

                for v in s['volumes']:
                    vol = Volume()
                    vol.title = v['name']
                    vol.volume_id = v['uuid']
                    vol.volume_num = self._extract_num(v['sort_key'])
                    vol.logo_url = v['cover_image']
                    series.volumes.append(vol)

                    for book in v['books']:
                        issue = Issue()
                        issue.comic_id = book['book_uuid']
                        issue.num = self._extract_num(book['sort_key'])
                        issue.volume_id = book['volume_uuid']
                        issue.series_id = book['series_uuid']
                        issue.title = self._trim_number(book['title'])
                        issue.cover_url = book['cover_image']
                        issue.url = book['more_info_url']
                        issue.price = book['price']

                        issue.set_metadata_loader(self._get_issue_metadata)

                        vol.issues.append(issue)

        return collection

    def _extract_num(self, sort_key):
        m = re.search('_(\d+)$', sort_key)
        if m:
            return int(str(m.group(1)))
        return None

    def _trim_number(self, title):
        m = re.search('(.*) #\d+$', title)
        if m:
            return str(m.group(1))
        return title

    def _get_issue_metadata(self, comic_id):
        item = self.cache.get('get_issue_%s' % comic_id)
        if item is None:
            url = self._get_api_url('bookmanifest/%s' % comic_id)
            r = requests.get(url, auth=self._get_auth())
            r.raise_for_status()
            item = r.json()
            self.cache.set('get_issue_%s' % comic_id, item)

        issue = IssueMetadata()
        issue.synopsis = item['description']
        #issue.version = item['version']
        issue.publisher = 'Dark Horse'
        url = self._get_api_url('book/%s' % comic_id)
        def _get_archive_request():
            return requests.get(url, auth=self._get_auth(), stream=True)
        issue.request_factory = _get_archive_request
        return issue

    def get_issue_downloader(self, issue, ctx):
        downloader = ArchiveIssueDownloader(issue, ctx)
        downloader.manifest_builder = DarkHorseAccount._get_manifest
        downloader.cleaner = DarkHorseAccount._clean_download
        return downloader

    @staticmethod
    def _get_manifest(ctx):
        folder = ctx.temp_folder
        with open(os.path.join(folder, 'manifest.json')) as fp:
            manifest = json.load(fp)
        pages = []
        for i, p in enumerate(manifest['pages']):
            src = os.path.join(folder, p['src_image'])
            dst = os.path.join(folder, '%04d.jpg' % i)
            os.rename(src, dst)
            pages.append(dst)
        return pages

    @staticmethod
    def _clean_download(ctx):
        os.remove(os.path.join(ctx.temp_folder, 'manifest.json'))
        os.remove(os.path.join(ctx.temp_folder, 'manifest.jsonp'))

    def _get_api_url(self, endpoint):
        return DARKHORSE_API_URL + endpoint

    def _get_auth(self):
        return (self.username, self.password)

