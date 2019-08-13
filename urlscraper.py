#!/usr/bin/env python

from __future__ import print_function
import requests
import myutils as UT


class urlFinder(object):
    # Base class for finding urls in page
    # This one creates list and explores one page at a time
    def __init__(self, types, skips, maxSize):
        # types is a list of what is wanted: like .edu or .gov
        # skips is a list of what is not wanted: like .gif or .pdf
        # maxSize is how many urls you want to collect
        self.maxSize = maxSize
        self.types = types
        self.skips = skips
        self.newUrls = []
        self.urls = []
        self.sizeChanged = 0
        self.lastLinkBad = False
        self.dupRatio = -1

    def disp(self):
        print("Found {} good links".format(len(self.urls)))
        print("Dup ratio removed: ", self.dupRatio)
        for u in self.urls:
            print(u)

    def full(self):
        # May go over by one page worth, since self.urls is only updated
        # when a page is finished
        return (len(self.urls) > self.maxSize)

    def badLink(self):
        # True if the last link explored gave an error
        # Gets updated on every parseOne() call
        return self.lastLinkBad

    def foundLinks(self):
        # Treat this as a boolean, or see how many links were found
        # Gets updated on every parseOne() call
        return self.sizeChanged

    def urlFix(self, url):
        # Fix or standardize most urls that could cause errors
        if url[:4] == 'http' and not ('www' in url):
            return url
        if UT.verbose and not ('www' in url):  # too much output
            print("fixing: ", url)
        errs = ['www.', '//', 'www,']
        for err in errs:
            index = url.find(err)
            if index != -1:
                return 'http://' + url[index + len(err):]
        return 'http://' + url

    def isText(self, url):
        # Skip unwanted file types in url
        for skip in self.skips:
            if skip in url:
                if UT.verbose:
                    print("Caught unwanted type: ", skip)
                return False

        # Catch bad links, bad https certificates, any requests error
        try:
            header = requests.head(url, allow_redirects=True, timeout=5)
            contentType = header.headers.get('content-type')

            # Catch incomplete doc
            if not contentType:
                if UT.verbose:
                    print("Caught no content type: ", url)
                return False

            # Catch non text
            contentType = contentType.lower()
            if ('text' in contentType or 'html' in contentType):
                return True
            else:
                if UT.verbose:
                    print("Caught non-text type: ", url)
                return False
        except requests.exceptions.RequestException as e:
            if UT.verbose and e:
                print("Caught exception: ", e)
        return False

    # below: functions for parsing single url page and adding urls to list
    def parseOne(self, url):
        # clear list for storing new urls
        self.newUrls = []
        # Discover bad url
        if not (url and self.isText(url)):
            self.lastLinkBad = True
            return
        r = requests.get(url, timeout=5)
        if not r:
            self.lastLinkBad = True
            return
        self.lastLinkBad = False
        # locate hrefs in html
        text = r.text
        i = text.find('href=', 0)
        while i != -1 and i < len(text):
            start, end, bad = self.getQuoted(i + 5, text)
            if bad:
                break
            self.addIfRelevant(text[start:end].strip())
            i = text.find('href=', end)
        # remove duplicates
        self.rmNewDups()
        # log whether we found any new urls
        self.sizeChanged = len(self.newUrls)
        # combine new with existing
        self.urls.extend(self.newUrls)

    def getQuoted(self, start, text):
        # Given a string index < a quote, returns first quoted text found
        # Works with single and double quotes
        while start < len(text) and text[start] != '"' and text[start] != "'":
            start += 1
        quote = text[start]
        end = start = start + 1
        while end < len(text) and text[end] != quote:
            end += 1
        bad = (end >= len(text) or start >= len(text))
        return (start, end, bad)

    def addIfRelevant(self, utext):
        # drop mail links etc
        if not ("http" in utext or "www" in utext):
            return
        # drop links not specified in constraint list
        for typ in self.types:
            if typ in utext:
                # Fix improper links now, before adding to list
                utext = self.urlFix(utext)
                self.newUrls.append(utext)
                return

    def rmNewDups(self):
        # Remove duplicates from url list and calculate fraction of removed
        oldLen = len(self.newUrls)
        if oldLen == 0:
            return
        self.newUrls = list(set(self.newUrls))
        ratio = (oldLen - len(self.newUrls)) / oldLen
        # Since this is updated on parseOne(), need to average the dupRatio
        if self.dupRatio == -1:
            self.dupRatio = ratio
        else:
            self.dupRatio = (self.dupRatio + ratio) / 2

    def rmAllDups(self):
        # If appending to an existing list with a new seedlist, may need to
        # get rid of dups in the final list
        oldLen = len(self.urls)
        if oldLen == 0:
            return
        self.urls = list(set(self.urls))
        self.dupRatio = (oldLen - len(self.urls)) / oldLen


class urlScraper(urlFinder):
    def __init__(self, types, skips, maxSize):
        # set up list and types
        super(urlScraper, self).__init__(types, skips, maxSize)
        self.badList = []
        self.deadEnds = []

    def parseAll(self, seedlist):
        # This calls parseOne() again and again
        # until we run out of links to follow (which won't happen) or until
        # maxSize is reached.
        # Keep in mind when setting maxSize that there may be up to 1/3
        # duplicate links. We remove dups as we go, but the actual number
        # of urls may vary
        self.urls = seedlist
        i = 0
        progress = 0
        while i < len(self.urls) and not self.full():
            if UT.verbose and progress % 5 == 0:
                print("parsed ", progress, " pages")
            progress += 1
            self.parseOne(self.urls[i])
            if self.badLink():
                self.badList.append(self.urls[i])
            elif not self.foundLinks():
                self.deadEnds.append(self.urls[i])
            i += 1
        # Finish up:
        self.dispParse()  # for dev
        self.rmAllDups()
        self.badList = list(set(self.badList))
        self.deadEnds = list(set(self.deadEnds))
        self.dispFinal()  # for dev

    def dispParse(self):
        if not UT.verbose:
            return
        print('urls len =', len(self.urls))
        print('Dup ratio within pages =', self.dupRatio)

    def dispFinal(self):
        if not UT.verbose:
            return
        print('Dup ratio between pages =', self.dupRatio)
        print('Collected {} urls, of {} assigned'.format(
            len(self.urls), self.maxSize))
        if len(self.badList):
            print('Disp bad urls')
            for u in self.badList:
                print(u)
        else:
            print('No bad urls')
        if len(self.badList):
            print('Disp dead ends')
            for u in self.deadEnds:
                print(u)
        else:
            print('No dead ends')

    def serialize(self, filename="urllist.txt"):
        with open(UT.fixPath(filename), "w") as f:
            for u in self.urls:
                if not (u in self.badList or u in self.deadEnds):
                    f.write(u + '\n')
                elif UT.verbose:
                    print('Serialize skipped: ', u)

    def deserialize(self, filename="urllist.txt"):
        self.urls = []
        with open(UT.fixPath(filename), "r") as f:
            self.urls = [line.rstrip('\n') for line in f]


def testUrlScraper(numUrls=50):
    # You can specify how many you are trying to collect
    # Because of removed duplicates, actual amount will be lower

    # Starter urls: more variety here gives more variety in result
    seedlist = [
        "https://universityofcalifornia.edu/",
        "https://calstate.edu/",
        "https://calbaptist.edu/"
    ]
    # Here you can specify the things you want and don't want
    followTypes = ['.edu']
    skips = ['.pdf', '.ico', '.png']

    # Probably don't want to display on big runs
    U = urlScraper(followTypes, skips, numUrls)
    U.parseAll(seedlist)
    U.serialize()
    U.disp()
