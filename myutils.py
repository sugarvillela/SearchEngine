from __future__ import print_function
import os
import os.path
import sys                      # For version number
import string                   # For punctuation
from collections import defaultdict  # for auto-creating sub dicts
import json                     # For saving inverted index
from nltk.stem.porter import *  # sudo pip install nltk
import requests                 # For getting files from urls
import os                       # For file size


def nested_dict():
    return defaultdict(nested_dict)


verbose = True
defaultSubDir = 'textFiles1/'


def fixPath(filename, subdir=defaultSubDir):
    # Add absolute path to relative path from where code file resides
    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
    return os.path.join(script_dir, subdir + filename)


def readall(filename, subdir=defaultSubDir):
    # Open file, dump to list (endlines removed) and close
    try:
        with open(fixPath(filename, subdir)) as f:
            out = [line.strip() for line in f]
            return out
    except IOError:
        return None


class globalStopWordTest(object):
    # This is specific to Information Retrieval
    def __init__(self):
        self.stops = readall('stoplist.txt')
        if self.stops is None:
            raise ValueError('BAD PATH TO STOPLIST FILE')

    def isStopWord(self, word):
        return word in self.stops


stops = globalStopWordTest()


def dispMap(nested, dim, label='Disp:', spacer=''):
    # Displays key=value; indents each level
    print(spacer + label)
    for key, val in nested.items():
        if dim == 1:
            print(spacer + "   " + key + "=" + str(val))
        else:
            dispMap(nested[key], dim - 1, key, spacer + '   ')


def disp1d(lst, label='Disp:'):
    print(label, ': length =', len(lst))
    print(*lst, sep="\n")


def fileSize(filename, subdir=defaultSubDir):
    try:
        return os.stat(fixPath(filename, subdir)).st_size
    except IOError:
        return 0


def urlToFile(url, fileName):
    # Opens url, dumps to file
    # IMPORTANT: fixPath before passing fileName
    try:
        r = requests.get(url)
        if not r:
            return False
        text = r.text
        with open(fileName, "w") as f:
            f.write(text)
    except requests.exceptions.RequestException as e:
        if verbose and e:
            print("urlToFile: Caught: ", e)
        return False
    except IOError:
        if verbose:
            print("urlToFile: file error: ", fileName)
        return False
    return True


def killPunct(text):  # Remove punctuation
    return "".join(ch for ch in text if ch not in set(string.punctuation))


def nestedTypes(iList, oList):
    """
        iList is input list, oList is for output
        Populates oList like this ['t0','t1','t2'...]
    """
    t = type(iList).__name__[0]
    oList.append(t)
    if t == 'l' or t == 't' or t == 'd':  # collections recur, strings return
        for item in iList:
            nestedTypes(item, oList)
            break


def nestedFind(l1, target):  # for very small nested collections
    t1 = type(l1).__name__[0]
    if t1 == 's':
        return l1 == target
    for l2 in l1:
        if nestedFind(l2, target):
            return True
    return False


def hammingDistance_int(a, b, nBytes=4):
    mask = 1 << (nBytes * 8)
    dis = 0
    while mask:
        if (mask & a) != (mask & b):
            dis += 1
        mask = mask >> 1
    return dis


def uni(text):
    return text if isinstance(text, unicode) else text.decode('utf8')


class UQGen(object):  # see testFunction
    # class for generating unique id's as int or string with leading zeros
    # call with str(uq), int(uq), uq+0
    # Picks up where it last left off if you pass None for start
    # You need to explicitly serialize the state with saveState()
    # To use multiple instantiations with file memory, need unigue file names
    def __init__(self, start=1, strwidth=5, filename="uqgen.txt"):
        self.cur = self.getState(filename) if start is None else start
        self.width = str(strwidth)

    def gen(self):
        self.cur += 1
        return self.cur - 1

    def __int__(self):
        self.cur += 1
        return self.cur - 1

    def __str__(self):
        return ('{:0' + self.width + 'd}').format(self.gen())

    def __add__(self, offset):
        self.cur += 1
        return self.cur - 1 + offset

    def __radd__(self, offset):
        self.cur += 1
        return self.cur - 1 + offset

    def saveState(self, filename="uqgen.txt"):
        with open(fixPath(filename), "w") as f:
            f.write(str(self.cur))

    def getState(self, filename="uqgen.txt"):
        try:
            with open(fixPath(filename), "r") as f:
                return int(f.readline().strip())
        except IOError:
            return 1

    def reset(self, val=1):
        self.cur = val
        self.saveState()


class dummyStemmer:
    # strategy pattern: pass this to skip stemming
    def stem(self, text):
        return text

    def stemLine(self, text):
        return text

    def stemLine_stops(self, text):
        return text


class Stemmer_killPunct:
    # Wrap porter stemmer with a punctuation remover
    def __init__(self):
        self.stemmer = PorterStemmer()

    def stem(self, text):
        return self.stemmer.stem(killPunct(text.strip().lower()))

    def stemLine(self, line):
        # stem a whole line
        nuLine = []
        for word in line.split():
            nuLine.append(self.stem(word))
        return ' '.join(nuLine)

    def stemLine_stops(self, line):
        # stem a line, skipping stop words
        nuLine = []
        for word in line.split():
            if not stops.isStopWord(word.strip().lower()):
                nuLine.append(self.stem(word))
        return ' '.join(nuLine)


class dummyFileWriter(object):
    # strategy pattern: pass this to skip file writing
    def __init__(self, keepLog=False):
        self.keepLog = keepLog
        self.wrote = 0

    def write(self, text, filename, subdir=None):
        return 0

    def json(self, obj, filename, subdir=None):
        return 0

    def sizeWritten(self):
        return self.wrote


class FileWriter(dummyFileWriter):
    # File writer with size logging
    def write(self, text, filename, subdir=defaultSubDir):
        try:
            with open(fixPath(filename, subdir), 'w') as f:
                # dump string or list
                if type(text).__name__[0] == 's':
                    f.write(text + '\n')
                else:
                    f.write('\n'.join(str(line) for line in text))
        except IOError:
            return 0
        if self.keepLog:
            s = fileSize(filename, subdir)
            self.wrote += s
            return s
        return 0

    def json(self, obj, filename, subdir=defaultSubDir):
        try:
            with open(fixPath(filename, subdir), 'w') as f:
                json.dump(obj, f)
        except IOError:
            return 0
        if self.keepLog:
            s = fileSize(filename, subdir)
            self.wrote += s
            return s
        return 0


# Tests


def testUQGen():
    print(sys.version)
    uq = UT.UQGen()
    print(int(uq))  # 1
    print(10 + uq)  # 12
    print(uq + 10)  # 33
    print('Hey! ', uq)  # Hey! 00004
    print(str(uq))  # 00005
    print(uq)  # 00006
    uq.saveState()
    uq2 = UT.UQGen(None)
    print(uq2)  # 00007
    print(uq2)  # 00008
    uq3 = UT.UQGen()
    print(uq3)  # 00001
