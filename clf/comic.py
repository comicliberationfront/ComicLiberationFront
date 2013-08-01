

class _ParentChildList(list):
    def __init__(self, parent):
        list.__init__(self)
        self._parent = parent

    def _parent_setter(self, item, value):
        # This can be overriden if an item stores its parent
        # reference as a different attribute.
        item.parent = value

    def append(self, item):
        list.append(self, item)
        self._parent_setter(item, self._parent)

    def __setitem__(self, key, value):
        self._parent_setter(self[key], None)
        list.__setitem__(self, key, value)
        self._parent_setter(value, self._parent)

    def __delitem__(self, key):
        self._parent_setter(self[key], None)
        list.__delitem__(self, key)


class Collection(object):
    def __init__(self):
        self.series = _ParentChildList(self)

    def __iter__(self):
        for s in self.series:
            yield s

    def get_series(self, series_id):
        for s in self.series:
            if s.series_id == series_id:
                return s
        return None

    def get_issues(self):
        for s in self.series:
            for i in s.get_issues():
                yield i


class Series(object):
    def __init__(self, title=None):
        self.title = title
        self.series_id = None
        self.logo_url = None
        self.parent = None
        self.volumes = _ParentChildList(self)

    def __iter__(self):
        for v in self.volumes:
            yield v

    @property
    def volume_count(self):
        return len(self.volumes)

    @property
    def issue_count(self):
        result = 0
        for v in self.volumes:
            result += v.issue_count
        return result

    @property
    def has_unique_volume(self):
        return len(self.volumes) == 1 and self.volumes[0].is_transparent

    def get_display_title(self, volume_title_sep=None, volume_num_sep=None):
        if self.has_unique_volume:
            return self.volumes[0].get_display_title(True, volume_title_sep, volume_num_sep)
        return self.title

    def get_issues(self):
        for vol in self.volumes:
            for issue in vol.get_issues():
                yield issue


class Volume(object):
    def __init__(self, title=None):
        self.title = title
        self.volume_id = None
        self.volume_num = None
        self.logo_url = None
        self.is_transparent = False
        self._issues = None
        self._issues_loader = None
        self._preview_issue_count = None
        self.parent = None

    def __iter__(self):
        for i in self.issues:
            yield i

    @property
    def issue_count(self):
        if self._issues is None and self._preview_issue_count is not None:
            return self._preview_issue_count
        return len(self.issues)

    @property
    def issues(self):
        if self._issues is not None:
            return self._issues
        self._issues = _ParentChildList(self)
        if self._issues_loader is not None:
            loaded = self._issues_loader(self.volume_id)
            for l in loaded:
                self._issues.append(l)
        return self._issues

    def get_display_title(self, with_series_title=True, title_sep=None, num_sep=None):
        if title_sep is None:
            title_sep = ': '
        if num_sep is None:
            num_sep = ' Vol.'

        series = self.parent
        if not series:
            raise Exception("This volume is not attached to a series.")

        if with_series_title:
            dt = series.title
        else:
            dt = ''

        if self.volume_num:
            try:
                pretty_volume_num = "%02d" % int(self.volume_num)
            except ValueError:
                pretty_volume_num = self.volume_num
            dt += '%s%s' % (num_sep, pretty_volume_num)
        
        if (self.title and
                not self.title.lower().startswith(series.title.lower())):
            dt += '%s%s' % (title_sep, self.title)
        return dt

    def set_preview_issue_count(self, count):
        self._preview_issue_count = count

    def set_issue_loader(self, loader):
        if self._issues is not None:
            raise Exception("Issues have already been loaded!")
        self._issues_loader = loader

    def get_issues(self):
        return self.issues


class Issue(object):
    def __init__(self, title=None):
        self.title = title
        self.comic_id = None
        self.num = None
        self.cover_url = None
        self.url = None
        self.price = 0
        self.parent = None
        self._metadata = None
        self._metadata_loader = None

    def get_display_title(self, with_volume_title=True, volume_title_sep=None, volume_num_sep=None, title_sep=None, num_sep=None):
        if title_sep is None:
            title_sep = ' - '
        if num_sep is None:
            num_sep = ' #'

        volume = self.parent
        if not volume:
            raise Exception("This issue is not attached to a volume.")

        if with_volume_title:
            dt = volume.get_display_title(volume_title_sep, volume_num_sep)
            if self.title != volume.title:
                dt += '%s%s' % (title_sep, self.title)
        else:
            dt = self.title

        if self.num:
            try:
                pretty_num = "%02d" % int(self.num)
            except ValueError:
                pretty_num = self.num
            dt += '%s%s' % (num_sep, pretty_num)

        return dt

    @property
    def metadata(self):
        if self._metadata is None:
            if self._metadata_loader is None:
                raise Exception("No metadata loader was defined for this issue.")
            self.set_metadata(self._metadata_loader(self.comic_id))
        return self._metadata

    def set_metadata(self, metadata):
        self._metadata = metadata
        if self._metadata is not None:
            self._metadata.parent = self

    def set_metadata_loader(self, metadata_loader):
        self._metadata_loader = metadata_loader

    def get_issues(self):
        return [self]


class IssueMetadata(object):
    def __init__(self):
        self.is_volume_tpb = False
        self.version = None
        self.publisher = None
        self.imprint = None
        self.synopsis = None
        self.print_publish_date = None
        self.creators = {}

