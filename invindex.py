from __future__ import print_function
import os
import os.path
import math                     # For log10
import sys                      # For version number
import string                   # For punctuation
from collections import defaultdict # for auto-creating sub dicts
import json                     # For saving inverted index
from nltk.stem.porter import *  # sudo pip install nltk
import requests                 # For getting files from urls
import re                       # regular expressions

nested_dict = lambda: defaultdict(nested_dict);
verbose=True;

def disp( nested, dim, label='Disp:', spacer='' ):
    print( spacer+label );
    for key, val in nested.items():
        if dim==1:
            print( spacer+"   "+key+"="+str( val ) );
        else:
            disp( nested[key], dim-1, key, spacer+'   ' );

# Add absolute path to relative path from where code file resides
def fixPath( filename ):
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    return os.path.join(script_dir, 'textFiles1/'+filename)

# Open file, dump to list (endlines removed) and close    
def readall( filename ):
    with open( fixPath( filename ) ) as f:
        out = [line.strip() for line in f]
        return out;

# Dont want to stem? Pass a dummy stemmer to the index constructor         
class dummyStemmer:
    def stem(self, text):
        return text;

# Wrap porter stemmer with a punctuation remover        
class Stemmer_killPunct:
    def __init__( self ):
        self.stemmer=PorterStemmer();
        
    def stem(self, text):
        return self.stemmer.stem( 
            "".join(ch for ch in text if ch not in set(string.punctuation))
        );

# Abstract file ops into simple interface: good, done, nextWord        
class WordIter(object):
    def __init__(self, filename ):
        filename=fixPath( filename );
        self.words=[];
        self.index=0;
        self.fin=None;
        
        try:
            self.fin=open( filename );
            self.isGood=True;
            self.isDone=False;
        except IOError:
            self.isGood=False;
            self.isDone=True;

    def __del__(self):
        if self.isGood:
            self.fin.close();
            
    def good(self):
        return self.isGood;
        
    def done(self):
        return self.isDone;

    def nextWord(self):             #return single word stripped and lowercase
        # length=len(self.words);
        while not len(self.words) or self.index>=len(self.words) :
            line="\n";
            while line=='\n':
                line = self.fin.readline(); # Don't strip yet
                if not line:                # "" is eof, "\n" is empty line
                    self.isDone=True;
                    return "";
            self.words=line.split();        #tokenize
            self.index=0;                   #reset line iteration
        self.index+=1;                      #inc for next iteration
        return self.words[self.index-1].strip().lower();

# Use wordIter to get words, parse doc tags        
class DocIter(WordIter):
    def __init__(self, filename ):
        super(DocIter, self).__init__( filename );
        self.currDocNum='01';
        self.docChanged=False;
        # Need a two-state machine for the doc reader
        self.read=False;

    def getDocNum(self):
        return self.currDocNum;
        
    def isNewDoc(self):# cheap way of notifying clients
        if self.docChanged:
            self.docChanged=False;
            return True;
        return False;
    
    def nextWord(self):
        while True:
            word=super( DocIter, self ).nextWord();
            # case eof:  wordIter can tell blank from eof
            if self.done():         
                return '';
            # case: in text, find end of text, stop reading
            elif word=="</text>":
                self.read=False;
            # case: reading, in text
            elif self.read:
                return word;
            # case: skipping, find new doc number
            elif word=="<docno>":
                self.docChanged=True;
                self.currDocNum=super( DocIter, self ).nextWord();
                self.read=False;
            # case: skipping, find start of text, start reading
            elif word=="<text>":
                self.read=True;

