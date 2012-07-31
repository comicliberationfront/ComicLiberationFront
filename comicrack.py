import string
from lxml import etree


class ComicInfo:
    @staticmethod
    def from_issue(issue):
        ci = ComicInfo()
        ci.title = issue['title']
        ci.series = issue['series_title']
        if issue['num']:
            ci.number = issue['num']
        ci.summary = issue['synopsis']
        ci.year = issue['print_publish_date']['year']
        ci.month = issue['print_publish_date']['month']
        if 'writers' in issue:
            ci.writers = issue['writers']
        if 'pencillers' in issue:
            ci.pencillers = issue['pencillers']
        if 'inkers' in issue:
            ci.inkers = issue['inkers']
        if 'artists' in issue:
            if not ci.pencillers:
                ci.pencillers = []
            if not ci.inkers:
                ci.inkers = []
            for a in issue['artists']:
                ci.pencillers.append(a)
                ci.inkers.append(a)
        ci.publisher = issue['publisher']
        ci.imprint = issue['imprint']
        ci.web = 'http://www.comixology.com/digital-comic/%s' % issue['comic_id']
        for i, p in enumerate(issue['pages']):
            pi = PageInfo(i)
            pi.size = p['size']
            pi.width = p['width']
            pi.height = p['height']
            ci.pages.append(pi)

        return ci


    def __init__(self, title='', number=-1):
        self.title = title
        self.series = title
        self.number = number
        self.volume = -1
        self.alternate_series = ''
        self.summary = ''
        self.notes = ''
        self.year = -1
        self.month = -1
        self.writers = []
        self.pencillers = []
        self.inkers = []
        self.colorists = []
        self.letterers = []
        self.cover_artists = []
        self.editors = []
        self.publisher = ''
        self.imprint = ''
        self.web = ''
        self.characters = []
        self.teams = []
        self.locations = []
        self.pages = []

    def save(self, path):
        dom = self.get_xml_dom()
        with open(path, 'w') as f:
            f.write(etree.tostring(
                dom,
                xml_declaration=True,
                pretty_print=True
                ))
        
    def get_xml_dom(self):
        root = etree.Element('ComicInfo')
        if self.title:
            etree.SubElement(root, 'Title').text = self.title
        if self.series:
            etree.SubElement(root, 'Series').text = self.series
        if self.number >= 0:
            etree.SubElement(root, 'Number').text = str(self.number)
        if self.volume >= 0:
            etree.SubElement(root, 'Volume').text = str(self.volume)
        if self.alternate_series:
            etree.SubElement(root, 'AlternateSeries').text = self.alternate_series
        if self.summary:
            etree.SubElement(root, 'Summary').text = self.summary
        if self.notes:
            etree.SubElement(root, 'Notes').text = self.notes
        if self.year >= 0:
            etree.SubElement(root, 'Year').text = str(self.year)
        if self.month >= 0:
            etree.SubElement(root, 'Month').text = str(self.month)
        if self.writers:
            etree.SubElement(root, 'Writer').text = string.join(self.writers, ', ')
        if self.pencillers:
            etree.SubElement(root, 'Penciller').text = string.join(self.pencillers, ', ')
        if self.inkers:
            etree.SubElement(root, 'Inker').text = string.join(self.inkers, ', ')
        if self.colorists:
            etree.SubElement(root, 'Colorist').text = string.join(self.colorists, ', ')
        if self.letterers:
            etree.SubElement(root, 'Letterer').text = string.join(self.letterers, ', ')
        if self.cover_artists:
            etree.SubElement(root, 'CoverArtist').text = string.join(self.cover_artists, ', ')
        if self.editors:
            etree.SubElement(root, 'Editor').text = string.join(self.editors, ', ')
        if self.publisher:
            etree.SubElement(root, 'Publisher').text = self.publisher
        if self.imprint:
            etree.SubElement(root, 'Imprint').text = self.imprint
        if self.web:
            etree.SubElement(root, 'Web').text = self.web
        if self.pages:
            etree.SubElement(root, 'PageCount').text = str(len(self.pages))
        if self.characters:
            etree.SubElement(root, 'Characters').text = string.join(self.characters, ', ')
        if self.teams:
            etree.SubElement(root, 'Teams').text = string.join(self.teams, ', ')
        if self.locations:
            etree.SubElement(root, 'Locations').text = string.join(self.locations, ', ')

        pages_root = etree.SubElement(root, 'Pages')
        for page in self.pages:
            page_element = etree.SubElement(pages_root, 'Page')
            if page.number >= 0:
                page_element.set('Image', str(page.number))
            if page.size > 0:
                page_element.set('ImageSize', str(page.size))
            if page.width > 0:
                page_element.set('ImageWidth', str(page.width))
            if page.height > 0:
                page_element.set('ImageHeight', str(page.height))
            if page.type:
                page_element.set('Type', page.type)

        return root


class PageInfo:
    FRONT_COVER = 'FrontCover'
    INNER_COVER = 'InnerCover'
    ROUNDUP = 'Roundup'
    STORY = 'Story'
    ADVERTISEMENT = 'Advertisement'
    EDITORIAL = 'Editorial'
    LETTERS = 'Letters'
    PREVIEW = 'Preview'
    BACK_COVER = 'BackCover'
    OTHER = 'Other'
    DELETED = 'Deleted'

    def __init__(self, number=-1, type=''):
        self.number = number
        self.size = -1
        self.width = -1
        self.height = -1
        self.type = type

