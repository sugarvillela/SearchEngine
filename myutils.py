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

def dispMap( nested, dim, label='Disp:', spacer='' ):
    print( spacer+label );
    for key, val in nested.items():
        if dim==1:
            print( spacer+"   "+key+"="+str( val ) );
        else:
            dispMap( nested[key], dim-1, key, spacer+'   ' );

# Add absolute path to relative path from where code file resides
def fixPath( filename, subdir='textFiles1/' ):
    script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
    return os.path.join(script_dir, subdir+filename)

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
