from __future__ import print_function
# import os
# import os.path
import math                     # For log10
import json                     # For saving inverted index
import myutils as UT
import dociters as DOCS


class QueryIndex(object):
    def __init__(self, setStemmer, setText=None, setCollection=None):
        # This is a stripped down version of CollectionIndex
        # Its task is similar to CollectionIndex so inheritance is justified
        # It parses a colletion of one doc: the query
        # It needs data from a CollectionIndex to calculate
        # tfidf for query words
        self.stemmer = setStemmer
        self.text = setText
        self.collection = setCollection  # CollectionIndex for tfidf calc
        # inverted index is a 3-d default dict:  index[word][docNum][field]
        # For simpler syntax, this is accessed publicly without get method
        self.index = UT.nested_dict()
        # doc index is a 2-d dict for doc info:  docIndex[docNum][field]
        self.docIndex = UT.nested_dict()
        # parseLog stores doc collection traits: sizes, mins, maxes etc
        self.parseLog = ParseLog()
        # note: for QueryIndex, need to call parseDoc separately

    def inc(self, word, docNum):
        #   If first time saving word, create and set count to 1
        #   If word already exists in map, increment count
        if word in self.index and docNum in self.index[word]:
            self.index[word][docNum]['count'] += 1
        else:
            self.index[word][docNum]['docNum'] = docNum  # for search
            self.index[word][docNum]['count'] = 1

    def getDocFreq(self, word):
        # Number of docs in which a word occurs
        if word in self.index:
            return len(self.index[word])
        return 0

    def parseDoc(self):
        count = 0
        for dWord in self.text.split(' '):
            dWord = dWord.strip()
            if dWord and not UT.stops.isStopWord(dWord):
                count += 1
                self.inc(self.stemmer.stem(dWord), '01')

        # Do end of doc tasks
        # only one doc in query, so '01'
        self.docIndex['01']['numTerms'] = count
        self.docIndex['01']['docNum'] = '01'
        self.parseLog.logDoc(count)
        self.calcTFIDF()
        self.calcMagnitudes()
        # self.parseLog.disp();  # For debug

    def calcTFIDF(self):
        # For query, we get term freq from query, but take docFreq from
        # collection.  If word not in collection, set tf and tfidf to 0
        for word, docList in self.index.items():
            docFreq = self.collection.getDocFreq(word)
            if docFreq:
                IDF = math.log1p(
                    self.collection.parseLog.numDocsTotal / docFreq)  # 1+log e
                # node is index['word']['docNum']
                for docNum, node in docList.items():
                    node['termFreq'] = node['count'] / \
                        self.docIndex[docNum]['numTerms']
                    node['tfidf'] = node['termFreq'] * IDF
                    self.parseLog.logTFIDF(node['tfidf'])
            else:
                # node is index['word']['docNum']
                for docNum, node in docList.items():
                    node['termFreq'] = 0
                    node['tfidf'] = 0

    def calcMagnitudes(self):
        # docNode is docIndex['docNum']
        for docNum, docNode in self.docIndex.items():
            total = 0
            # doclist is index['word']
            for word, docList in self.index.items():
                # sum
                if docNum in docList:
                    tfidf = docList[docNum]['tfidf']
                    total += tfidf * tfidf
            docNode['mag'] = math.sqrt(total)

    def serialize(self, filename="index.txt"):
        with open(UT.fixPath(filename), "w") as f:
            json.dump(self.index, f)
        with open(UT.fixPath("d_" + filename), "w") as g:
            json.dump(self.docIndex, g)
        with open(UT.fixPath("n_" + filename), "w") as h:
            json.dump(str(self.parseLog.numDocsTotal), h)

    def deserialize(self, filename="index.txt"):
        with open(UT.fixPath(filename), "r") as f:
            self.index = json.load(f)
        with open(UT.fixPath("d_" + filename), "r") as g:
            self.docIndex = json.load(g)
        with open(UT.fixPath("n_" + filename), "r") as g:
            self.parseLog.numDocsTotal = int(json.load(g))


