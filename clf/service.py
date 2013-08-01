from cache import DummyCache


class ServiceAccount(object):
    """ The base class for a service account.
    """
    service_name = None
    service_label = None

    def __init__(self, username=None):
        self.username = username
        self.cache = DummyCache()

    def login(self, password):
        """ Logs the user into the service.
        """
        raise NotImplementedError()

    def get_cookie(self):
        """ Gets a cookie that makes it possble to log back into
            the service later.
        """
        return {
                'service': self.service_name,
                'username': self.username
                }

    def eat_cookie(self, cookie):
        """ Load a session from the given cookie.
        """
        if cookie['service'] != self.service_name:
            raise Exception("This cookie is not for a '%s' service." % self.service_label)
        self.username = cookie['username']

    def get_collection(self):
        """ Gets the metadata for all the series in the user's
            collection.
        """
        raise NotImplementedError()

    def get_issue(self, comic_id):
        collection = self.get_collection()
        for s in collection.series:
            for v in s.volumes:
                for i in v.issues:
                    if i.comic_id == comic_id:
                        return i
        return None

    def get_issue_downloader(self, issue, ctx):
        """ Gets a downloader object for the given issue.
        """
        raise NotImplementedError()

    @classmethod
    def from_cookie(cls, cookie):
        account = cls()
        account.eat_cookie(cookie)
        return account

