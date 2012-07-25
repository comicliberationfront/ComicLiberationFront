import json
import urllib
import urllib2
import httplib


COMIXOLOGY_API_URL = 'https://secure.comixology.com/ios/api/{0}/{1}/?{2}'
COMIXOLOGY_API_NAMES = {
        'ios': 'com.iconology.comics',
        'android': 'com.iconology.android.comics',
        'windows8': 'com.iconology.windows.comics'
        }
COMIXOLOGY_API_VERSION = '3.0'

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

    def save(self, path):
        self._check_logged_in()

        cookie = {
                'username': self.username,
                'email': self.email,
                'password': self.password
                }
        with open(path, 'w') as f:
            f.write(json.dumps(cookie))

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
            collection.append({
                'series_id': item['series_id'],
                'title': item['title'],
                'logo': item['square_image']['scalable_representation']['url'],
                'issue_count': item['total_comics']
                })
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
            issues.append({
                'comic_id': item['issue_summary']['comic_id'],
                'series_id': item['issue_summary']['series_id'],
                'title': item['issue_summary']['title'],
                'num': item['issue_summary']['issue_num'],
                'cover': item['issue_summary']['cover_image']['scalable_representation']['url'],
                'url': item['issue_summary']['share_url']
                })
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
        issue = {
                'comic_id': item['comic_id'],
                'version': item['version'],
                'title': item['issue_info']['title'],
                'publisher': item['issue_info']['publisher']['name'],
                'series_id': item['issue_info']['series']['series_id'],
                'series_title': item['issue_info']['series']['title'],
                'num': '',
                'synopsis': item['issue_info']['synopsis'],
                'cover': item['issue_info']['cover_image']['image_descriptors'][-1]['uri'],
                'pages': []
                }
        if 'issue_num' in item['issue_info']['series']:
            issue['num'] = item['issue_info']['series']['issue_num']
        for page in item['book_info']['pages']:
            p = {
                'thumbnail': page['descriptor_set']['image_descriptors'][0]['uri'],
                'uri': page['descriptor_set']['image_descriptors'][1]['uri']
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
    def load(path):
        with open(path, 'r') as f:
            cookie_str = f.read()
        cookie = json.loads(cookie_str)
        account = ComicsAccount(cookie['username'])
        account.email = cookie['email']
        account.password = cookie['password']
        print "Loaded session for '%s' (%s)." % (account.username, account.email)
        return account

