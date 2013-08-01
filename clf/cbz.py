import os
import os.path
import shutil
import zipfile
import re
import string
import json
import logging
import comicrack
import comicbookinfo
from downloader import DownloadContext


valid_path_chars = "-_.() /\\%s%s" % (string.ascii_letters, string.digits)


def _clean_path(path):
    path = re.sub('[^\w\d &\-_\.\(\)\'/\\\\]', '-', path)
    path = string.strip(path, '-.')
    return path


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
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing CBZ library at '%s'." % root_path)

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
        volume = issue.parent
        series = volume.parent
        path = _clean_path(series.title)
        if issue.metadata.is_volume_tpb:
            vdt = volume.get_display_title(True, ' - ', ' Vol.')
            path += os.sep + _clean_path(vdt) + '.cbz'
        else:
            vdt = volume.get_display_title(False, ' - ', 'Vol.')
            path += os.sep + _clean_path(vdt)
            issue_dt = issue.get_display_title(False, ' - ', ' Vol.', ' ', ' ')
            path += os.sep + _clean_path(issue_dt)
            path += '.cbz'
        return os.path.join(self.root_path, path)

    def sync_issues(self, builder, issues, 
            metadata_only=False, 
            new_only=False,
            force=False):
        for i, issue in enumerate(issues):
            prefix = "[%s] %s" % (issue.comic_id, issue.get_display_title())
            path = self.get_issue_path(issue)
            if os.path.isfile(path):
                if new_only:
                    continue
                do_sync = False
                do_sync_reason = None
                if force:
                    do_sync = True
                    do_sync_reason = 'forced'
                else:
                    local_version = int(get_issue_version(path))
                    remote_version = int(issue.metadata.version)
                    if remote_version > local_version:
                        do_sync = True
                        do_sync_reason = '%d[remote] > %d[local]' % (remote_version, local_version)
                    else:
                        do_sync_reason = '%d[remote] <= %d[local]' % (remote_version, local_version)

                if do_sync:
                    self.logger.info("%s: syncing issue (reason: %s)" % (prefix, do_sync_reason))
                    if metadata_only:
                        builder.update(issue, in_library=self)
                    else:
                        os.rename(path, path + '.old')
                        builder.save(issue, in_library=self)
                        os.remove(path + '.old')
                else:
                    self.logger.info("%s: up-to-date (%s)" % (prefix, do_sync_reason))
            elif not metadata_only:
                self.logger.info("%s: downloading (new)" % prefix)
                builder.save(issue, in_library=self)


class CbzBuilder(object):
    def __init__(self, service, username=None, subscriber=None, temp_folder=None):
        self.service = service
        self.username = username
        self.subscriber = subscriber
        self.temp_folder = temp_folder

    def update(self, issue, out_path=None, in_library=None):
        if out_path is None:
            if in_library is not None:
                out_path = in_library.get_issue_path(issue)
            else:
                raise Exception("You must specify either an output path or a library.")

        self.subscriber.progress(value=0, message="Re-creating metadata...")
        ci, cbi = self._get_metadata(issue)

        self.subscriber.progress(value=30, message=("Updating CBZ: %s..." % out_path))
        os.rename(out_path, out_path + '.old')
        with zipfile.ZipFile(out_path + '.old', 'a') as zfin:
            with zipfile.ZipFile(out_path, 'w') as zfout:
                for info in zfin.infolist():
                    if info.filename == 'ComicInfo.xml':
                        zfout.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
                    else:
                        zfout.writestr(info, zfin.read(info.filename))
                zfout.comment = cbi.get_json_str()

        self.subscriber.progress(value=60, message="Cleaning up...")
        os.remove(out_path + '.old')
        self.subscriber.progress(value=100)

    def save(self, issue, out_path=None, in_library=None):
        if out_path is None:
            if in_library is not None:
                out_path = in_library.get_issue_path(issue)
            else:
                raise Exception("You must specify either an output path or a library.")

        temp_folder = self.temp_folder
        if temp_folder is None:
            temp_folder = os.path.dirname(out_path)
        temp_folder = os.path.join(temp_folder, 'dltmp', self.service.service_name, issue.comic_id)
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        out_dir = os.path.dirname(out_path)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        self.subscriber.progress(value=0, message="Creating metadata...")
        ci, cbi = self._get_metadata(issue)

        self.subscriber.progress(value=5, message="Downloading pages...")
        self.subscriber.set_progress_limits(5, 85)
        ctx = DownloadContext(temp_folder, self.subscriber)
        downloader = self.service.get_issue_downloader(issue, ctx)
        downloader.download()
        self.subscriber.set_progress_limits(0, 100)

        self.subscriber.progress(90, "Creating CBZ: %s" % out_path)
        try:
            temp_out_path = os.path.join(temp_folder, 'comic.cbz')
            with zipfile.ZipFile(temp_out_path, 'w') as zf:
                zf.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
                for name in ctx.pages:
                    zf.write(name, os.path.basename(name))
                zf.comment = cbi.get_json_str()
            shutil.copyfile(temp_out_path, out_path)
        except Exception as e:
            message = ("Couldn't create CBZ file: %s" % e)
            self.subscriber.error(message)
            return

        self.subscriber.progress(95, "Cleaning up...")
        try:
            for name in ctx.pages:
                os.remove(name)
            downloader.cleanup()
            os.remove(temp_out_path)
            os.rmdir(temp_folder)
        except Exception as e:
            message = ("Error while cleaning up: %s\nThe comic has however been successfully downloaded." % e)
            self.subscriber.error(message)

        self.subscriber.progress(value=100, message=("Issue downloaded to: %s" % out_path))


    def _get_metadata(self, issue):
        ci_notes = "Tool: ComicLiberationFront/0.1.0\n"
        cbi_extra = {
                'version': issue.metadata.version
                }
        if self.service:
            ci_notes += "Service: %s\n" % self.service.service_name
            cbi_extra['service'] = self.service.service_name
        if self.username:
            ci_notes += "Owner: %s\n" % self.username
            cbi_extra['owner'] = self.username

        ci = comicrack.ComicInfo.from_issue(issue)
        ci.notes = ci_notes

        cbi = comicbookinfo.ComicBookInfo.from_issue(issue)
        cbi.extra['x-ComicLiberationFront'] = cbi_extra

        return (ci, cbi)

