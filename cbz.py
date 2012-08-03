import os
import os.path
import urllib
import zipfile
import re
import string
import json
import comicrack
import comicbookinfo


valid_path_chars = "-_.() /\\%s%s" % (string.ascii_letters, string.digits)

def _clean_path(path):
    return re.sub('[^\w\d &\-_\.\(\)/\\\\]', '-', path)


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


class CbzLibrary:
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
        if not issue['title'] or not issue['series_title']:
            raise Exception("Can't build comic path without a title for the issue and series.")

        if not issue['num']:
            filename = "%s.cbz" % issue['title']
        else:
            filename = "%s %02d.cbz" % (issue['title'], int(issue['num']))
        filename = _clean_path(filename)
        
        dirname = _clean_path(issue['series_title'])
        if 'volume_num' in issue and issue['volume_num']:
            dirname += '%sVolume %02d' % (os.sep, int(issue['volume_num']))
            if 'volume_title' in issue and issue['volume_title']:
                dirname += ' - %s' % _clean_path(issue['volume_title'])
        elif 'volume_title' in issue and issue['volume_title']:
            dirname += '%s%s' % (os.sep, _clean_path(issue['volume_title']))
        
        return os.path.join(self.root_path, dirname, filename)


class CbzBuilder:
    def __init__(self, account):
        self.account = account

    def update(self, out_path, issue, add_folder_structure = True):
        if add_folder_structure:
            lib = CbzLibrary(out_path)
            out_path = lib.get_issue_path(issue)

        print "Re-creating metadata..."
        ci, cbi = self._get_metadata(issue)

        print "Updating CBZ: %s..." % out_path
        os.rename(out_path, out_path + '.old')
        with zipfile.ZipFile(out_path + '.old', 'a') as zfin:
            with zipfile.ZipFile(out_path, 'w') as zfout:
                for info in zfin.infolist():
                    if info.filename == 'ComicInfo.xml':
                        zfout.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
                    else:
                        zfout.writestr(info, zfin.read(info.filename))
                zfout.comment = cbi.get_json_str()

        print "Cleaning up..."
        os.remove(out_path + '.old')


    def save(self, out_path, issue, add_folder_structure = True, subscriber = None):
        if add_folder_structure:
            lib = CbzLibrary(out_path)
            out_path = lib.get_issue_path(issue)

        temp_folder = os.path.join(os.path.dirname(out_path), '__clf_download', issue['comic_id'])
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        print "Creating metadata..."
        ci, cbi = self._get_metadata(issue)

        print "Downloading pages..."
        page_files = []
        page_count = len(issue['pages']) + 1  # plus the cover
        if subscriber:
            subscriber(0)

        page_files.append(os.path.join(temp_folder, '0000_cover.jpg'))
        urllib.urlretrieve(issue['cover'], page_files[-1])
        if subscriber:
            subscriber(100.0 / page_count)

        for idx, page in enumerate(issue['pages']):
            page_num = idx + 1
            page_files.append(os.path.join(temp_folder, '%04d.jpg' % page_num))
            urllib.urlretrieve(page['uri'], page_files[-1])
            if subscriber:
                subscriber(100.0 * (page_num + 1) / page_count)

        if subscriber:
            subscriber(100)
            
        print "Creating CBZ: %s..." % out_path
        with zipfile.ZipFile(out_path, 'w') as zf:
            zf.writestr('ComicInfo.xml', unicode(str(ci), 'utf-8'))
            for name in page_files:
                zf.write(name, os.path.basename(name))
            zf.comment = cbi.get_json_str()

        print "Cleaning up..."
        try:
            for name in page_files:
                os.remove(name)
            os.rmdir(temp_folder)
        except Exception as e:
            print "Error while cleaning up: %s" % e
            print "The comic has however been successfully downloaded."

    def _get_metadata(self, issue):
        ci = comicrack.ComicInfo.from_issue(issue)
        ci.notes = "Tool: ComicLiberationFront/0.1.0, Owner: %s" % self.account.username

        cbi = comicbookinfo.ComicBookInfo.from_issue(issue)
        cbi.extra['x-ComicLiberationFront'] = {
                'owner': self.account.username,
                'version': issue['version']
                }
        return (ci, cbi)

