import os
import requests
import libsdvx
import html_to_json
import logging as log
from argparse import ArgumentParser
from itertools import batched
from pathlib import Path

def ntfs_strip(string): 
    result = string
    for ch in "\"|%:/,\\[]<>*?":
        if ch in result:
            result = result.replace(ch, ' ')
            
    while result[-1:] == ' ' or result[-1:] == '.':
        result = result[:-1]
    return result

def get_batch_romanizations(songtitles):
    result = {}
    normalized = {}

    # Perform manual overrides for problematic titles
    for i, title in enumerate(songtitles):
        match title:
            case 'XXanadu#climaXX':
                songtitles[i] = 'XXanadu climaXX'
            case '#EmoCloche':
                songtitles[i] = 'EmoCloche'
            case 'うぇるかむ -||祭みっくす||-':
                songtitles[i] = 'VVelcome -matsuri mix-'
            case 'I':
                songtitles[i] = 'I (Chroma)'
            case 'gigadelic(m3rkAb4# R3m!x)':
                songtitles[i] = 'Gigadelic(m3rkAb4h R3m!x)'

    normalized['I (Chroma)'] = 'I'
    normalized['XXanadu climaXX'] = 'XXanadu#climaXX'
    normalized['EmoCloche'] = '#EmoCloche'
    normalized['VVelcome -matsuri mix-'] = 'うぇるかむ -||祭みっくす||-'
    normalized['Gigadelic(m3rkAb4h R3m!x)'] = 'gigadelic(m3rkAb4# R3m!x)'

    # Query the RemyWiki API
    queryString = '|'.join(songtitles)
    params = {\
        'action': 'query',
        'titles': queryString,
        'redirects': 1,
        'format': 'json'
    }
    remyreq = requests.get('https://remywiki.com/api.php', params=params)
    req_json = remyreq.json()

    # Keep track of titles that have been normalized (i.e. changed) in the query process
    if 'normalized' in req_json['query']:
        for song in req_json['query']['normalized']:
            normalized[song['to']] = song['from']

    # Handle redirects, which automatically mean a matching romanization was found
    if 'redirects' in req_json['query']:
        for song in req_json['query']['redirects']:
            # Handles case of a page redirect leading to another
            # redirect. This code finds the original song name in the result dict
            # and updates the value to the new redirect.
            if song['from'] in result.values():
                for test in result.keys():
                    if result[test] == song['from']:
                        result[test] = song['to']
                        break
            # Handles case of a song query having been normalized.
            # Instead of using the query in song['from'] as the key in result,
            # search for it in the normalized dict to get the real song name
            # to then use as a key in the result dict.
            elif song['from'] in normalized:
                result[normalized[song['from']]] = song['to']
                del normalized[song['from']]
            else:
                result[song['from']] = song['to']

    # Handle rest of returned pages, which includes pages w/o redirect or
    # pages without any pages, either due to different romanization on wiki
    # or song is too new
    if 'pages' in req_json['query']:
        for (_,song) in req_json['query']['pages'].items():
            # check if song is missing
            if 'missing' in song:
                # check if the missing song had a normalized title
                if song['title'] in normalized:
                    result[normalized[song['title']]] = None
                # otherwise, check if the missing song is not
                # already listed in the result dict.
                # Handles the case of a song query having a redirect to
                # a non-existent page.
                elif song['title'] not in result.values():
                    result[song['title']] = None
            # check if song was normalized in search
            # this means that the song's wiki page title is the same
            # as the track except for slight changes
            elif song['title'] in normalized:
                normal_title = normalized[song['title']]
                result[normal_title] = normal_title
            # otherwise, title is identical, add to result
            # but do not add duplicates
            elif song['title'] not in result.values():
                result[song['title']] = song['title'].replace('/', '-')
    
    return result

def get_song_game(song):
    game = None
    title = None

    # Get RemyWiki page
    params = {\
        'action': 'parse',\
        'page': song,\
        'prop': 'text',\
        'redirects': 1,\
        'format': 'json'\
    }
    remyreq = requests.get('https://remywiki.com/api.php', params=params)
    req_json = remyreq.json()
    if 'error' in req_json:
        return (None, None)

    # Check for redirect containing romanization
    if 'redirects' in req_json['parse'] and len(req_json['parse']['redirects']) != 0:
        title = req_json['parse']['redirects'][0]['to']

    # Parse html
    html = req_json['parse']['text']['*']
    parsed = html_to_json.convert(html)

    # Find SOUND VOLTEX in <a> elements in <p> element
    for p in parsed['div'][0]['p']:
        if 'a' in p:
            for a in p['a']:
                if 'SOUND VOLTEX' in a['_value'] and a['_value'].replace(' ', '') != 'SOUNDVOLTEX@wiki':
                    game = a['_value']
                    break

    # Find SOUND VOLTEX in <li> elements in <ul> element, if title not already found
    if not game:
        for li in parsed['div'][0]['ul'][0]['li']:
            if 'a' in li:
                if 'SOUND VOLTEX' in li['a'][0]['_value']:
                    game = li['a'][0]['_value']
                    break

    match game:
        case 'SOUND VOLTEX BOOTH':
            game = 'SDVX BOOTH'
        case 'SOUND VOLTEX II -infinite infection-':
            game = 'SDVX Infinite Infection'
        case 'SOUND VOLTEX III GRAVITY WARS':
            game = 'SDVX Gravity Wars'
        case 'SOUND VOLTEX IV HEAVENLY HAVEN':
            game = 'SDVX Heavenly Haven'
        case 'SOUND VOLTEX VIVID WAVE':
            game = 'SDVX Vivid Wave'
        case 'SOUND VOLTEX EXCEED GEAR':
            game = 'SDVX Exceed Gear'

    return (game, title)

