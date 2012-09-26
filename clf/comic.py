import datetime
import string


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
            try:
                pretty_volume_num = "%02d" % int(self.volume_num)
            except ValueError:
                pretty_volume_num = self.volume_num
            dt += ' Vol.%s' % pretty_volume_num
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
        self.is_volume_tpb = False
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
        return self.get_display_title()

    def get_display_title(self, num_sep=' #', vol_sep=': ', title_sep=' - '):
        dt = self.series_title
        vdt = self.get_volume_display_title(vol_sep)
        if vdt is not None:
            dt += ' ' + vdt.lstrip()
        if self.title != self.series_title:
            dt += title_sep + self.title
        if self.num:
            try:
                pretty_num = "%02d" % int(self.num)
            except ValueError:
                pretty_num = self.num
            dt += '%s%s' % (num_sep, pretty_num)
        return dt

    @property
    def volume_display_title(self):
        return self.get_volume_display_title()

    def get_volume_display_title(self, vol_sep=': '):
        if self.volume_num:
            try:
                pretty_volume_num = "%02d" % int(self.volume_num)
            except ValueError:
                pretty_volume_num = self.volume_num
            dt = 'Vol.%s' % pretty_volume_num
            if self.volume_title:
                dt += '%s%s' % (vol_sep, self.volume_title)
            return dt
        elif self.volume_title:
            return '%s%s' % (vol_sep, self.volume_title)
        else:
            return None

    @property
    def series_display_title(self):
        dt = self.series_title
        vdt = self.volume_display_title
        if vdt is not None:
            dt += ' ' + vdt
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