class QueryIndex(object):
    def __init__(self, setStemmer, setStops, setText=None, setCollection=None ):
        # This is a stripped down version of CollectionIndex
        # Its task is similar to CollectionIndex so inheritance is justified
        # It parses a colletion of one doc: the query
        # It needs data from a CollectionIndex to calculate tfidf for query words
        self.stemmer=setStemmer;
        self.stops=setStops;            # A list, taken from a file
        self.text=setText;
        self.collection=setCollection;  # CollectionIndex for tfidf calc
        # inverted index is a 3-d default dict:  index[word][docNum][field]
        # For simpler syntax, this is accessed publicly without get method
        self.index=nested_dict();   
        # doc index is a 2-d dict for doc info:  docIndex[docNum][field]
        self.docIndex=nested_dict();    
        # parseLog stores doc collection traits: sizes, mins, maxes etc
        self.parseLog=ParseLog();
        # note: for QueryIndex, need to call parseDoc separately
        
    def isStopWord( self, word ):
        if word in self.stops:
            return True;
        else:
            return False;
            
    def inc( self, word, docNum ):
        #   If first time saving word, create and set count to 1
        #   If word already exists in map, increment count 
        if word in self.index and docNum in self.index[word]:
            self.index[word][docNum]['count']+=1;
        else:
            self.index[word][docNum]['docNum']=docNum;#for search
            self.index[word][docNum]['count']=1;

    def getDocFreq( self, word ):
        # Number of docs in which a word occurs 
        if word in self.index:
            return len( self.index[word] );
        return 0;
    
    def parseDoc(self):
        count=0;
        for dWord in self.text.split(' '):
            dWord=dWord.strip();
            if dWord and not self.isStopWord( dWord ):#skip empty and stopword  
                count+=1;
                self.inc( self.stemmer.stem( dWord.lower() ),'01' );
        
        # Do end of doc tasks
        self.docIndex['01']['numTerms']=count;  #only one doc in query, so '01'
        self.docIndex['01']['docNum']='01';
        self.parseLog.logDoc( count );
        self.calcTFIDF();
        self.calcMagnitudes();
        #self.parseLog.disp();  # For debug
        
    def calcTFIDF( self ):
        # For query, we get term freq from query, but take docFreq from 
        # collection.  If word not in collection, set tf and tfidf to 0
        for word, docList in self.index.items():
            docFreq=self.collection.getDocFreq( word );
            if docFreq:
                IDF=math.log1p( self.collection.parseLog.numDocsTotal/docFreq );#1+log e
                for docNum, node in docList.items():#node is index['word']['docNum']
                    node['termFreq']=node['count']/self.docIndex[docNum]['numTerms']
                    node['tfidf']=node['termFreq']*IDF;
                    self.parseLog.logTFIDF( node['tfidf'] );
            else:
                for docNum, node in docList.items():#node is index['word']['docNum']
                    node['termFreq']=0;
                    node['tfidf']=0;
                
    def calcMagnitudes( self ):
        # docNode is docIndex['docNum']
        for docNum, docNode in self.docIndex.items():
            total=0;
            # doclist is index['word']
            for word, docList in self.index.items():
                # sum
                if docNum in docList:
                    tfidf=docList[docNum]['tfidf'];
                    total+=tfidf*tfidf;
            docNode['mag']=math.sqrt( total );
                
    def serialize( self, filename="index.txt" ):
        with open( fixPath( filename ), "w" ) as f:
            json.dump( self.index, f );
        with open( fixPath( "d_"+filename ), "w" ) as g:
            json.dump( self.docIndex, g );
        with open( fixPath( "n_"+filename ), "w" ) as h:
            json.dump( str( self.parseLog.numDocsTotal ), h );
            
    def deserialize( self, filename="index.txt" ):
        with open( fixPath( filename ), "r") as f:
            self.index = json.load( f );
        with open( fixPath( "d_"+filename ), "r") as g:
            self.docIndex = json.load( g );
        with open( fixPath( "n_"+filename ), "r") as g:
            self.parseLog.numDocsTotal = int( json.load( g ) );
            
