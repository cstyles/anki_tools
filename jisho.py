#!/usr/bin/env python3

import requests
import sys
import argparse
import romkan
import os
from bs4 import BeautifulSoup
import bs4.element



def convert(mylist):
    if len(mylist) > 1:
        newlined_mylist = '\n'.join(mylist)
        return f'"{newlined_mylist}"'
    elif len(mylist) == 1:
        return mylist[0]
    else:
        return ''



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



def get_html(word, url, filename):
    if filename:
        with open(filename, 'r') as f:
            text = f.read()
    elif url:
        page = requests.get(url)
        text = page.text
    else:
        page = requests.get(f'http://jisho.org/word/{word}')
        text = page.text
    
    return text



def extract_term_and_reading(args, soup):
    # Extract furigana
    reading = soup.find(class_='furigana')
    furigana = []
    
    for r in reading:
        if type(r) is bs4.element.Tag:
            # For the exceptions that use a ruby tag (e.g., '矢鱈')
            if r.name == 'ruby':
                for child in r.children:
                    if child.name == 'rt':
                        furigana.append(child.text)
            else:
                furigana.append(r.text)
    
    # Extract the kanji
    text = soup.find_all(class_='text')[-1]
    kanji = []
    
    i = 0
    for t in text:
        if type(t) is bs4.element.NavigableString:
            t = t.strip()
            for char in t:
                i += 1
                kanji.append(char)
        else:
            kanji.append(t.text.strip())
            furigana[i] = t.text.strip()
            i += 1
    
    reading = ''.join(furigana)
    
    # If kana mode is on, use kana only for the term
    if args.kana:
        term = reading = romkan.to_hiragana(romkan.to_roma(reading))
    elif args.katakana:
        term = romkan.to_katakana(romkan.to_roma(reading))
        reading = term
    else:
        term = ''.join(kanji)
    
    return term, reading



def get_child(element, number=0):
    return list(element.children)[number]



def handle_sentence(top):
    sentence = english = ''
    
    for element in top:
        # If the element is a string, just include it
        if type(element) is bs4.element.NavigableString:
            sentence += element.strip()
        
        # If it's the english translation, add it
        elif 'english' in element.attrs['class']:
            english += element.text.strip()
        
        # Otherwise, assume it's a japanese sentence
        else:
            for child in element.children:
                # Disregard any furigana
                if 'unlinked' in child.attrs['class']:
                    sentence += child.text.strip()
    
    return sentence, english



def handle_meaning(sub):
    definition = sentence = english = None
    
    for child in sub.children:
        # Definition
        if 'meaning-definition' in child.attrs['class']:
            definition = get_child(child, 1).text
        
        # Sentence
        elif 'sentences' in child.attrs['class']:
            child = get_child(get_child(child))
            sentence, english = handle_sentence(child)
    
    return definition, sentence, english



def extract_meanings(soup):
    ret = []
    
    wrapper = soup.find(class_='meanings-wrapper')
    
    positions = []
    meanings = []
    sentences = []
    englishes = []
    skip = False
    
    for sub in wrapper:
        if skip:
            skip = False
            continue
        
        if 'meaning-tags' in sub.attrs['class']:
            if sub.text in ['Other forms', 'Wikipedia definition', 'Notes']:
                skip = True
                continue
            else:
                positions.append(sub.text)
        else:
            # meaning, sentence = handle_meaning(sub)
            meaning, sentence, english = handle_meaning(sub)
            meanings.append(meaning)
            
            if sentence is not None:
                sentences.append(sentence)
            
            if english is not None:
                englishes.append(english)
    
    return positions, meanings, sentences, englishes



def handle_term(args, word=None, url=None, filename=None):
    # Get the HTML
    text = get_html(word, url, filename)
    
    # Parse the HTML
    soup = BeautifulSoup(text, 'html.parser')
    
    # Extract any kanji and furigana
    term, reading = extract_term_and_reading(args, soup)
    
    # Get position, definitions, and sentences (English and Japanese)
    positions, meanings, sentences, englishes = extract_meanings(soup)
    
    print(f'term      : {term}')
    print(f'reading   : {reading}')
    print(f'positions : {positions}')
    print(f'meanings  : {meanings}')
    print(f'sentences : {sentences}')
    print(f'englishes : {englishes}')
    
    position, meaning, sentences, englishes = map(
        convert,
        [positions, meanings, sentences, englishes],
    )
    
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
    
    print()



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
