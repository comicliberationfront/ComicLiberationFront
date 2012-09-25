import os
import os.path
import shutil
import urllib
import zipfile
import re
import string
import json
import comicrack
import comicbookinfo


valid_path_chars = "-_.() /\\%s%s" % (string.ascii_letters, string.digits)

def _clean_path(path):
    return re.sub('[^\w\d &\-_\.\(\)\'/\\\\]', '-', path)


def get_issue_version(path):
    with zipfile.ZipFile(path, 'r') as zf:
        if not zf.comment:
            return -1
        cbi = json.loads(zf.comment)
    if not 'x-ComicLiberationFront' in cbi:
        return -1
    if not 'version' in cbi['x-ComicLiberationFront']:
        return -1
    return cbi['x-ComicLiberationFront']['version']


class CbzLibrary(object):
    def __init__(self, root_path):
        self.root_path = root_path

    def get_series_names(self):
        root, dirs, files = os.walk(self.root_path)
        return dirs

    def get_issue_names(self, series_name):
        series_path = os.path.join(self.root_path, series_name)
        if not os.path.isdir(series_path):
            return None
        root, dirs, files = os.walk(series_path)
        return files

    def get_issue_path(self, issue):
        if not issue.title or not issue.series_title:
            raise Exception("Can't build comic path without a title for the issue and series.")

        path = _clean_path(issue.series_title)
        if issue.is_volume_tpb:
            path += os.sep + _clean_path(issue.get_display_title(' ', ' - ')) + '.cbz'
        else:
            vdt = issue.get_volume_display_title(' - ')
            if vdt is not None:
                path += os.sep + _clean_path(issue.series_title + ' ' + vdt)
            path += os.sep + _clean_path(issue.get_display_title(' ', ' - ')) + '.cbz'
        return os.path.join(self.root_path, path)

    def sync_issues(self, builder, issues, 
            metadata_only=False, 
            force=False,
            subscriber=None):
        for i, issue in enumerate(issues):
            prefix = "[%s] %s" % (issue.comic_id, issue.display_title)
            path = self.get_issue_path(issue)
            if os.path.isfile(path):
                do_sync = False
                do_sync_reason = None
                if force:
                    do_sync = True
                    do_sync_reason = 'forced'
                else:
                    local_version = int(get_issue_version(path))
                    remote_version = int(issue.version)
                    if remote_version > local_version:
                        do_sync = True
                        do_sync_reason = '%d[remote] > %d[local]' % (remote_version, local_version)
                    else:
                        do_sync_reason = '%d[remote] <= %d[local]' % (remote_version, local_version)

                if do_sync:
                    if subscriber is not None:
                        subscriber(message="%s: syncing issue (reason: %s)" % (prefix, do_sync_reason))
                    if metadata_only:
                        builder.update(issue, in_library=self)
                    else:
                        os.rename(path, path + '.old')
                        builder.save(issue, in_library=self)
                        os.remove(path + '.old')
                else:
                    if subscriber is not None:
                        subscriber(message="%s: up-to-date (%s)" % (prefix, do_sync_reason))
            elif not metadata_only:
                if subscriber is not None:
                    subscriber(message="%s: downloading (new)" % prefix)
                builder.save(issue, in_library=self)


