import datetime


class Series(object):
    def __init__(self, title=None):
        self.title = title
        self.series_id = None
        self.volume_num = None
        self.volume_title = None
        self.logo_url = None
        self.issue_count = 0

    @property
    def display_title(self):
        dt = self.title
        if self.volume_num:
            dt += ' Vol.%s' % self.volume_num
        if self.volume_title:
            dt += ': %s' % self.volume_title
        return dt


class Issue(object):
    def __init__(self, title=None):
        self.title = title
        self.comic_id = None
        self.series_id = None
        self.series_title = None
        self.version = None
        self.num = None
        self.volume_num = None
        self.volume_title = None
        self.cover_url = None
        self.url = None
        self.publisher = None
        self.imprint = None
        self.synopsis = None
        self.series_synopsis = None
        self.print_publish_date = None
        self.price = 0
        self.creators = {}
        self.pages = []

    def __repr__(self):
        return str(self.__dict__)

    @property
    def display_title(self):
        dt = self.title
        if self.volume_num:
            dt += ' Vol.%s' % self.volume_num
        if self.volume_title:
            dt += ': %s' % self.volume_title
        if self.num:
            dt += ' #%s' % self.num
        return dt


class Page(object):
    def __init__(self):
        self.thumbnail_url = None
        self.url = None
        self.width = 0
        self.height = 0
        self.size = 0

    def __repr__(self):
        return str(self.__dict__)

