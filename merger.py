import os
import requests
import libsdvx
import html_to_json
from tinylog import log, debug
from argparse import ArgumentParser

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
    unresolved = []
    normalized = {}

    # Query the RemyWiki API
    # Includes manual overrides for problematic titles
    # TODO: find better replacement method
    fixes = list(map(lambda x: x.replace('I', 'I (Chroma)') if x == 'I' else x, songtitles))
    fixes2 = list(map(lambda x: x.replace('#', ' ') if x == 'XXanadu#climaXX' else x, fixes))
    fixes3 = list(map(lambda x: x.replace('#', '') if x == '#EmoCloche' else x, fixes2))
    fixes4 = list(map(lambda x: x.replace('うぇるかむ -||祭みっくす||-', 'うぇるかむ'), fixes3))
    normalized['I (Chroma)'] = 'I'
    normalized['XXanadu climaXX'] = 'XXanadu#climaXX'
    normalized['EmoCloche'] = '#EmoCloche'
    normalized['うぇるかむ'] = 'うぇるかむ -||祭みっくす||-'
    queryString = '|'.join(fixes4)
    params = {\
        'action': 'query',\
        'titles': queryString,\
        'redirects': 1,\
        'format': 'json'\
    }
    remyreq = requests.get('https://remywiki.com/api.php', params=params)
    req_json = remyreq.json()

    # Update song lists in unresolved for any titles that may have changed in query, if any
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
                    unresolved.append(normalized[song['title']])
                    result[normalized[song['title']]] = None
                # otherwise, check if the missing song is not
                # already listed in the result dict.
                # Handles the case of a song query having a redirect to
                # a non-existent page.
                elif song['title'] not in result.values():
                    unresolved.append(song['title'])
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
    assert(os.path.exists(args.left) and os.path.exists(args.right))
    if not os.path.exists(args.output):
        os.mkdir(args.output)

    log('info', 'Initializing left collection')
    left = libsdvx.SDVXCollection(args.left, verbose=args.verbose)
    log('info', 'Initializing right collection')
    right = libsdvx.SDVXCollection(args.right, verbose=args.verbose)

    left_unmatched = []
    right_unmatched = list(right.collection.keys())

    for song in left.collection.keys():
        if song in right.collection:
            right_unmatched.remove(song)
        else:
            left_unmatched.append(song)
    
    left_unmatched.sort()
    right_unmatched.sort()

    right_unmatched.append(None)
    #print('[INFO] The following songs have no matches in the left library:')
    #print(left_unmatched)
    #print('[INFO] The following songs have no matches in the right library:')
    #print(right_unmatched)

    log('info', 'Beginning merge process!')
    log('info', 'Merging songs existing in both collections')
    left_songs = list(left.collection.keys())
    right_songs = list(right.collection.keys())
    
    # Append None to song lists
    # This allows the inner if statement to pass
    # allowing for a song title query with less than 50 songs
    left_songs.append(None)
    right_songs.append(None)
    queue = []
    for song in left_songs:
        if song in right_songs:
            if song:
                queue.append(song)
            if len(queue) == 50 or not song:
                if len(queue) == 0:
                    continue
                result = get_batch_romanizations(queue)
                for (original_song, romanization) in result.items():
                    debug(args.verbose, f'Current song is {original_song} with romanization {romanization}')
                    # check if no romanization was found
                    if not romanization:
                        romanization = input(f'Romanizaton for {original_song} was not found, please specify one: ')

                    # formulate new folder(s) in destination dir and copy files over
                    # get base game directory from right
                    cur_song = right.collection[original_song]
                    game_dir = os.path.dirname(cur_song.dirname)

                    # substitute right dir with destination dir and append romanization
                    dest_game_dir = game_dir.replace(args.right, args.output)
                    dest_dir = os.path.join(dest_game_dir, ntfs_strip(romanization))

                    # combine songs in case right collection contains a VVD/XCD
                    log('log', f'Attempting to combine both sets of {original_song}')
                    left.merge_songs(left.collection[original_song], right.collection[original_song])

                    # finally, create dest dir and copy
                    os.makedirs(dest_dir, exist_ok=True)
                    left.collection[original_song].copy_song(dest_dir)
                    log('log', f'Transferred song file contents to {dest_dir}')
                queue = []

    log('info', 'Merging songs from left collection!')
    for song in left_unmatched:
        # get song game and romanized title (if any)
        debug(args.verbose, f'Attempting to obtain metadata for {song}')
        (game, title) = get_song_game(song)
        if not game:
            game = input(f'Could not get game from RemyWiki. Please specify the game for {song}:')
            if not title:
                title = input(f'Could not get title from RemyWiki. Please specify the romanization for {song}:')
        if not title:
            title = song

        dest_dir = os.path.join(args.output, game, ntfs_strip(title))

        # make dest dir and copy
        os.makedirs(dest_dir, exist_ok=True)
        left.collection[song].copy_song(dest_dir)
        log('log', f'Transferred song file contents to {dest_dir}')

    log('info', 'Merging songs from right collection!')
    queue = []
    for song in right_unmatched:
        if song:
            queue.append(song)
        if len(queue) == 50 or not song:
            if len(queue) == 0:
                continue
            result = get_batch_romanizations(queue)
            for (original_song, romanization) in result.items():
                debug(args.verbose, f'Attempting to add song {original_song} with romanization {romanization}')
                # check if no romanization was found
                if not romanization:
                    romanization = input(f'Romanizaton for {original_song} was not found, please specify one: ')

                # formulate new folder(s) in destination dir and copy files over
                # get base game directory from right
                cur_song = right.collection[original_song]
                game_dir = os.path.dirname(cur_song.dirname)

                # substitute right dir with destination dir and append romanization
                dest_game_dir = game_dir.replace(args.right, args.output)
                dest_dir = os.path.join(dest_game_dir, ntfs_strip(romanization))

                # finally, create dest dir and copy
                os.makedirs(dest_dir, exist_ok=True)
                right.collection[original_song].copy_song(dest_dir)
                log('log', f'Transferred song file contents to {dest_dir}')
            queue = []

    log('info', 'Merger Complete!')

parser = ArgumentParser()
parser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
parser.add_argument('-l', '--left', help='Collection you wish to overlay over the other', required=True)
parser.add_argument('-r', '--right', help='Collection you wish to have overlayed by the other', required=True)
parser.add_argument('-o', '--output', help='Output folder to write new collection to', required=True)

args = parser.parse_args()

main(args)
