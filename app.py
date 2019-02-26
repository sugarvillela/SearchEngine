#!/usr/bin/env python
 
from __future__ import print_function
import os
import os.path
import sys                      # For version number

import invindex as INV
import myutils as UT
import urlscraper as URL

port = os.getenv('PORT', '8080')
host = os.getenv('IP', '0.0.0.0')

def menu():
    prompt='Outer Menu: Choose a test to run\n'\
        '{:15s}  1  \n'\
        '{:15s}  2  \n'.format('Inverted Index','URL Scraper');
    return input(prompt).strip().lower();

def main():
    print(sys.version);
    while True:
        text = menu();
        if not text:
            continue;
        print();
        if text=='q':
            break;
        elif text=='1':
            INV.testCosineSearch();
        elif text=='2':
            URL.testUrlScraper();
        else:
            break;
    print();
    #URL.testUrlScraper();
    

if __name__ == '__main__':
	main();


