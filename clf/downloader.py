import os.path
import urllib
import logging
import tarfile


class DownloadProgress(object):
    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger
        self.progress_offset = 0
        self.progress_total = 100

    def set_progress_limits(self, offset=0, total=100):
        self.progress_offset = offset
        self.progress_total = total

    def progress(self, value, message=None):
        value = value * self.progress_total / 100 + self.progress_offset
        value = min(100, value)
        value = max(0, value)
        self._doProgress(value, message)

    def error(self, message):
        self.logger.error(message)

    def warning(self, message):
        self.logger.warning(message)

    def info(self, message):
        self.logger.info(message)

    def debug(self, message):
        self.logger.debug(message)

    def _doProgress(self, value, message=None):
        raise NotImplementedError()


class NullDownloadProgress(DownloadProgress):
    def progress(self, value, message=None):
        pass


class DownloadContext(object):
    def __init__(self, temp_folder, subscriber=None):
        self.temp_folder = temp_folder
        if subscriber is None:
            subscriber = NullDownloadProgress()
        self.subscriber = subscriber
        self.pages = []


class IssueDownloader(object):
    def __init__(self, issue, ctx):
        self.issue = issue
        self.ctx = ctx

    def download(self):
        raise NotImplementedError()

    def cleanup(self):
        pass


class PagesIssueDownloader(IssueDownloader):
    def __init__(self, issue, ctx):
        IssueDownloader.__init__(self, issue, ctx)
        if not hasattr(issue.metadata, 'pages'):
            raise Exception("No pages have been defined on the issue metadata.")

    def download(self):
        page_count = len(self.issue.metadata.pages)
        try:
            for idx, page in enumerate(self.issue.metadata.pages):
                page_num = idx + 1
                page_file = os.path.join(self.ctx.temp_folder, '%04d.jpg' % page_num)
                urllib.urlretrieve(page.url, page_file)
                self.ctx.pages.append(page_file)
                self.ctx.subscriber.progress(100.0 * page_num / page_count, message="Downloading pages...")
            self.ctx.subscriber.progress(100)
        except Exception as e:
            message = "Couldn't download pages: %s" % e
            self.ctx.subscriber.error(message)
            return

class ArchiveIssueDownloader(IssueDownloader):
    def __init__(self, issue, ctx):
        IssueDownloader.__init__(self, issue, ctx)
        if not hasattr(issue.metadata, 'request_factory'):
            raise Exception("No archive URL was defined on the issue metadata.")
        self.manifest_builder = None
        self.cleaner = None

    def download(self):
        if not self.manifest_builder:
            raise Exception("No manifest builder was defined on this downloader.")

        progress = 0
        r = self.issue.metadata.request_factory()
        r.raise_for_status()
        content_length = int(r.headers['content-length'])
        temp_file = os.path.join(self.ctx.temp_folder, 'archive.tar')
        with open(temp_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=(content_length / 9)):
                self.ctx.subscriber.progress(progress, message="Downloading archive...")
                if progress <= 90:
                    progress += 10
                f.write(chunk)

        self.ctx.subscriber.progress(90, message="Extracting archive...")
        with tarfile.open(temp_file) as archive:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(archive, self.ctx.temp_folder)

        self.ctx.subscriber.progress(95, message="Building manifest...")
        self.ctx.pages = self.manifest_builder(self.ctx)

        self.ctx.subscriber.progress(100)

    def cleanup(self):
        os.remove(os.path.join(self.ctx.temp_folder, 'archive.tar'))
        if self.cleaner:
            self.cleaner(self.ctx)

