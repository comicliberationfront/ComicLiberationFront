import datetime
import json
import urllib
import urllib2
import urlparse
import httplib
from cache import DummyCache
from comic import Series, Issue, Page


COMIXOLOGY_API_URL = 'https://secure.comixology.com/ios/api/{0}/{1}/?{2}'
COMIXOLOGY_API_NAMES = {
        'ios': 'com.iconology.comics',
        'android': 'com.iconology.android.comics',
        'windows8': 'com.iconology.windows.comics'
        }
COMIXOLOGY_API_VERSION = '3.0'


class ComicsAccount(object):
    service_name = 'comixology'
    service_label = 'Comixology'

    def __init__(self, username, password=None, api_name='ios'):
        self.username = username
        self.password = password
        self.email = None
        self.api_name = api_name
        self.cache = DummyCache()

    @property
    def cdn(self):
        return CDN

    def login(self, password):
        print "Logging in as '%s'..." % self.username
        data = {
                'format': 'json',
                'action': 'login',
                'username': self.username,
                'password': password
                }
        req = self._make_api_request(data)
        resp = urllib2.urlopen(req)

        result = json.loads(resp.read())
        if not 'account_info' in result:
            raise Exception("Error logging in: %s" % result['error']['message'])
        self.email = result['account_info']['email']
        self.password = password

        print "...logged in as '%s' (%s)" % (
                self.username,
                self.email
                )

    def get_cookie(self):
        self._check_logged_in()

        cookie = {
                'service': ComicsAccount.service_name,
                'username': self.username,
                'password': self.password,
                'email': self.email,
                'api_name': self.api_name
                }
        return cookie

    def is_logged_in(self):
        return self.password != None

    def get_recent_purchases(self):
        self._check_logged_in()
        
        result = self.cache.get('get_recent_purchases')
        if result is None:
            data = {
                    'username': self.username,
                    'password': self.password,
                    'format': 'json',
                    'action': 'getRecentPurchases'
                    }
            req = self._make_api_request(data)
            resp = urllib2.urlopen(req)
            result = json.loads(resp.read())
            self.cache.set('get_recent_purchases', result)

        purchases = []
        for item in result['items']:
            issue = Issue()
            issue.comic_id = item['issue_summary']['comic_id']
            issue.series_id = item['issue_summary']['series_id']
            issue.title = item['issue_summary']['title']
            issue.num = item['issue_summary']['issue_num']
            issue.cover_url = item['issue_summary']['cover_image']['scalable_representation']['url']
            issue.url = item['issue_summary']['share_url']
            purchases.append(issue)
        return purchases

    def get_all_issues(self, series_id=None):
        if series_id:
            series = self.get_series(series_id)
            for i in series:
                yield self.get_issue(i['comic_id'])
        else:
            collection = self.get_collection()
            for series in collection:
                issues = self.get_series(series['series_id'])
                for i in issues:
                    yield self.get_issue(i['comic_id'])

    def get_collection(self):
        self._check_logged_in()

        result = self.cache.get('get_collection')
        if result is None:
            data = {
                    'username': self.username,
                    'password': self.password,
                    'format': 'json',
                    'action': 'getPurchasedSeries'
                    }
            req = self._make_api_request(data)
            resp = urllib2.urlopen(req)
            result = json.loads(resp.read())
            self.cache.set('get_collection', result)

        collection = []
        for item in result['items']:
            series = Series()
            series.series_id = item['series_id']
            series.title = item['title']
            series.logo_url = item['square_image']['scalable_representation']['url']
            series.issue_count = int(item['total_comics'])
            if 'volume_num' in item:
                series.volume_num = item['volume_num']
            if 'volume_title' in item:
                series.volume_title = item['volume_title']
            collection.append(series)

        return collection

    def get_series(self, series_id):
        self._check_logged_in()

        result = self.cache.get('get_series/%s' % series_id)
        if result is None:
            data = {
                    'username': self.username,
                    'password': self.password,
                    'format': 'json',
                    'action': 'getPurchasedIssuesForSeries',
                    'seriesid': series_id
                    }
            req = self._make_api_request(data)
            resp = urllib2.urlopen(req)
            result = json.loads(resp.read())
            self.cache.set('get_series_%s' % series_id, result)

        issues = []
        for item in result['items']:
            issue = Issue()
            issue.comic_id = item['issue_summary']['comic_id']
            issue.series_id = item['issue_summary']['series_id']
            issue.title = item['issue_summary']['title']
            issue.num = item['issue_summary']['issue_num']
            issue.cover_url = item['issue_summary']['cover_image']['scalable_representation']['url']
            issue.url = item['issue_summary']['share_url']
            if 'volume_num' in item['issue_summary']:
                issue.volume_num = item['issue_summary']['volume_num']
            if 'volume_title' in item['issue_summary']:
                issue.volume_title = item['issue_summary']['volume_title']
            issues.append(issue)
        return issues

    def get_issue(self, comic_id):
        self._check_logged_in()

        item = self.cache.get('get_issue/%s' % comic_id)
        if item is None:
            data = {
                    'username': self.username,
                    'password': self.password,
                    'format': 'json',
                    'action': 'getUserPurchase',
                    'item_id': comic_id
                    }
            req = self._make_api_request(data)
            resp = urllib2.urlopen(req)
            item = json.loads(resp.read())
            self.cache.set('get_issue_%s' % comic_id, item)

        item_info = item['issue_info']

        issue = Issue()
        issue.comic_id = item['comic_id']
        issue.version = item['version']
        issue.title = item_info['title']
        issue.publisher = item_info['publisher']['name']
        issue.imprint = item_info['publisher']['name']
        issue.num = ''
        issue.synopsis = item_info['synopsis']
        issue.cover_url = item_info['cover_image']['image_descriptors'][-1]['uri']
        issue.series_id = item_info['series']['series_id']
        issue.series_title = item_info['series']['title']
        issue.series_synopsis = item_info['series']['synopsis']
        issue.pages = []
        
        if 'print_publish_date' in item_info:
            issue.print_publish_date = datetime.date(
                    item_info['print_publish_date']['year'],
                    item_info['print_publish_date']['month'],
                    1
                    )
        if 'issue_num' in item_info['series']:
            issue.num = item_info['series']['issue_num']
        if 'issue_volume_title' in item_info['series']:
            issue.volume_title = item_info['series']['issue_volume_title']
        if 'issue_volume_num' in item_info['series']:
            issue.volume_num = item_info['series']['issue_volume_num']
        if 'parent' in item_info['publisher']:
            issue.publisher = item_info['publisher']['parent']['name']
        if 'creator_sections' in item_info:
            for cs in item_info['creator_sections']:
                creator_type = None
                if cs['role']['role_id'] == '2':
                    creator_type = 'writers'
                elif cs['role']['role_id'] == '3':
                    creator_type = 'artists'
                elif cs['role']['role_id'] == '4':
                    creator_type = 'pencillers'
                elif cs['role']['role_id'] == '5':
                    creator_type = 'inkers'
                if creator_type:
                    issue.creators[creator_type] = [w['name']['display'] for w in cs['creators']]
        for page in item['book_info']['pages']:
            img_desc = page['descriptor_set']['image_descriptors']
            p = Page()
            p.thumbnail_url = img_desc[0]['uri']
            p.url = img_desc[1]['uri']
            p.width = int(img_desc[1]['pixel_width'])
            p.height = int(img_desc[1]['pixel_height'])
            p.size = int(img_desc[1]['expected_content_length'])
            issue.pages.append(p)
        return issue

    def _check_logged_in(self):
        if not self.is_logged_in():
            raise Exception("You must login.")

    def _make_api_request(self, data):
        api_url = COMIXOLOGY_API_URL.format(
                COMIXOLOGY_API_NAMES[self.api_name],
                COMIXOLOGY_API_VERSION,
                urllib.urlencode(data)
                )
        req = urllib2.Request(api_url)
        return req

    @staticmethod
    def from_cookie(cookie):
        if cookie['service'] != ComicsAccount.service_name:
            raise Exception("This cookie is not for a Comixology service.")
        account = ComicsAccount(cookie['username'])
        account.email = cookie['email']
        account.password = cookie['password']
        if 'api_name' in cookie:
            account.api_name = cookie['api_name']
        else:
            account.api_name = 'windows8'
        return account


class CDN(object):
    @staticmethod
    def get_resized(url, width, height):
        comps = urlparse.urlparse(url)
        query = urlparse.parse_qs(comps.query)
        re_url = 'https://dcomixologyssl.sslcs.cdngc.net' + comps.path + '?'
        for key, val in query.iteritems():
            re_url += '%s=%s&' % (key, val[0])
        re_url += 'width=%d&height=%d' % (width, height)
        return re_url