class CollectionIndex(QueryIndex):
    def __init__(self, setStemmer, fileName):
        # Build 3-d map.  This one parses document collection
        super(CollectionIndex, self).__init__(setStemmer)
        # for getting words and docNum
        self.F = DOCS.XMLIter(DOCS.FileIter(fileName))
        # parseDoc called from constructor; 1-step index build
        # (see super class)
        self.parseDoc()

    def parseDoc(self):
        currDocNum = self.F.getDocNum()
        count = 0
        while True:
            dWord = self.F.nextWord()
            if self.F.done():
                break
            if self.F.isNewDoc():
                # Do end of doc tasks
                if(count):  # keep from logging at start of file
                    self.docIndex[currDocNum]['numTerms'] = count
                    self.docIndex[currDocNum]['docNum'] = currDocNum
                    self.parseLog.logDoc(count)
                    count = 0
                # Set up new doc
                currDocNum = self.F.getDocNum()

            if not UT.stops.isStopWord(dWord):  # skip stopword
                count += 1
                self.inc(  # add or increment inverted index
                    self.stemmer.stem(dWord),  # stemmed word gets stored
                    currDocNum
                )
        # Do end of doc tasks (same as 'if' case above)
        self.docIndex[currDocNum]['numTerms'] = count
        self.docIndex[currDocNum]['docNum'] = currDocNum
        self.parseLog.logDoc(count)
        # Do end of parse tasks
        self.calcTFIDF()
        self.calcMagnitudes()
        if UT.verbose:
            self.parseLog.disp()

    def calcTFIDF(self):
        # Iterate all nodes to set termFreq and TFIDF
        for word, docList in self.index.items():
            IDF = math.log1p(self.parseLog.numDocsTotal /
                             self.getDocFreq(word))  # 1+log e
            # node is index['word']['docNum']
            for docNum, node in docList.items():
                node['termFreq'] = node['count'] / \
                    self.docIndex[docNum]['numTerms']
                node['tfidf'] = node['termFreq'] * IDF
                self.parseLog.logTFIDF(node['tfidf'])


class StoredIndex(QueryIndex):
    def __init__(self, filename="index.txt"):
        self.parseLog = ParseLog()
        self.deserialize(filename)


class ParseLog:
    # For logging statistics about collection
    # The only value needed for tfidf is numDocsTotal
    # The rest can be displayed for debug or used in further calculations
    # You could reduce document returns by filtering tfidf < (maxTFIDF/2)
    def __init__(self):
        self.numDocsTotal = 0
        self.numTermsTotal = 0
        self.minSize = 2000000000
        self.maxSize = 0
        self.minTFIDF = 2000000000
        self.maxTFIDF = 0
        self.avgTFIDF = -1

    def logDoc(self, count):
        if count < self.minSize:
            self.minSize = count
        if count > self.maxSize:
            self.maxSize = count
        self.numTermsTotal += count
        self.numDocsTotal += 1

    def logTFIDF(self, tfidf):
        if tfidf < self.minTFIDF:
            self.minTFIDF = tfidf
        if tfidf > self.maxTFIDF:
            self.maxTFIDF = tfidf
        if self.avgTFIDF == -1:
            self.avgTFIDF = tfidf
        else:
            self.avgTFIDF = (self.avgTFIDF + tfidf) / 2

    def disp(self):
        print(
            "Documents    Terms        Min Size     Max Size     Min TFIDF     Max TFIDF     Avg TFIDF"
        )
        print(
            "{:<9d}    {:<9d}    {:<9d}    {:<9d}    {:<9.8f}    {:<9.8f}    {:<9.8f}    ".format(
                self.numDocsTotal,
                self.numTermsTotal,
                self.minSize,
                self.maxSize,
                self.minTFIDF,
                self.maxTFIDF,
                self.avgTFIDF
            ))


