import json
from datetime import datetime


class ComicBookInfo(object):
    @staticmethod
    def from_issue(issue):
        cbi = ComicBookInfo()
        if issue.metadata.version:
            cbi.last_modified = datetime.strptime(
                    issue.metadata.version,
                    '%Y%m%d%H%M%S'
                    )
        cbi.series = issue.parent.get_display_title()
        cbi.title = issue.title
        cbi.publisher = issue.metadata.publisher
        cbi.comments = issue.metadata.synopsis
        if issue.num:
            cbi.issue = issue.num
        if issue.parent.volume_num:
            cbi.volume = issue.parent.volume_num
        if issue.metadata.print_publish_date:
            cbi.publication_month = issue.metadata.print_publish_date.month
            cbi.publication_year = issue.metadata.print_publish_date.year
        if 'writers' in issue.metadata.creators:
            cbi.writers = issue.metadata.creators['writers']
        if 'pencillers' in issue.metadata.creators:
            cbi.pencillers = issue.metadata.creators['pencillers']
        if 'inkers' in issue.metadata.creators:
            cbi.inkers = issue.metadata.creators['inkers']
        if 'artists' in issue.metadata.creators:
            cbi.artists = issue.metadata.creators['artists']
        return cbi

    def __init__(self, title='', issue=-1):
        self.app_id = 'ComicLiberationFront'
        self.last_modified = datetime.now
        self.series = title
        self.title = title
        self.publisher = ''
        self.publication_month = -1
        self.publication_year = -1
        self.issue = -1
        self.volume = -1
        self.writers = []
        self.pencillers = []
        self.inkers = []
        self.artists = []
        self.comments = ''
        self.extra = {}

    def save(self, path):
        data = self.get_json_data()
        with open(path, 'w') as f:
            json.dump(data, f)

    def get_json_str(self):
        data = self.get_json_data()
        return json.dumps(data)

    def get_json_data(self):
        data = {
                'appID': self.app_id,
                'lastModified': str(self.last_modified),
                'ComicBookInfo/1.0': {
                    'series': self.series,
                    'title': self.title,
                    'publisher': self.publisher,
                    'publicationMonth': self.publication_month,
                    'publicationYear': self.publication_year,
                    'issue': self.issue,
                    'volume': self.volume,
                    'credits': [],
                    'comments': self.comments
                    }
                }
        for w in self.writers:
            data['ComicBookInfo/1.0']['credits'].append({
                'person': w,
                'role': 'Writer'
                })
        for a in self.artists:
            data['ComicBookInfo/1.0']['credits'].append({
                'person': a,
                'role': 'Artist'
                })
        for p in self.pencillers:
            data['ComicBookInfo/1.0']['credits'].append({
                'person': p,
                'role': 'Penciller'
                })
        for i in self.inkers:
            data['ComicBookInfo/1.0']['credits'].append({
                'person': i,
                'role': 'Inker'
                })
        for k, v in self.extra.iteritems():
            data[k] = v
        return data
        
