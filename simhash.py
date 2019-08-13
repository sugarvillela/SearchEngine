#!/usr/bin/env python

from __future__ import print_function
import sys                      # For version number
import myutils as UT
import dociters as DOCS
import binascii                 # For crc32


class Simhash:
    def __init__(self, setStemmer=UT.dummyStemmer(), numBytes=4):
        self.stemmer = setStemmer
        self.numBytes = numBytes
        self.hashList = []
        self.hamList = []
        self.dupList = []
        self.dupThresh = 4  # hamming distance where doc considered a duplicate
        self.minHam = 1000000
        self.maxHam = 0

    def parseDoc(self, F, docNum):
        """
            F is a wordIter or DocItr or NGram generator from docIters
        """
        if not F or not F.good():
            print('Simhash: bad file')
            return

        # Make a list of hashed N-grams from document
        curList = []
        while True:
            dWord = F.nextWord()
            if F.done():
                break
            curList.append(binascii.crc32(bytes(dWord, 'utf-8')))

        # compare bits in each hash to build simhash for document
        mask = 1 << (self.numBytes * 8)  # 0x80000000
        out = 0
        while mask:                     # mask/=2 each iteration until 0
            total = 0                    # for tallying bit comparisons
            for h in curList:           # same bit for every hash in list
                if((h & mask) != 0):      # bit is 1
                    total += 1
                else:                   # bit is 0
                    total -= 1

            if total >= 0:                # convert pos to 1, neg to 0
                out |= mask
            mask = mask >> 1               # shift to check next bit

        # save current result to list for later check
        self.hashList.append((docNum, out))  # Save result
        return out

    def isDup(self, checkMe, docNo):
        for h in self.hashList:
            if h[0] == docNo:  # skip own simhash
                continue
            ham = UT.hammingDistance_int(h[1], checkMe)

            # for dev: need min and max ham to guess dupThresh
            if ham < self.minHam:
                self.minHam = ham
            elif ham > self.maxHam:
                self.maxHam = ham

            if ham <= self.dupThresh:
                print('isDup', h[1], docNo)
                return True
        return False

    def setDups(self):
        # Make hamlist from stored hashes, then make dupList based on that
        # You can use the dupList to delete dup documents in collection:
        # Compare hamming distance of all files, save to hamList
        # Generates n choose k results, where n=len(hashList) and k=2
        # Then copy doc numbers to dupList, if hamming distance is less than
        # dupThreshold.
        self.hamList = []
        for i in range(len(self.hashList) - 1):
            for j in range(i + 1, len(self.hashList)):  # avoids checking self
                ham = UT.hammingDistance_int(
                    self.hashList[i][1], self.hashList[j][1])

                # for dev: need min and max ham to guess dupThresh
                if ham < self.minHam:
                    self.minHam = ham
                elif ham > self.maxHam:
                    self.maxHam = ham

                self.hamList.append(
                    (
                        self.hashList[i][0],
                        self.hashList[j][0],
                        ham
                    ))
        self.dupList = [tup[1]
                        for tup in self.hamList if tup[2] < self.dupThresh]
        self.dupList = list(set(self.dupList))

    def getHashList(self):
        return self.hashList

    def getHamList(self):
        return self.hamList

    def getDupList(self):
        return self.dupList

    def getMinMaxHam(self):
        return (self.minHam, self.maxHam)

    def disp(self):
        print('Hashlist: (docNumber, simhash)')
        print(*self.hashList, sep="\n")
        print('Hamlist: (docNumber1, docNumber2, hammingDistance)')
        print(*self.hamList, sep="\n")
        print('Duplist: docNumber')
        print(*self.dupList, sep="\n")


def testSimHash():
    print(sys.version)
    H = Simhash()
    H.parseDoc(DOCS.NGram(DOCS.SmallFileIter('file00001.txt ')), '01')
    H.parseDoc(DOCS.NGram(DOCS.SmallFileIter('file00002.txt ')), '02')
    H.parseDoc(DOCS.NGram(DOCS.SmallFileIter('file00003.txt ')), '03')
    H.parseDoc(DOCS.NGram(DOCS.SmallFileIter('file00004.txt ')), '04')
    H.parseDoc(DOCS.NGram(DOCS.SmallFileIter('file00005.txt ')), '05')
    H.setDups()
    H.disp()
