import os
import os.path
import urllib
import zipfile


class CbzBuilder:
    def __init__(self, account):
        self.account = account

    def save(self, out_path, issue, add_folder_structure = True, subscriber = None):
        if add_folder_structure:
            filename = ("%s %s" % (issue['title'], issue['num'])).strip()
            out_path = os.path.join(
                    out_path, 
                    issue['series_title'], 
                    "%s.cbz" % filename
                    )

        folder = os.path.dirname(out_path)
        if not os.path.exists(folder):
            os.makedirs(folder)

        print "Downloading pages..."
        page_files = []
        page_count = len(issue['pages']) + 1  # plus the cover
        if subscriber:
            subscriber(0)

        print "- cover..."
        page_files.append(os.path.join(folder, '00_cover.jpg'))
        urllib.urlretrieve(issue['cover'], page_files[-1])
        if subscriber:
            subscriber(1)

        for idx, page in enumerate(issue['pages']):
            page_num = idx + 1
            print "- %d..." % page_num
            page_files.append(os.path.join(folder, '%02d.jpg' % page_num))
            urllib.urlretrieve(page['uri'], page_files[-1])
            if subscriber:
                subscriber(page_num + 1)
            
        print "Creating CBZ: %s..." % out_path
        with zipfile.ZipFile(out_path, 'w') as zf:
            for name in page_files:
                zf.write(name, os.path.basename(name))

        print "Cleaning up..."
        for name in page_files:
            os.remove(name)

        if subscriber:
            subscriber(-1)

