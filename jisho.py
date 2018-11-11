#!/usr/bin/env python3


ignore_definitions = [
    'Other forms',
    'Wikipedia definition',
    'Notes',
    'Place',
]


def ensure_https(url):
    return re.sub(r'^http:', 'https:', url)


def convert(mylist):
    if len(mylist) > 1:
        return '\n'.join(mylist)
    elif len(mylist) == 1:
        return mylist[0]
    else:
        return ''


def construct_parser():
    import argparse
    argparser = argparse.ArgumentParser()

    # Positional arguments
    argparser.add_argument(
        'words',
        type=str,
        nargs='*',
        help='The words to look up and add.'
    )

    # Optional arguments
    argparser.add_argument(
        '-d', '--debug',
        action='store_true',
        default=False,
        help='Debug mode (don\'t write to file)'
    )

    argparser.add_argument(
        '-k', '--kana',
        action='store_true',
        default=False,
        help='Use only hiragana for the term.'
    )

    argparser.add_argument(
        '-kk', '--katakana',
        action='store_true',
        default=False,
        help='Use only katakana for the term.'
    )

    argparser.add_argument(
        '-f', '--file',
        type=str,
        nargs='+',
        help='Use a file instead of going online.'
    )

    argparser.add_argument(
        '-o', '--output',
        type=str,
        help='CSV file to write to.')

    argparser.add_argument(
        '-i', '--interactive',
        action='store_true',
        default=False,
        help='Interactive mode.'
    )

    return argparser


def print_error(word, filename=None):
    if filename:
        source = filename
    else:
        source = word

    print(f'Error processing: {source}')
    print()


def get_first_search_result(url):
    page = requests.get(ensure_https(url))
    page.raise_for_status()
    text = page.text
    soup = bs4.BeautifulSoup(text, 'html.parser')
    detail = soup.find(class_='light-details_link')
    if detail is None:
        return
    detail_href = detail.attrs['href']
    return requests.get('https:' + detail_href)


def get_html(word, filename):
    if filename:
        with open(filename, 'r') as f:
            text = f.read()

    # If the word is a direct URL to a word
    elif re.match(r'https?://jisho\.org/word/.+', word):
        page = requests.get(ensure_https(word))
        text = page.text

    # If the word is a direct URL to a search
    elif re.match(r'https?://jisho\.org/search/.+', word):
        page = get_first_search_result(word)
        if page is None:
            return
        text = page.text

    else:
        page = requests.get(f'https://jisho.org/word/{word}')

        # If the word doesn't exist, search and use the first result
        if page.status_code == 404:
            print(f'No exact match for "{word}". Trying search…')
            page = get_first_search_result(f'https://jisho.org/search/{word}')
            if page is None:
                return
        else:
            page.raise_for_status()

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
            if sub.text in ignore_definitions:
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


def handle_term(args, word=None, filename=None):
    # Get the HTML
    text = get_html(word, filename)
    if text is None:
        print_error(word, filename)
        return

    # Parse the HTML
    soup = bs4.BeautifulSoup(text, 'html.parser')

    # Extract any kanji and furigana
    try:
        term, reading = extract_term_and_reading(args, soup)
    except TypeError:
        print_error(word, filename)
        return

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

    if len(term) > 0 and not args.debug:
        # If no output file is given, default to 'out.csv'
        if args.output is None:
            args.output = 'out.csv'
        # If an output DIRECTORY is given, write to 'out.csv' in that directory
        elif os.path.isdir(args.output):
            args.output = os.path.join(args.output, 'out.csv')

        # Blanks are for the fields we don't care about
        with open(args.output, 'a') as f:
            csvf = csv.writer(f, delimiter='\t', quotechar='"')
            csvf.writerow([
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
            ])

    print()


if __name__ == '__main__':
    import sys
    argparser = construct_parser()
    args = argparser.parse_args(sys.argv[1:])

    # Exit if there's nothing to do
    if len(args.words) == 0 and args.file is None and args.interactive is False:
        exit(0)

    import requests
    import romkan
    import os
    import bs4
    import re
    import csv

    if args.interactive:
        import readline
        while True:
            try:
                s = input('>>> ')
                if s == '-k':
                    args.kana = not args.kana
                elif s == '-kk':
                    args.katakana = not args.katakana
                else:
                    handle_term(args, word=s)

            except TypeError as e:
                print('Nothing doing')

            except (KeyboardInterrupt, EOFError) as e:
                print()
                exit(0)
    else:
        if args.file:
            for filename in args.file:
                handle_term(args, filename=filename)

        for word in args.words:
            handle_term(args, word=word)
