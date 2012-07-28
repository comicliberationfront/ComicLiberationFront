import os
import os.path
import urllib
import zipfile
import re
import string

valid_path_chars = "-_.() /\\%s%s" % (string.ascii_letters, string.digits)

def _clean_path(path):
    return re.sub('[^\w\d &\-_\.\(\)/\\\\]', '-', path)


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

    def build_issue_path(self, series_title, issue_title, issue_num):
        if not issue_num:
            filename = "%s.cbz" % issue_title
        else:
            filename = "%s %02d.cbz" % (issue_title, int(issue_num))
        return os.path.join(self.root_path, series_title, filename)


class CbzBuilder:
    def __init__(self, account):
        self.account = account

    def save(self, out_path, issue, add_folder_structure = True, subscriber = None):
        if add_folder_structure:
            lib = CbzLibrary(out_path)
            out_path = lib.build_issue_path(issue['series_title'], issue['title'], issue['num'])

        temp_folder = os.path.join(os.path.dirname(out_path), '__clf_download', issue['comic_id'])
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        print "Downloading pages..."
        page_files = []
        page_count = len(issue['pages']) + 1  # plus the cover
        if subscriber:
            subscriber(0)

        page_files.append(os.path.join(temp_folder, '00_cover.jpg'))
        urllib.urlretrieve(issue['cover'], page_files[-1])
        if subscriber:
            subscriber(100.0 / page_count)

        for idx, page in enumerate(issue['pages']):
            page_num = idx + 1
            page_files.append(os.path.join(temp_folder, '%02d.jpg' % page_num))
            urllib.urlretrieve(page['uri'], page_files[-1])
            if subscriber:
                subscriber(100.0 * (page_num + 1) / page_count)
            
        print "Creating CBZ: %s..." % out_path
        with zipfile.ZipFile(out_path, 'w') as zf:
            for name in page_files:
                zf.write(name, os.path.basename(name))

        print "Cleaning up..."
        for name in page_files:
            os.remove(name)
        os.rmdir(temp_folder)

        if subscriber:
            subscriber(100)