class Vector_Model:
    def __init__(self, fileName, refresh=True):
        # If refresh set, will parse file to build inverted index
        # If refresh not set, will load json-formatted data
        # Not much difference in speed with small collection
        self.stemmer = UT.Stemmer_killPunct()
        self.lastSearch = ''
        self.resultLimit = 100
        if refresh:
            self.collection = CollectionIndex(
                self.stemmer, fileName
            )
            self.collection.serialize()
        else:
            self.collection = StoredIndex()  # deserializes json file on init

    def getResult(self):
        return self.result

    def disp(self):
        UT.dispMap(self.collection.index, 3)

    def cosineSearch(self, text):
        # For multi-word search
        # Sort if found, else set result null
        self.lastSearch = text
        # Make a small inverted index for query
        # Sets tf-idf for query terms
        Q = QueryIndex(self.stemmer, text, self.collection)
        Q.parseDoc()
        # Populate a result map
        self.rankByCosine(Q.index, Q.docIndex)
        # Any match populates docRank: sort by cosine result
        if len(self.docRank):
            self.result = list(self.docRank.values())
            self.result.sort(key=lambda x: x['cosine'], reverse=True)
        else:
            self.result = None

    def rankByCosine(self, qIndex, qDoc):
        # Implement (a dot b)/(|a||b|) for all found docs

        self.docRank = UT.nested_dict()         # docRank[docNum][field]
        mag = qDoc['01']['mag']              # magnitude of query weights
        # parse query inverted index: look for words in collection
        for qword, qdocList in qIndex.items():
            if qword in self.collection.index:
                # If we're here, the word exists in collection
                # Now parse index[word] doclist nodes and get doc
                # numbers, tfidf's
                for docNum, node in self.collection.index[qword].items():
                    # multiply found tfidf's with query tfidf's
                    vProduct = node['tfidf'] * qdocList['01']['tfidf']
                    # Add the vProduct to docRank[docNum]
                    # Use the nodes from docIndex: already calculated magnitude
                    # Copy ref to docRank list so we only use relevant docNums
                    if docNum in self.docRank:
                        self.docRank[docNum]['vProduct'] += vProduct  # add to
                    else:
                        self.docRank[docNum] = self.collection.docIndex[docNum]
                        # overwrite
                        self.docRank[docNum]['vProduct'] = vProduct
        # Finish cosine calcs: divide each inner product by magnitudes product
        for docNum, node in self.docRank.items():
            node['cosine'] = node['vProduct'] / ((node['mag'] * mag))

    def dispCosineSearch(self):
        if self.result is None:
            print("Your search - " + self.lastSearch +
                  " - did not match any documents.")
            return
        nResults = len(self.result)
        rank = 1
        if nResults > 100:
            nResults = 100
        print()
        print(
            "'" + self.lastSearch + "' returned " + str(nResults) + " results"
        )
        print("(Results in descending order of relevance)")
        print()
        print("RANK  DOC              COSINE SIMILARITY")
        print("================================================")
        for node in self.result:
            # Need an upper bound for
            if rank > self.resultLimit:
                break
            print("{:4d}  {:4s}    {:9.9f}".format(
                rank, node['docNum'], node['cosine']
            ))
            rank += 1
        print("================================================")
        print()

    def wordSearch(self, word):
        # For single word search
        # Sort if found, else set result null
        self.lastSearch = word
        word = self.stemmer.stem(word)
        if word in self.collection.index:
            self.result = list(self.collection.index[word].values())
            self.result.sort(key=lambda x: x['termFreq'], reverse=True)
        else:
            self.result = None
        self.dispWordSearch()

    def dispWordSearch(self):
        # For single word search
        if self.result is None:
            print("Your search - " + self.lastSearch +
                  " - did not match any documents.")
            return
        print()
        print("'" + self.lastSearch + "' returned " +
              str(len(self.result)) + " results")
        print("(Results in descending order of relevance)")
        print()
        print("DOC           COUNT   FREQ         TFIDF")
        print("================================================")
        for node in self.result:
            print("{:4s} {:6d}  {:9.6f}   {:9.9f}".format(
                node['docNum'], node['count'],
                node['termFreq'], node['tfidf']
            ))
        print("================================================")
        print()


class trec:
    def __init__(self, model):
        self.qList = UT.readall('query_list.txt')           # input file
        with open(UT.fixPath("qrels.txt"), "w+") as F:   # overwrite
            pass
        with open(UT.fixPath("qrels.txt"), "a+") as F:   # output file
            for q in self.qList:
                qNum, qText = self.queryPreprocess(
                    q)  # split the number and text
                print(qText)
                print(qNum)
                model.cosineSearch(qText)
                self.writeFile(model.getResult(), qNum, F)

    def queryPreprocess(self, query):
        tok = query.split('.', 1)
        return (tok[0].strip(), tok[1].strip())

    def writeFile(self, result, qNum, F):
        if result is None:
            return
        resultLimit = 100
        rank = 1
        for node in result:
            # Need an upper bound for
            if rank > resultLimit:
                break
            # < query - number > Q0 < docno > < rank > < score > Exp
            F.write("{:s} Q0 {:s} {:d} {:9.9f} Exp\r\n".format(
                qNum, node['docNum'], rank, node['cosine']
            ))
            rank += 1


def testCosineSearch():
    model = Vector_Model("ap89_collection")
    while True:
        text = input(
            "Enter 'disp', 'trec', 'q' or type a query  : "
        ).strip().lower()
        if not text:
            continue
        if text == 'q':
            break
        if text == 'disp':
            model.disp()
        elif text == 'trec':
            T = trec(model)
        else:
            model.cosineSearch(text)
            model.dispCosineSearch()