class CollectionIndex(QueryIndex):
    def __init__(self, setStemmer, setStops, fileName ):
        # Build 3-d map.  This one parses document collection 
        super(CollectionIndex, self).__init__( setStemmer, setStops );
        self.F=DocIter( fileName );     # for getting words and docNum
        # parseDoc called from constructor; 1-step index build (see super class)
        self.parseDoc();
            
    def parseDoc(self):
        currDocNum=self.F.getDocNum();
        count=0;
        while True:
            dWord = self.F.nextWord();
            if self.F.done():
                break;
            if self.F.isNewDoc():
                # Do end of doc tasks
                if( count ):#keep from logging at start of file
                    self.docIndex[currDocNum]['numTerms']=count;
                    self.docIndex[currDocNum]['docNum']=currDocNum;
                    self.parseLog.logDoc( count );
                    count=0;
                # Set up new doc
                currDocNum=self.F.getDocNum();
                
            if not self.isStopWord( dWord ):    #skip stopword  
                count+=1;
                self.inc(                       #add or increment inverted index
                    self.stemmer.stem(dWord),   #stemmed word gets stored
                    currDocNum 
                );
        # Do end of doc tasks (same as 'if' case above)
        self.docIndex[currDocNum]['numTerms']=count;
        self.docIndex[currDocNum]['docNum']=currDocNum;
        self.parseLog.logDoc( count );
        # Do end of parse tasks
        self.calcTFIDF();
        self.calcMagnitudes();
        if verbose:
            self.parseLog.disp();
        
    def calcTFIDF( self ):
        # Iterate all nodes to set termFreq and TFIDF 
        for word, docList in self.index.items():
            IDF=math.log1p( self.parseLog.numDocsTotal/self.getDocFreq( word ) );#1+log e
            for docNum, node in docList.items():#node is index['word']['docNum']
                node['termFreq']=node['count']/self.docIndex[docNum]['numTerms']
                node['tfidf']=node['termFreq']*IDF;
                self.parseLog.logTFIDF( node['tfidf'] );
                
class StoredIndex(QueryIndex):
    def __init__(self,filename="index.txt"):
        self.parseLog=ParseLog();
        self.deserialize( filename );

class ParseLog:
    # For logging statistics about collection
    # The only value needed for tfidf is numDocsTotal
    # The rest can be displayed for debug or used in further calculations
    # You could reduce document returns by filtering tfidf < (maxTFIDF/2)
    def __init__( self ):
        self.numDocsTotal=0;
        self.numTermsTotal=0;
        self.minSize=2000000000;
        self.maxSize=0;
        self.minTFIDF=2000000000;
        self.maxTFIDF=0;
        self.avgTFIDF=-1;
        
    def logDoc( self, count ):
        if count<self.minSize:
            self.minSize=count;
        if count>self.maxSize:
            self.maxSize=count;
        self.numTermsTotal+=count;
        self.numDocsTotal+=1;
        
    def logTFIDF( self, tfidf ):
        if tfidf<self.minTFIDF:
            self.minTFIDF=tfidf;
        if tfidf>self.maxTFIDF:
            self.maxTFIDF=tfidf;
        if self.avgTFIDF==-1:
            self.avgTFIDF=tfidf;
        else:
            self.avgTFIDF=(self.avgTFIDF+tfidf)/2;

    def disp(self):
        print(
            "Documents    Terms        Min Size     Max Size     Min TFIDF     Max TFIDF     Avg TFIDF"
        );
        print( 
            "{:<9d}    {:<9d}    {:<9d}    {:<9d}    {:<9.8f}    {:<9.8f}    {:<9.8f}    ".format(
            self.numDocsTotal, 
            self.numTermsTotal,
            self.minSize,
            self.maxSize,
            self.minTFIDF,
            self.maxTFIDF,
            self.avgTFIDF
        )); 
        