def main(args):
    # ensure all folder paths given exist and are folders
    left_path = Path(args.left)
    right_path = Path(args.right)
    assert(left_path.exists() and left_path.is_dir() and right_path.exists() and right_path.is_dir())
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        log.basicConfig(format='[%(levelname)s] %(message)s', level=log.DEBUG)
    else:
        log.basicConfig(format='[%(levelname)s] %(message)s', level=log.INFO)

    # create SDVXCollection from both input folders
    log.info('Initializing left collection')
    left = libsdvx.SDVXCollection(args.left)
    log.info('Initializing right collection')
    right = libsdvx.SDVXCollection(args.right)

    left_unmatched = []
    right_unmatched = list(right.collection.keys())

    for song in left.collection.keys():
        if song in right.collection:
            right_unmatched.remove(song)
        else:
            left_unmatched.append(song)
    
    left_unmatched.sort()
    right_unmatched.sort()

    log.info('Beginning song collection merge process!')
    log.info('Merging songs existing in right collection!')
    left_songs = list(left.collection.keys())
    right_songs = list(right.collection.keys())
    
    # obtain romanizations of songs in batches of 50
    # and create corresponding folders in new output
    #left_right_songs = [song for song in left_songs if song in right_songs]
    for batch in batched(right_songs, 50):
        result = get_batch_romanizations(batch)
        for (original_song, romanization) in result.items():
            log.debug(f'Current song is {original_song} with romanization {romanization}')
            # check if no romanization was found
            if not romanization:
                romanization = input(f'Romanizaton for {original_song} was not found, please specify one: ')

            # formulate new folder(s) in destination dir and copy files over
            # get base game directory from right
            cur_song = right.collection[original_song]
            game_dir = cur_song.dirname.parent

            # substitute right dir with destination dir and append romanization
            dest_dir = output_path / game_dir.relative_to(right_path) / ntfs_strip(romanization)

            # create dest dir before copying
            dest_dir.mkdir(parents=True, exist_ok=True)

            # if song is in left collection, merge right equivalent with it
            # then copy the song from left collection to dest
            if original_song in left.collection:
                # combine songs in case right collection contains INF/GRV/HVN/VVD/XCD
                log.info(f'Attempting to combine both sets of {original_song}')
                left.merge_songs(left.collection[original_song], right.collection[original_song])

                # finally, copy song from left collection to dest dir
                left.collection[original_song].copy_song(dest_dir)
            else:
                # otherwise, just copy song from right collection to dest dir
                right.collection[original_song].copy_song(dest_dir)

            log.info(f'Transferred song file contents to {dest_dir}')

    # merge songs found only in the left collection
    # these songs require querying the wiki for both romanization and game of origin
    log.info('Merging songs from left collection!')
    for song in left_unmatched:
        # get song game and romanized title (if any)
        log.debug(f'Attempting to obtain metadata for {song}')
        (game, title) = get_song_game(song)
        if not game:
            game = input(f'Could not get game from RemyWiki. Please specify the game for {song}:')
            if not title:
                title = input(f'Could not get title from RemyWiki. Please specify the romanization for {song}:')
        if not title:
            title = song

        dest_dir = output_path / game / ntfs_strip(title)

        # make dest dir and copy
        dest_dir.mkdir(parents=True, exist_ok=True)
        left.collection[song].copy_song(dest_dir)
        log.info(f'Transferred song file contents to {dest_dir}')

    # repeat same process as merging songs present in both collections
    #log.info('Merging songs from right collection!')
    #for batch in batched(right_unmatched, 50):
    #    result = get_batch_romanizations(batch)
    #    for (original_song, romanization) in result.items():
    #        log.debug(f'Attempting to add song {original_song} with romanization {romanization}')
    #        # check if no romanization was found
    #        if not romanization:
    #            romanization = input(f'Romanizaton for {original_song} was not found, please specify one: ')

    #        # formulate new folder(s) in destination dir and copy files over
    #        # get base game directory from right
    #        cur_song = right.collection[original_song]
    #        game_dir = cur_song.dirname.parent

    #        # substitute right dir with destination dir and append romanization
    #        dest_dir = output_path / game_dir.relative_to(right_path) / ntfs_strip(romanization)

    #        # finally, create dest dir and copy
    #        dest_dir.mkdir(parents=True, exist_ok=True)
    #        right.collection[original_song].copy_song(dest_dir)
    #        log.info(f'Transferred song file contents to {dest_dir}')

    log.info('Merger Complete!')

parser = ArgumentParser()
parser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
parser.add_argument('-l', '--left', help='Collection you wish to overlay over the other', required=True)
parser.add_argument('-r', '--right', help='Collection you wish to have overlayed by the other', required=True)
parser.add_argument('-o', '--output', help='Output folder to write new collection to', required=True)

args = parser.parse_args()

main(args)
