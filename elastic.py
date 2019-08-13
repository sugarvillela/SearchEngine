from __future__ import print_function

from elasticsearch import Elasticsearch

import dociters as ITRS
import myutils as UT

es = Elasticsearch()
indexName = 'webindex'


def buildIndex():
    jget = ITRS.DirIter('htmlfiles2/')
    print('Building Index...')
    for i in range(10000000):
        doc = jget.nextFile()
        if jget.done():
            print('Done: Loaded', i, 'documents')
            break
        if i % 100 == 0:
            print('Loaded', i, 'documents')
        es.index(index=indexName, doc_type="web",
                 id=doc['docno'], body=doc)
    print('Build Index done')


def deleteIndex():
    es.indices.delete(index='english')


class WebIndex(object):
    def __init__(self, setStemmer=UT.Stemmer_killPunct()):
        self.stemmer = setStemmer
        self.MaxResults = 100   # limit elastic search results
        self.htmlDir = 'htmlfiles3/'
        self.lastSearch = ''
        self.stemmedQuery = ''   # query with all words stemmed
        self.result = None
        self.numHits = 0

    def search(self, query):
        self.lastSearch = query
        self.stemmedQuery = self.stemmer.stemLine_stops(query)
        print('***' + self.stemmedQuery + '***')
        if not len(self.stemmedQuery):
            return False
        query_format = {
            "query": {"match": {'content': self.stemmedQuery}},
            "terminate_after": self.MaxResults
        }
        res = es.search(index=indexName, body=query_format)
        self.numHits = res['hits']['total']
        if self.numHits:
            self.result = []
            for r in res['hits']['hits']:
                snip = self.bestSnip(
                    self.findSnips('file' + r['_id'] + '.txt')
                )
                self.result.append(
                    {
                        'url': r['_source']['url'],
                        'docno': r['_id'],
                        'snip': snip
                    }
                )

    def dispSearchResult(self):
        if self.numHits == 0:
            print("Your search - " + self.lastSearch +
                  " - did not match any documents.")
            return
        print()
        print("'" + self.lastSearch + "' returned " +
              str(self.numHits) + " results")
        print()
        print("DOC     URL")
        print("================================================")
        for r in self.result:
            print("{}   {}".format(
                r['docno'], r['url']
            ))
            print("     {}".format(
                r['snip']
            ))
            print()
        print("================================================")
        print()

    def findSnips(self, filename):
        # Locate words in content that are in query
        # Get lines where words are found
        # Remove duplicates
        snips = []
        F = ITRS.SmallFileIter(filename, self.htmlDir)
        if not F.good():
            print('bad file name:', filename)
            return []
        while True:
            dWord = F.nextWord()
            if F.done():
                return snips
            dWord = dWord.strip().lower()
            if (
                len(dWord) < 3 or
                UT.stops.isStopWord(dWord)
            ):
                continue
            dWord = self.stemmer.stem(dWord)
            if dWord in self.stemmedQuery:
                line = F.currLine()
                pos = line.lower().find(dWord)
                if pos != -1:
                    snips.append(
                        (line, pos)
                    )
                    snips = list(set(snips))
            return snips

    def bestSnip(self, snips):
        # Find longest snippet
        # Truncate to 5 words before and 5 words after found word
        if not len(snips):
            # should never happen unless filenames got changed
            return '...'
        snips.sort(key=lambda x: len(x[0]), reverse=True)
        line, pos = snips[0]
        lo = line[:pos].split()
        hi = line[pos:].split()
        out = []

        loIndex = max(len(lo) - 5, 0)
        for i in range(loIndex, len(lo)):
            out.append(lo[i])

        hiIndex = min(len(hi), 10 - (len(lo) - loIndex))
        for i in range(0, hiIndex):
            out.append(hi[i])
        if len(out):
            return '...' + ' '.join(out) + '...'
        else:
            return '...'
