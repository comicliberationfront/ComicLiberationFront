import json
import urllib
import urllib2
import urlparse
import httplib


COMIXOLOGY_API_URL = 'https://secure.comixology.com/ios/api/{0}/{1}/?{2}'
COMIXOLOGY_API_NAMES = {
        'ios': 'com.iconology.comics',
        'android': 'com.iconology.android.comics',
        'windows8': 'com.iconology.windows.comics'
        }
COMIXOLOGY_API_VERSION = '3.0'


def get_display_title(item):
    display_title = item['title']
    if 'volume_num' in item and item['volume_num']:
        display_title += ' Vol.%s' % item['volume_num']
    if 'volume_title' in item and item['volume_title']:
        display_title += ': %s' % item['volume_title']
    if 'num' in item and item['num']:
        display_title += ' #%s' % item['num']
    return display_title

class ComicsAccount:
    def __init__(self, username, api_name='ios'):
        self.username = username
        self.password = None
        self.email = None
        self.api_name = api_name

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

        data = {
                'username': self.username,
                'password': self.password,
                'format': 'json',
                'action': 'getRecentPurchases'
                }
        req = self._make_api_request(data)
        resp = urllib2.urlopen(req)

        purchases = []
        result = json.loads(resp.read())
        for item in result['items']:
            purchases.append({
                'comic_id': item['issue_summary']['comic_id'],
                'series_id': item['issue_summary']['series_id'],
                'title': item['issue_summary']['title'],
                'num': item['issue_summary']['issue_num'],
                'cover': item['issue_summary']['cover_image']['scalable_representation']['url'],
                'url': item['issue_summary']['share_url']
                })
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

        data = {
                'username': self.username,
                'password': self.password,
                'format': 'json',
                'action': 'getPurchasedSeries'
                }
        req = self._make_api_request(data)
        resp = urllib2.urlopen(req)

        collection = []
        result = json.loads(resp.read())
        for item in result['items']:
            series = {
                'series_id': item['series_id'],
                'title': item['title'],
                'volume_num': None,
                'volume_title': None,
                'logo': item['square_image']['scalable_representation']['url'],
                'issue_count': item['total_comics']
                }
            if 'volume_num' in item:
                series['volume_num'] = item['volume_num']
            if 'volume_title' in item:
                series['volume_title'] = item['volume_title']
            collection.append(series)

        return collection

    def get_series(self, series_id):
        self._check_logged_in()

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
        issues = []
        for item in result['items']:
            issue = {
                'comic_id': item['issue_summary']['comic_id'],
                'series_id': item['issue_summary']['series_id'],
                'title': item['issue_summary']['title'],
                'num': item['issue_summary']['issue_num'],
                'volume_num': None,
                'volume_title': None,
                'cover': item['issue_summary']['cover_image']['scalable_representation']['url'],
                'url': item['issue_summary']['share_url']
                }
            if 'volume_num' in item['issue_summary']:
                issue['volume_num'] = item['issue_summary']['volume_num']
            if 'volume_title' in item['issue_summary']:
                issue['volume_title'] = item['issue_summary']['volume_title']
            issues.append(issue)
        return issues

    def get_issue(self, comic_id):
        self._check_logged_in()

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
        item_info = item['issue_info']
        issue = {
                'comic_id': item['comic_id'],
                'version': item['version'],
                'title': item_info['title'],
                'publisher': item_info['publisher']['name'],
                'imprint': item_info['publisher']['name'],
                'num': '',
                'synopsis': item_info['synopsis'],
                'cover': item_info['cover_image']['image_descriptors'][-1]['uri'],
                'print_publish_date': item_info['print_publish_date'],
                'series_id': item_info['series']['series_id'],
                'series_title': item_info['series']['title'],
                'series_synopsis': item_info['series']['synopsis'],
                'pages': []
                }
        if 'issue_num' in item_info['series']:
            issue['num'] = item_info['series']['issue_num']
        if 'parent' in item_info['publisher']:
            issue['publisher'] = item_info['publisher']['parent']['name']
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
                    issue[creator_type] = [w['name']['display'] for w in cs['creators']]
        for page in item['book_info']['pages']:
            img_desc = page['descriptor_set']['image_descriptors']
            p = {
                'thumbnail': img_desc[0]['uri'],
                'uri': img_desc[1]['uri'],
                'width': img_desc[1]['pixel_width'],
                'height': img_desc[1]['pixel_height'],
                'size': img_desc[1]['expected_content_length']
                }
            issue['pages'].append(p)
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
        account = ComicsAccount(cookie['username'])
        account.email = cookie['email']
        account.password = cookie['password']
        if 'api_name' in cookie:
            account.api_name = cookie['api_name']
        else:
            account.api_name = 'windows8'
        print "Loaded session for '%s' (%s)." % (account.username, account.email)
        return account

class CDN:
    @staticmethod
    def get_resized(url, width, height):
        comps = urlparse.urlparse(url)
        query = urlparse.parse_qs(comps.query)
        re_url = 'https://dcomixologyssl.sslcs.cdngc.net' + comps.path + '?'
        for key, val in query.iteritems():
            re_url += '%s=%s&' % (key, val[0])
        re_url += 'width=%d&height=%d' % (width, height)
        return re_url