class Vector_Model:
    def __init__( self, fileName, refresh=True ):
        # If refresh set, will parse file to build inverted index
        # If refresh not set, will load json-formatted data
        # Not much difference in speed with small collection
        self.stemmer=Stemmer_killPunct();
        self.stops=readall('stoplist.txt');
        self.lastSearch='';
        self.resultLimit=100;
        if refresh:
            self.collection=CollectionIndex( self.stemmer, self.stops, fileName );
            self.collection.serialize();
        else:
            self.collection=StoredIndex();#deserializes json file on init

    def getResult( self ):
        return self.result;
        
    def disp(self):
        disp( self.collection.index, 3 );
        
    def cosineSearch(self, text ):
        # For multi-word search
        # Sort if found, else set result null
        self.lastSearch=text;
        # Make a small inverted index for query
        # Sets tf-idf for query terms
        Q=QueryIndex( self.stemmer, self.stops, text, self.collection );
        Q.parseDoc();
        # Populate a result map
        self.rankByCosine( Q.index, Q.docIndex );
        # Any match populates docRank: sort by cosine result
        if len( self.docRank ):
            self.result=list( self.docRank.values() );
            self.result.sort( key=lambda x: x['cosine'], reverse=True );
        else:
            self.result=None;
        
    def rankByCosine( self, qIndex, qDoc ):
        # Implement (a dot b)/(|a||b|) for all found docs
        
        self.docRank=nested_dict();         # docRank[docNum][field]
        mag=qDoc['01']['mag'];              # magnitude of query weights
        # parse query inverted index: look for words in collection
        for qword, qdocList in qIndex.items():
            if qword in self.collection.index:
                # If we're here, the word exists in collection
                # Now parse index[word] doclist nodes and get doc numbers, tfidf's
                for docNum, node in self.collection.index[qword].items():
                    # multiply found tfidf's with query tfidf's
                    vProduct=node['tfidf']*qdocList['01']['tfidf'];
                    # Add the vProduct to docRank[docNum]
                    # Use the nodes from docIndex: already calculated magnitude
                    # Copy ref to docRank list so we only use relevant docNums
                    if docNum in self.docRank:
                        self.docRank[docNum]['vProduct']+=vProduct  # add to
                    else:
                        self.docRank[docNum]=self.collection.docIndex[docNum];
                        self.docRank[docNum]['vProduct']=vProduct   # overwrite
        # Finish cosine calcs: divide each inner product by magnitudes product
        for docNum, node in self.docRank.items():
            node['cosine']=node['vProduct']/((node['mag']*mag));

    def dispCosineSearch(self):
        if self.result==None:
            print("Your search - "+self.lastSearch+" - did not match any documents.");
            return;
        nResults=len(self.result);
        rank=1;
        if nResults>100:
            nResults=100;
        print();
        print("'"+self.lastSearch+"' returned "+str( nResults )+" results");
        print( "(Results in descending order of relevance)"); 
        print();
        print("RANK  DOC              COSINE SIMILARITY");
        print("================================================");
        for node in self.result:
            # Need an upper bound for 
            if rank>self.resultLimit:
                break;
            print( "{:4d}  {:4s}    {:9.9f}".format(
                rank, node['docNum'], node['cosine']
            ));
            rank+=1;
        print("================================================");
        print();
        
    def wordSearch( self, word ):
        # For single word search
        # Sort if found, else set result null
        self.lastSearch=word;
        word=self.stemmer.stem(word);
        if word in self.collection.index:
            self.result=list( self.collection.index[word].values() );
            self.result.sort( key=lambda x: x['termFreq'], reverse=True );
        else:
            self.result=None;
        self.dispWordSearch();
        
    def dispWordSearch(self):
        # For single word search
        if self.result==None:
            print("Your search - "+self.lastSearch+" - did not match any documents.");
            return;
        print();
        print("'"+self.lastSearch+"' returned "+str(len(self.result))+" results");
        print( "(Results in descending order of relevance)"); 
        print();
        print("DOC           COUNT   FREQ         TFIDF");
        print("================================================");
        for node in self.result:
            print( "{:4s} {:6d}  {:9.6f}   {:9.9f}".format(
                node['docNum'], node['count'], 
                node['termFreq'], node['tfidf']
            ));
        print("================================================");
        print();
        
class trec:
    def __init__( self, model ):
        self.qList=readall('query_list.txt');           # input file
        with open( fixPath( "qrels.txt" ),"w+") as F:   # overwrite
            pass;
        with open( fixPath( "qrels.txt" ),"a+") as F:   # output file
            for q in self.qList:
                qNum, qText = self.queryPreprocess(q);  # split the number and text
                print( qText );
                print( qNum );
                model.cosineSearch( qText );
                self.writeFile( model.getResult(), qNum, F );
    
    def queryPreprocess( self, query ):
        tok=query.split( '.', 1 );
        return ( tok[0].strip(), tok[1].strip());
        
    def writeFile(self, result, qNum, F ): 
        if result==None:
            return;
        resultLimit=100;
        nResults=len(result);
        rank=1;
        for node in result:
            # Need an upper bound for 
            if rank>resultLimit:
                break;
            #< query − number > Q0 < docno > < rank > < score > Exp
            F.write( "{:s} Q0 {:s} {:d} {:9.9f} Exp\r\n".format(
                qNum, node['docNum'], rank, node['cosine']
            ));
            rank+=1;

def testCosineSearch():
    model=Vector_Model( "ap89_collection" );   
    
    while True:
        text = input("Enter 'disp', 'trec', 'q' or type a query  : ").strip().lower();
        if not text:
            continue;
        if text=='q':
            break;
        if text=='disp':
            model.disp();
        if text=='trec':
            T=trec( model );
        else:
            model.cosineSearch( text );
            model.dispCosineSearch();