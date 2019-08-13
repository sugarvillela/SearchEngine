#!/usr/bin/env python3

from __future__ import print_function
import os
import os.path
import sys                      # For version number
import urlscraper
import dociters
import docscraper as DOC
import simhash
import elastic

# path: cd Desktop/School/2019Win/172/myProj
# path: cd Downloads/elasticsearch-6.6.2/bin$ ./elasticsearch
# view index:  http://localhost:9200/english/sentences/

# To activate this project's virtualenv, run pipenv shell.
# Alternatively, run a command inside the virtualenv with pipenv run.


port = os.getenv('PORT', '8080')
host = os.getenv('IP', '0.0.0.0')


def menu():
    prompt = 'Outer Menu: Choose a test to run:  \n'\
        '{:15s}  1  \n'\
        '{:15s}  2  \n'\
        '{:15s}  3  \n'\
        '{:15s}  4  \n'\
        '{:15s}  5  \n'.format(
            'URL Scraper',
            'Web Scraper',
            'Build Index',
            'Search',
            'Simhash'
        )
    return input(prompt).strip().lower()


def promptInt(prompt):
    val = input(prompt).strip().lower()
    if not val:
        return 0
    return int(val)


def main():
    print(sys.version)
    print('=============')

    while True:
        text = menu()
        if not text:
            continue
        if text == 'q':
            break

        elif text == '1':  # url scrape
            n = promptInt('How many urls do you want to collect?  ')
            urlscraper.testUrlScraper(n)

        elif text == '2':  # web scrape
            n = promptInt('How many bytes do you want to collect?  ')
            D = DOC.DocScraper(
                dociters.FileIter('urllist.txt'), n
            )
            if D.good():
                print('D good')
                D.parseAll(1)
            print('done')

        elif text == '3':  # Build
            print('Building...')
            elastic.buildIndex()

        elif text == '4':  # Search
            S = elastic.WebIndex()
            while True:
                text = input('Enter Query: ').strip().lower()
                if not text:
                    continue
                if text == 'q':
                    break
                S.search(text)
                S.dispSearchResult()

        elif text == '5':  # Simhash
            simhash.testSimHash()
        else:
            break
        print()


if __name__ == '__main__':
    main()
