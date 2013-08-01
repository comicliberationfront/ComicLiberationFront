import datetime
import json
import urllib
import urllib2
import urlparse
import logging
from service import ServiceAccount
from comic import Collection, Series, Volume, Issue, IssueMetadata
from downloader import PagesIssueDownloader


COMIXOLOGY_API_URL = 'https://secure.comixology.com/ios/api/{0}/{1}/?{2}'
COMIXOLOGY_API_NAMES = {
        'ios': 'com.iconology.Comics',
        'android': 'com.iconology.android.comics',
        'windows8': 'com.iconology.windows.comics'
        }
COMIXOLOGY_API_VERSION = '3.0'


class IssuePage(object):
    def __init__(self):
        self.thumbnail_url = None
        self.url = None
        self.width = 0
        self.height = 0
        self.size = 0

    def __repr__(self):
        return str(self.__dict__)


class ComixologyIssueMetadata(IssueMetadata):
    def __init__(self):
        IssueMetadata.__init__(self)
        self.pages = []


class ComicsAccount(ServiceAccount):
    service_name = 'comixology'
    service_label = 'Comixology'

    def __init__(self, username=None, password=None, api_name='ios'):
        ServiceAccount.__init__(self, username)
        self.password = password
        self.email = None
        self.api_name = api_name
        self.logger = logging.getLogger(__name__)

    @property
    def cdn(self):
        return CDN

    def login(self, password):
        self.logger.info("Logging in as '%s'..." % self.username)
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

        self.logger.info("...logged in as '%s' (%s)" % (
                self.username,
                self.email
                ))

    def get_cookie(self):
        self._check_logged_in()

        cookie = ServiceAccount.get_cookie(self)
        cookie.update({
                'password': self.password,
                'email': self.email,
                'api_name': self.api_name
                })
        return cookie

    def eat_cookie(self, cookie):
        ServiceAccount.eat_cookie(self, cookie)
        self.email = cookie['email']
        self.password = cookie['password']
        if 'api_name' in cookie:
            self.api_name = cookie['api_name']
        else:
            self.api_name = 'windows8'

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

        collection = Collection()

        for item in result['items']:
            series = Series()
            series.title = item['title']
            series.series_id = item['series_id']
            collection.series.append(series)

            vol = Volume()
            vol.title = item['title']
            vol.volume_id = item['series_id']
            vol.is_transparent = True
            if 'volume_title' in item:
                vol.title = item['volume_title']
            if 'volume_num' in item:
                vol.volume_num = item['volume_num']
            vol.logo_url = item['square_image']['scalable_representation']['url']
            
            vol.set_preview_issue_count(int(item['total_comics']))
            vol.set_issue_loader(self._get_issues)

            series.volumes.append(vol)

        return collection
    
    def _get_issues(self, series_id):
        self._check_logged_in()

        result = self.cache.get('get_series_%s' % series_id)
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
            issue.title = item['issue_summary']['title']
            issue.num = item['issue_summary']['issue_num']
            issue.cover_url = item['issue_summary']['cover_image']['scalable_representation']['url']
            issue.url = item['issue_summary']['share_url']
            if 'usd_price_in_cents' in item['issue_summary']:
                issue.price = int(item['issue_summary']['usd_price_in_cents']) / 100.0
            issue.set_metadata_loader(self._get_issue_metadata)
            issues.append(issue)
        return issues

    def _get_issue_metadata(self, comic_id):
        self._check_logged_in()

        item = self.cache.get('get_issue_%s' % comic_id)
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

        issue = ComixologyIssueMetadata()
        issue.version = item['version']
        issue.synopsis = item_info['synopsis']

        issue.publisher = item_info['publisher']['name']
        issue.imprint = item_info['publisher']['name']
        if 'parent' in item_info['publisher']:
            issue.publisher = item_info['publisher']['parent']['name']

        if 'print_publish_date' in item_info:
            issue.print_publish_date = datetime.date(
                    item_info['print_publish_date']['year'],
                    item_info['print_publish_date']['month'],
                    1
                    )

        #if 'issue_num' in item_info['series']:
        #    issue.num = item_info['series']['issue_num']
        if 'issue_volume_num' in item_info['series']:
        #    issue.num = item_info['series']['issue_volume_num']
            issue.is_volume_tpb = True

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
            p = IssuePage()
            p.thumbnail_url = img_desc[0]['uri']
            p.url = img_desc[1]['uri']
            p.width = int(img_desc[1]['pixel_width'])
            p.height = int(img_desc[1]['pixel_height'])
            p.size = int(img_desc[1]['expected_content_length'])
            issue.pages.append(p)

        return issue

    def get_issue_downloader(self, issue, ctx):
        downloader = PagesIssueDownloader(issue, ctx)
        return downloader

    def _check_logged_in(self):
        if self.password == None:
            raise Exception("You must login.")

    def _make_api_request(self, data):
        api_url = COMIXOLOGY_API_URL.format(
                COMIXOLOGY_API_NAMES[self.api_name],
                COMIXOLOGY_API_VERSION,
                urllib.urlencode(data)
                )
        req = urllib2.Request(api_url)
        return req


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

