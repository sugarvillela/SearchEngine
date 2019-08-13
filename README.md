# SearchEngine:
* Code I wrote for an Information Retrieval class in March 2019.  
* This repo isolates my contribution to this project:  https://github.com/CS172-UCR/finalproject-hookedonpythonics

## Description:
* Document ranking: Inverted index with TFIDF ranking
* URLl scraper:  Uses string manipulation to harvest URLs from web content, then follows the links
* Document Scraper:  Harvests page content without using simple html.parser module (not Beautiful Soup)
* Code to run ElasticSearch
* Simhash: Implements algorithm to decide if pages are similar
* Doc Iterators: Class hierarchy to parse various data streams
* Utilities

## Assume dependencies are installed, including:
* elasticsearch and its python client module
* NLTK porter stemmer, requests, html.parser

## To Run:
* ./app.py

## Notes:
* The folders html1, html2 and html3 normally would contain thousands of files. I include 10 each for brevity
* The stuff in html3 is not needed.  I used these files to provide snippets of un-stemmed content, but it's not a space-efficient solution.
* See Project Report for further documentation
