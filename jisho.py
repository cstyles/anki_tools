#!/usr/bin/env python3

import requests
import sys
import re
import html.parser
import argparse
import romkan
import os



def myprint(level, *args):
    if False:
        print('  ' * level, *args)



def convert(mylist):
    if len(mylist) > 1:
        return '"{}"'.format('\n'.join(mylist))
    elif len(mylist) == 1:
        return mylist[0]
    else:
        return ''



class MyHTMLParser(html.parser.HTMLParser):
    main_term1 = [('class', 'concept_light-representation')]
    main_term2 = [('class', 'text')]
    main_term_filter1 = [main_term1, main_term2]
    main_term_filter2 = [main_term1, main_term2, []]
    
    furigana1 = main_term1
    furigana2 = [('class', 'furigana')]
    furigana_filter = [furigana1, furigana2]
    
    sentence_filter1 = [('class', 'clearfix')]
    sentence_filter2 = [('class', 'unlinked')]
    sentence_filter3 = [
        [('class', 'sentences zero-padding')],
        [('class', 'sentence')],
        [('class', 'japanese japanese_gothic clearfix'), ('lang', 'ja')],
    ]
    
    english_filter = [('class', 'english'), ('lang', 'en')]
    
    
    def __init__(self):
        super(MyHTMLParser, self).__init__()
        
        self.attrs = []
        self.level = 0
        self.skip_level = -1
    
        self.term = ''
        self.reading = ''
        self.furigana = []
        
        self.positions = []
        self.meanings = []
        
        self.sentences = []
        self.englishes = []
    
    
    def handle_starttag(self, tag, attrs):
        myprint(self.level, "Start tag : {}".format(tag))
        self.level += 1
        self.attrs.append(attrs)
        
        for attr in attrs:
            myprint(self.level, "attr :", attr)
        
        if attrs == [('class', 'sentences zero-padding')]:
            self.sentences.append('')
        
        # If this is a blank span tag in the furigana section,
        # add a blank to the kanli list
        if len(self.attrs) >= 3:
            if self.attrs[-3:] == [self.furigana1, self.furigana2, []]:
                self.furigana.append(None)
    
    
    def handle_endtag(self, tag):
        if self.level < self.skip_level:
            self.skip_level = -1
        
        self.level -= 1
        self.attrs.pop()
        
        myprint(self.level, "End tag : {}".format(tag))
    
    
    def handle_data(self, data):
        myprint(self.level, "Data : {}".format(data))
        
        if self.skip_level != -1:
            return
        
        data = data.strip()
        
        if len(self.attrs) >= 1:
            # Position / part of speech
            if self.attrs[-1] == [('class', 'meaning-tags')]:
                if data == 'Other forms' or data == 'Wikipedia definition':
                    self.skip_level = self.level
                else:
                    self.positions.append(data)
            
            # Meaning / English definition
            elif self.attrs[-1] == [('class', 'meaning-meaning')]:
                self.meanings.append(data)
            
            # English translation of sentence
            elif self.attrs[-1] == self.english_filter:
                self.englishes.append(data)
        
        if len(self.attrs) >= 3:
            myprint(self.level, self.attrs[-3:])
            # Build up the example sentence
            if (self.sentence_filter1 in self.attrs[-3:] and \
                self.sentence_filter2 in self.attrs[-3:]) or \
                self.sentence_filter3 == self.attrs[-3:]:
                self.sentences[-1] += data
            
            # Build up the main term (with kanji)
            elif self.attrs[-2:] == self.main_term_filter1 or \
               self.attrs[-3:] == self.main_term_filter2:
                self.term += data
            
            # Add a kana to the list to replace kanji in the reading
            elif self.attrs[-3:-1] == self.furigana_filter:
                self.furigana.append(data)



def construct_parser():
    argparser = argparse.ArgumentParser()
    
    # Positional arguments
    argparser.add_argument('words',
        type=str,
        nargs='*',
        help='The words to look up and add.')
    
    # Optional arguments
    argparser.add_argument('-d', '--debug',
        action='store_true',
        default=False,
        help='NOT IMPLEMENTED -- Enable debug mode.')
    
    argparser.add_argument('-k', '--kana',
        action='store_true',
        default=False,
        help='Use only hiragana for the term.')
    
    argparser.add_argument('-kk', '--katakana',
        action='store_true',
        default=False,
        help='Use only katakana for the term.')
    
    argparser.add_argument('-f', '--file',
        type=str,
        nargs='+',
        help='Use a file instead of going online.')
    
    argparser.add_argument('-u', '--url',
        type=str,
        nargs='+',
        help='Enter a URL directly.')
    
    argparser.add_argument('-o', '--output',
        type=str,
        help='CSV file to write to.')
    
    return argparser



def handle_term(args, word=None, url=None, filename=None):
    if filename:
        with open(filename, 'r') as f:
            text = f.read()
    elif url:
        page = requests.get(url)
        text = page.text
    else:
        page = requests.get('http://jisho.org/word/{}'.format(word))
        text = page.text
    
    parser = MyHTMLParser()
    parser.feed(text)
    
    # Pad the furigana out so that the lengths match
    original_furigana = parser.furigana
    diff = len(parser.term) - len(parser.furigana)
    furigana = parser.furigana + ([None] * diff)
    
    reading = ''
    for kanji, kana in zip(parser.term, furigana):
        if kana is not None:
            reading += kana
        else:
            reading += kanji
    
    print('term      : {}'.format(parser.term))
    print('furigana  : {}'.format(original_furigana))
    print('reading   : {}'.format(reading))
    print('positions : {}'.format(parser.positions))
    print('meanings  : {}'.format(parser.meanings))
    print('sentences : {}'.format(parser.sentences))
    print('englishes : {}'.format(parser.englishes))
    print()
    
    position, meaning, sentences, englishes = map(
        convert, [
            parser.positions, parser.meanings,
            parser.sentences, parser.englishes,
        ]
    )
    
    # If kana mode is on, use kana only for the term
    if args.kana:
        term = reading
    elif args.katakana:
        term = romkan.to_katakana(romkan.to_roma(reading))
    else:
        term = parser.term
    
    if len(term) > 0:
        # If no output file is given, default to 'out.csv'
        if args.output is None:
            args.output = 'out.csv'
        # If an output DIRECTORY is given, write to 'out.csv' in that directory
        elif os.path.isdir(args.output):
                args.output = os.path.join(args.output, 'out.csv')
        
        # Blanks are for the fields we don't care about
        with open(args.output, 'a') as f:
            f.write('\t'.join([
                term,       # Vocabulary-Kanji
                '',         # Vocabulary-Furigana
                reading,    # Vocabular-Kana
                meaning,    # Vocabulary-English
                '',         # Vocabulary-Audio
                position,   # Vocabulary-Pos
                '',         # Caution
                sentences,  # Expression
                '',         # Reading
                '',         # Sentence-Kana
                englishes,  # Sentence-English
            ]))
            f.write('\n')



if __name__ == '__main__':
    argparser = construct_parser()
    args = argparser.parse_args(sys.argv[1:])
    
    if args.file:
        for filename in args.file:
            handle_term(args, filename=filename)
    
    if args.url:
        for url in args.url:
            handle_term(args, url=url)
    
    for word in args.words:
        handle_term(args, word=word)