class CbzBuilder(object):
    def __init__(self):
        self.username = None
        self.service = None
        self.subscriber = None
        self.temp_folder = None

    def set_watermark(self, service, username):
        self.service = service
        self.username = username

    def set_progress_subscriber(self, subscriber):
        self.subscriber = subscriber

    def set_temp_folder(self, temp_folder):
        self.temp_folder = temp_folder

    def update(self, issue, out_path=None, in_library=None):
        if out_path is None:
            if in_library is not None:
                out_path = in_library.get_issue_path(issue)
            else:
                raise Exception("You must specify either an output path or a library.")

        if self.subscriber is not None:
            self.subscriber(value=0, message="Re-creating metadata...")
        ci, cbi = self._get_metadata(issue)

        if self.subscriber is not None:
            self.subscriber(value=30, message=("Updating CBZ: %s..." % out_path))
        os.rename(out_path, out_path + '.old')
        with zipfile.ZipFile(out_path + '.old', 'a') as zfin:
            with zipfile.ZipFile(out_path, 'w') as zfout:
                for info in zfin.infolist():
                    if info.filename == 'ComicInfo.xml':
                        zfout.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
                    else:
                        zfout.writestr(info, zfin.read(info.filename))
                zfout.comment = cbi.get_json_str()

        if self.subscriber is not None:
            self.subscriber(value=60, message="Cleaning up...")
        os.remove(out_path + '.old')
        if self.subscriber is not None:
            self.subscriber(value=100)


    def save(self, issue, out_path=None, in_library=None):
        if out_path is None:
            if in_library is not None:
                out_path = in_library.get_issue_path(issue)
            else:
                raise Exception("You must specify either an output path or a library.")

        temp_folder = self.temp_folder
        if temp_folder is None:
            temp_folder = os.path.dirname(out_path)
        temp_folder = os.path.join(temp_folder, '__clf_download', issue.comic_id)
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        out_dir = os.path.dirname(out_path)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        if self.subscriber:
            self.subscriber(value=0, message="Creating metadata...")
        ci, cbi = self._get_metadata(issue)

        if self.subscriber:
            self.subscriber(value=0, message="Downloading pages...")
        page_files = []
        page_count = len(issue.pages)
        try:
            for idx, page in enumerate(issue.pages):
                page_num = idx + 1
                page_files.append(os.path.join(temp_folder, '%04d.jpg' % page_num))
                urllib.urlretrieve(page.url, page_files[-1])
                if self.subscriber:
                    self.subscriber(value=(100.0 * (page_num + 1) / (page_count + 2)))
        except Exception as e:
            message = ("Couldn't download pages: %s" % e)
            if self.subscriber:
                self.subscriber(error=message)
            return

        if self.subscriber:
            self.subscriber(value=(100.0 * page_count / (page_count + 2)), message=("Creating CBZ: %s" % out_path))
        try:
            temp_out_path = os.path.join(temp_folder, 'comic.cbz')
            with zipfile.ZipFile(temp_out_path, 'w') as zf:
                zf.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
                for name in page_files:
                    zf.write(name, os.path.basename(name))
                zf.comment = cbi.get_json_str()
            shutil.copyfile(temp_out_path, out_path)
        except Exception as e:
            message = ("Couldn't create CBZ file: %s" % e)
            if self.subscriber:
                self.subscriber(error=message)
            return

        if self.subscriber:
            self.subscriber(value=(100.0 * (page_count + 1) / (page_count + 2)), message="Cleaning up...")
        try:
            for name in page_files:
                os.remove(name)
            os.remove(temp_out_path)
            os.rmdir(temp_folder)
        except Exception as e:
            message = ("Error while cleaning up: %s\nThe comic has however been successfully downloaded." % e)
            if self.subscriber:
                self.subscriber(error=message)

        if self.subscriber:
            self.subscriber(value=100)


    def _get_metadata(self, issue):
        ci_notes = "Tool: ComicLiberationFront/0.1.0\n"
        cbi_extra = {
                'version': issue.version
                }
        if self.service:
            ci_notes += "Service: %s\n" % self.service
            cbi_extra['service'] = self.service
        if self.username:
            ci_notes += "Owner: %s\n" % self.username
            cbi_extra['owner'] = self.username

        ci = comicrack.ComicInfo.from_issue(issue)
        ci.notes = ci_notes

        cbi = comicbookinfo.ComicBookInfo.from_issue(issue)
        cbi.extra['x-ComicLiberationFront'] = cbi_extra

        return (ci, cbi)

