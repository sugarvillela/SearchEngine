#!/usr/bin/env python

from __future__ import print_function
import sys                      # For version number
import myutils as UT
import dociters as ITRS
import simhash as SH

if int(sys.version[0]) > 2:  # They added a dot on version 3
    from html.parser import HTMLParser
else:
    from HTMLParser import HTMLParser


class HTMLTagHandler(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.VERBOSE = False
        self.isGood = True

        # class fields to be populated
        self.hasTitle = False
        self.data = []
        # state fields
        self.skipData = 0
        self.checkData = 0
        self.minRead = 2
        # Action tags: do something on these tags
        # These are function pointers in a map
        self.goTags = {
            'html': self.checkLang,
            'meta': self.checkUTF,
            'title': self.setTitle,
            'body': self.startBody,
        }
        # Turn off data recording during these tags
        self.skipTags = [
            'style', 'script', 'option'
        ]
        # Check length during these tags
        self.checkTags = [
            'a'
        ]

    def goodDoc(self):
        return self.isGood

    def content(self):
        return self.data

    # functions for pointers
    def checkLang(self, attrs):
        # These two functions check basic metadata from webpage
        # If not there in a good form, the page is probably bad.
        # Need exception block because some attrs have None or
        # unknown type
        try:
            if UT.nestedFind(attrs, 'lang') and not UT.nestedFind(attrs, 'en'):
                self.good = False
        except Exception as e:
            print("Caught exception: ", e)
            self.good = False

    def checkUTF(self, attrs):
        try:
            if (
                UT.nestedFind(attrs, 'charset') and not
                UT.nestedFind(attrs, 'utf-8')
            ):
                self.good = False
        except Exception as e:
            print("Caught exception: ", e)
            self.good = False

    def setTitle(self, attrs):
        if self.VERBOSE:
            print('setTitle: ', attrs)
        self.hasTitle = True

    def startBody(self, attrs):
        # There are no go tags in body
        self.goTags = {}
        self.skipData = 0
        self.checkData = 0

    # tag handlers
    def handle_starttag(self, tag, attrs):
        if self.VERBOSE:
            print("Start tag:", tag, type(attrs).__name__)
            for attr in attrs:
                print("attr:", attr)

        if tag in self.skipTags:    # int, not bool, for nested tags
            self.skipData += 1
        elif tag in self.checkTags:
            self.checkData += 1
        elif tag in self.goTags:    # if function, call it
            if attrs is None:       # More protection
                self.good = False
            else:
                self.goTags[tag](attrs)

    def handle_endtag(self, tag):
        if self.VERBOSE:
            print("End tag  :", tag)

        if tag in self.skipTags:
            self.skipData -= 1
        elif tag in self.checkTags:
            self.checkData -= 1

    def handle_data(self, data):
        if self.skipData > 0:
            return
        elif self.checkData > 0:
            data = data.strip()
            if data.count(' ') >= (self.minRead - 1):  # skip short lines
                self.data.append(data)
        else:
            self.data.append(data)

    def handle_comment(self, data):
        pass

    def handle_entityref(self, name):
        pass

    def handle_charref(self, name):
        pass

    def handle_decl(self, data):
        pass


class DocScraper(object):
    def __init__(
        self,
        setURLIter,
        maxFileBytes,
        setStemmer=UT.Stemmer_killPunct()
    ):
        self.urlIter = setURLIter
        self.stemmer = setStemmer
        self.simhash = SH.Simhash()
        # File writing
        self.writer = UT.FileWriter(True)  # True turns logging on
        self.contentWriter = UT.FileWriter()  # For unlogged content
        # Passing None makes uq resume after last uq id
        # Defeat this by saving a 1 to uqgen.txt
        # Call uq.saveState() after parseAll()
        self.uq = UT.UQGen(None)
        self.maxFile = maxFileBytes
        self.bytesWritten = 0
        # Logging
        self.badList = []
        # Current data
        self.currTitle = ""
        self.currRaw = None
        self.currContent = None
        self.procContent = None
        self.currAttr = None

    def parseOne(self, webDocIter):
        if not webDocIter.good():
            # webDocIter tries to open the url
            return False
        P = HTMLTagHandler()
        while True:
            line = webDocIter.nextLine()
            if webDocIter.done():
                break
            P.feed(line)
            if not P.goodDoc():
                # HTMLTagHandler has criteria to reject urls
                P.close()
                return False
        P.close()
        if P.hasTitle:
            # Web doc good; save content
            content = P.content()
            self.currTitle = content[0]
            self.currRaw = webDocIter.getAll()
            self.currContent = content
            self.procContent = self.processContent(content)
            self.currAttr = webDocIter.getAttr()
            return True
        return False

    def parseAll(self, setUQ=0):
        if setUQ != 0:  # Can defeat uq continuous count; reset to a value
            self.uq.reset(setUQ)

        while self.writer.sizeWritten() < self.maxFile:
            url = self.urlIter.nextLine()
            if self.urlIter.done():
                print('****urlIter.done')
                break
            print('parse url: ', url)
            if (
                not self.parseOne(ITRS.WebDocIter(url)) or
                not self.serialize(url)
            ):
                self.badList.append(url)
            print('****SIZE WRITTEN: ', self.writer.sizeWritten())
        # For dev
        print("hammings: ", self.simhash.getMinMaxHam())
        UT.disp1d(self.badList, 'badlist')
        # Uncomment to make uq resume after last uq id
        # self.uq.saveState()

    def processContent(self, content):
        # Prepare content for json encoding
        # lower case, stem
        out = []
        for line in content:
            if line:
                out.append(self.stemmer.stemLine_stops(line))
        return out

    def serialize(self, url):
        # Generate unique docNo
        docNo = str(self.uq)
        # Calculate simhash (simhash object keeps a list of duplicates)
        sig = self.simhash.parseDoc(
            ITRS.NGram(ITRS.TextIter(self.procContent)),
            docNo
        )
        if self.simhash.isDup(sig, docNo):
            return False
        # Avoid KeyError getting last-modified
        lastModified = (
            self.currAttr['last-modified']
            if 'last-modified' in self.currAttr
            else ''
        )
        obj = {
            'docno': docNo,
            'url': url,
            'simhash': sig,
            'last-modified': lastModified,
            'title': self.currTitle,
            'content': ' '.join(self.procContent)
        }
        # Write entire html doc to htmlfiles1
        self.writer.write(
            self.currRaw, 'file' + docNo + '.html', 'htmlfiles1/'
        )
        # Write obj to json for elastic search
        self.contentWriter.json(
            obj, 'file' + docNo + '.json', 'htmlfiles2/'
        )
        # Write unstemmed content to text file for snippets
        self.contentWriter.write(
            self.currContent, 'file' + docNo + '.txt', 'htmlfiles3/'
        )
        return True

    def good(self):
        return self.urlIter.good()
