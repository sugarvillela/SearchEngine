#!/usr/bin/env python

from __future__ import print_function
import os
import requests
import json
import myutils as UT


class TextIter(object):
    # This one iterates a list or string
    def __init__(self, setText):
        # Reject bad types
        t = type(setText).__name__[0]
        if t == 'l':
            self.text = setText
        elif t == 's':
            self.text = setText.split('\n')
        else:
            self.isGood = False
            return
        # Booleans
        self.isGood = (len(self.text) >= 1)
        self.isDone = not self.isGood
        # Iterator
        self.lindex = 0  # index for lines
        self.windex = 0  # index for words
        self.line = ''   # last result from nextLine()
        self.words = []  # for line tokenizing

    def good(self):
        return self.isGood

    def done(self):
        return self.isDone

    def getAttr(self):
        return {'lines': len(self.text)}

    def getText(self):
        return self.text

    def nextLine(self):
        while True:
            if self.lindex >= len(self.text):
                self.isDone = True
                return ""
            self.line = self.text[self.lindex].strip()
            self.lindex += 1
            return self.line

    def nextWord(self):
        # return single word stripped and lowercase
        # last word returned is blank, so check done() after nextWord()
        while not len(self.words) or self.windex >= len(self.words):
            line = "\n"
            while line == '\n':
                line = self.nextLine()  # Don't strip yet
                if self.isDone:                # "" is eof, "\n" is empty line
                    return ""
            self.words = line.split()  # tokenize
            self.windex = 0  # reset line iteration
        self.windex += 1  # inc for next iteration
        return self.words[self.windex - 1].strip().lower()

    def getAll(self):
        return self.text

    def currLine(self):
        return self.line

    def lastIndex(self):
        return self.lindex - 1


class SmallFileIter(TextIter):
    # This one brings file into memory
    def __init__(self, filename, subdir=UT.defaultSubDir):
        text = UT.readall(filename, subdir)
        if text is None:
            self.isGood = False
        else:
            super(SmallFileIter, self).__init__(text)


class FileIter(TextIter):
    # This one brings file in one line at a time
    def __init__(self, filename, subdir=UT.defaultSubDir):
        filename = UT.fixPath(filename.strip(), subdir)
        self.words = []  # for line tokenizing
        self.windex = 0  # index for words
        self.fin = None
        self.line = ''
        try:
            self.fin = open(filename)
            self.isGood = True
            self.isDone = False
            # print( 'opened' );
        except IOError:
            # print( 'err' );
            self.isGood = False
            self.isDone = True

    def nextLine(self):
        # For consistency, include a wrapper for file readLine()
        # This is to override superclass TextIter's version
        self.line = "\n"
        while self.line == '\n':
            self.line = self.fin.readline()  # Don't strip yet
            if not self.line:                # "" is eof, "\n" is empty line
                self.isDone = True
                return ""
        return self.line.strip()

    def getAll(self):
        # not keeping text, so override this with safe empty list
        return []

    def getAttr(self):
        return {}


class WebDocIter(TextIter):
    # This one brings an online document into memory
    def __init__(self, url):
        text = ""

        try:
            r = requests.get(url, timeout=5)
            if r:
                text = r.text
                self.attr = r.headers
        except requests.exceptions.RequestException as e:
            if UT.verbose and e:
                print("WebDocIter: Caught: ", e)
        except KeyError:
            pass
        if len(text) > 1:
            super(WebDocIter, self).__init__(text)
        else:
            self.isGood = False
            self.attr = {}

        self.isDone = not self.isGood

    def getAttr(self):
        return self.attr


class XMLIter(object):
    # Below: Using composition rather than inheritance for more versatility.
    # Can substitute different iterators: file, url, text
    def __init__(self, setWordIter):
        """
            This is left over from a previous project that read document
            content in an xml-like format
            Needs these tags: <TEXT> </TEXT> <DOCNO> </DOCNO> with spaces
            between tag and enclosed data
        """
        self.wordIter = setWordIter
        self.currDocNum = '01'
        self.docChanged = False
        # Need a two-state machine for the doc reader
        self.read = False

    def good(self):
        return self.wordIter.good()

    def done(self):
        return self.wordIter.done()

    def getDocNum(self):
        return self.currDocNum

    def isNewDoc(self):  # cheap way of notifying clients
        if self.docChanged:
            self.docChanged = False
            return True
        return False

    def nextWord(self):
        while True:
            word = self.wordIter.nextWord()
            # case eof:  wordIter can tell blank from eof
            if self.done():
                return ''
            # case: in text, find end of text, stop reading
            elif word == "</text>":
                self.read = False
            # case: reading, in text
            elif self.read:
                return word
            # case: skipping, find new doc number
            elif word == "<docno>":
                self.docChanged = True
                self.currDocNum = self.wordIter.nextWord()
                self.read = False
            # case: skipping, find start of text, start reading
            elif word == "<text>":
                self.read = True

    def currLine(self):
        return self.wordIter.currLine()


class NGram(object):
    def __init__(self, setWordIter, n=3):
        # Using composition rather than inheritance for more versatility.
        # Can substitute different iterators: file, url, text
        self.wordIter = setWordIter
        self.N = n
        self.gram = []
        for i in range(self.N):
            self.gram.append('')

    def good(self):
        return self.wordIter.good()

    def done(self):
        return self.wordIter.done()

    def nextWord(self):
        while True:
            word = self.wordIter.nextWord()
            # Shift elements, discarding first
            for i in range(self.N - 1):
                self.gram[i] = self.gram[i + 1]
            self.gram[self.N - 1] = word
            # 'w1 w2 w3'
            return ' '.join(self.gram).strip()

    def currLine(self):
        return self.wordIter.currLine()


class DirIter(object):
    def __init__(self, fileDir, fileExt='.json', start=1):
        self.ext = fileExt
        self.dir = fileDir
        # As with UQGen, pass None to resume at a saved point
        self.uq = UT.UQGen(start)
        self.isDone = False

    def done(self):
        return self.isDone

    def nextFile(self):
        # Generates file name, opens and returns json
        # When out of files, sets done to True
        # Tolerates up to 10 skipped file names
        for i in range(10):
            filename = UT.fixPath(
                'file' + str(self.uq) + self.ext,
                self.dir
            )
            if os.path.isfile(filename):
                try:
                    with open(filename, 'r') as f:
                        return json.load(f)
                except IOError:
                    self.isDone = True
                    return {}
        self.isDone = True
        return {}
