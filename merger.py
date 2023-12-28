import asyncio
import aiohttp
import libsdvx
import logging as log
import re
from argparse import ArgumentParser
from bs4 import BeautifulSoup
from itertools import batched, chain
from pathlib import Path

# remywiki's api limit is 50 titles per query
REMY_API = 'https://remywiki.com/api.php'
BATCH_SIZE = 50

# remove characters not allowed in ntfs filenames
def ntfs_strip(string):
    result = string
    substitutions = {
        '"|%:/,\\': ' ',
        '[<': '(',
        ']>': ')'
    }
    for (chs, sub) in substitutions.items():
        for ch in chs:
            if ch in result:
                result = result.replace(ch, sub)

    # make sure result does not end in a space or period
    while result[-1:] == ' ' or result[-1:] == '.':
        result = result[:-1]

    return result

# helper function to evaluate redirects
def resolve_redirects(data):
    # build dict of redirects, resolving any potential chain redirects
    redirects = {}
    for redirect in data:
        # if a redirect A's 'from' value = another redirect B's 'to' value
        # update B's 'to' value to A's 'to' value
        if redirect['from'] in redirects.values():
            redirect_keys = [key for key, value in redirects.items() if value == redirect['from']]
            redirects[redirect_keys[0]] = redirect['to']
        # if a redirect A's 'to' value = another redirect B's 'from' value
        # update redirect B's 'from' value to A's 'from' value
        elif redirect['to'] in redirects.keys():
            redirects[redirect['from']] = redirects[redirect['to']]
            del redirects[redirect['to']]
        # otherwise, just add redirect to dict
        else:
            redirects[redirect['from']] = redirect['to']

    return redirects

# get romanizations for a batch of BATCH_SIZE song titles asynchronously
async def get_batch_romanizations(session: aiohttp.ClientSession, songtitles: list[str]) -> (str, str | None):
    # manually override problematic titles
    # containing illegal characters for mediawiki queries
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
            case '[ ]DENTITY':
                songtitles[i] = 'IDENTITY'

    # join song titles together for query parameters
    query_string = '|'.join(songtitles)
    params = {
        'action': 'query',
        'titles': query_string,
        'redirects': 1,
        'format': 'json',
    }

    result = []

    # make remywiki query
    async with session.get(REMY_API, params=params) as response:
        data = await response.json()
        returned = []

        # keep track of titles that have been normalized (i.e. changed) in the query process
        # initialize with manual overrides
        normalized = {
            'I (Chroma)': 'I',
            'XXanadu climaXX': 'XXanadu#climaXX',
            'EmoCloche': '#EmoCloche',
            'VVelcome -matsuri mix-': 'うぇるかむ -||祭みっくす||-',
            'Gigadelic(m3rkAb4h R3m!x)': 'gigadelic(m3rkAb4# R3m!x)',
            'IDENTITY': '[ ]DENTITY'
        }

        # add all normalized titles to normalized dict
        if 'normalized' in data['query']:
            for song in data['query']['normalized']:
                normalized[song['to']] = song['from']

        # handle redirects, which automatically mean a matching romanization was found
        if 'redirects' in data['query']:
            # build dict of redirects, resolving any potential chain redirects
            redirects = resolve_redirects(data['query']['redirects'])

            # now, iterate through dict of redirects and check for normalization
            # before adding each member to result list
            for (original, redirect) in redirects.items():
                if original in normalized:
                    result.append((normalized[original], redirect))
                    del normalized[original]
                else:
                    result.append((original, redirect))
                returned.append(redirect)

        # handle rest of returned pages, which include titles without redirects
        # or titles without any page
        if 'pages' in data['query']:
            for song in data['query']['pages'].values():
                # check if song is missing
                if 'missing' in song:
                    # check for normalized title
                    if song['title'] in normalized:
                        result.append((normalized[song['title']], None))
                        del normalized[song['title']]
                        returned.append(song['title'])
                    # otherwise, check to make sure song hasn't already been returned w/redirect
                    # handles case of songs having redirect to page that doesn't exist
                    elif song['title'] not in returned:
                        result.append((song['title'], None))
                        returned.append(song['title'])
                # check if song was normalized in search
                if song['title'] in normalized:
                    result.append((normalized[song['title']], normalized[song['title']]))
                    del normalized[song['title']]
                    returned.append(song['title'])
                # otherwise, title's romanization is identical, and return tuple w/identical title
                # but do not return duplicates
                elif song['title'] not in returned:
                    result.append((song['title'], song['title']))
                    returned.append(song['title'])

        return result

games = {
    'SOUND VOLTEX BOOTH': 'SDVX BOOTH',
    'SOUND VOLTEX II -infinite infection-': 'SDVX Infinite Infection',
    'SOUND VOLTEX III GRAVITY WARS': 'SDVX Gravity Wars',
    'SOUND VOLTEX IV HEAVENLY HAVEN': 'SDVX Heavenly Haven',
    'SOUND VOLTEX VIVID WAVE': 'SDVX Vivid Wave',
    'SOUND VOLTEX EXCEED GEAR': 'SDVX Exceed Gear'
}

# get romanization and game of origin for a song title asynchronously
async def get_song_game(session: aiohttp.ClientSession, song: str):
    # query wiki for song's page HTML
    romanization = song
    game = None
    params = {
        'action': 'parse',
        'page': song,
        'prop': 'text',
        'redirects': 1,
        'format': 'json'
    }

    # make remywiki query
    async with session.get(REMY_API, params=params) as response:
        data = await response.json()
        if 'error' in data:
            return (song, None, None)

        # check for redirect containing romanization
        if 'redirects' in data['parse'] and len(data['parse']['redirects']) != 0:
            redirects = resolve_redirects(data['parse']['redirects'])
            # there should only be 1 (resolved) redirect per title
            romanization = list(redirects.values())[0]
        
        # parse html
        html = data['parse']['text']['*']
        soup = BeautifulSoup(html,features='html.parser')

        # find SOUND VOLTEX game title in html
        for result in soup.div.find_all(string=re.compile('SOUND VOLTEX*')):
            if str(result) in games:
                game = games[str(result)]
                break

        return (song, romanization, game)

async def main(args):
    # ensure all folder paths exist given and are folders
    left_path = Path(args.left)
    right_path = Path(args.right)
    assert(left_path.exists() and left_path.is_dir() and right_path.exists() and right_path.is_dir())
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        log.basicConfig(format='[%(levelname)s] %(message)s', level=log.DEBUG)
    else:
        log.basicConfig(format='[%(levelname)s] %(message)s', level=log.INFO)

    # init SDVXCollections for both input folders
    log.info('Initializing left collection')
    left = libsdvx.SDVXCollection(left_path)
    log.info('Initializing right collection')
    right = libsdvx.SDVXCollection(right_path)

    # save collection jsons for future use if program fails
    if not Path(left_path / 'data.json').exists():
        left.export_collection()
    if not Path(right_path / 'data.json').exists():
        right.export_collection()

    # assemble a separate list of songs in left collection
    # that are not in the right collection
    left_unmatched = []
    for song in left.collection.keys():
        if song not in right.collection:
            left_unmatched.append(song)

    log.info('Beginning song collection merge process!')
    log.info('Merging songs existing in right collection!')
    right_songs = list(right.collection.keys())

    # obtain romanizations of songs in right collection
    # and create corresponding folders in new output
    async with aiohttp.ClientSession() as session:
        # split songs into batches of BATCH_SIZE in order to query their
        # romanizations asynchronously
        tasks = [get_batch_romanizations(session, list(batch)) for batch in batched(right_songs, BATCH_SIZE)]
        for (original, romanization) in chain(*await asyncio.gather(*tasks)):
            log.debug(f'Current song is {original} with romanization {romanization}')
            # check if no romanization was found and prompt user if so
            if not romanization:
                romanization = input(f'Romanization for {original} was not found, please specify one: ')

            # formulate new folder(s) in destination dir and copy files over
            # start by getting base game directory from right
            right_song = right.collection[original]
            game_dir = right_song.dirname.parent

            # substitute right dir with destination dir and append romanization
            dest_dir = output_path / game_dir.relative_to(right_path) / ntfs_strip(romanization)

            # create dest dir before copying
            dest_dir.mkdir(parents=True, exist_ok=True)

            # if song is not in left collection, copy song from right collection to dest
            # otherwise, merge with left equivalent of song, then copy song from left
            if original not in left.collection:
                right_song.copy_song(dest_dir)
            else:
                # combine songs in case right collection contains INF/GRV/HVN/VVD/XCD
                log.info(f'Attempting to combine both sets of {original}')
                left_song = left.collection[original]
                left.merge_songs_internal(left_song, right_song)

                # finally, copy song from left collection to dest dir
                left_song.copy_song(dest_dir)

            log.info(f'Transferred song file contents to {dest_dir}')

        # merge songs only found in the left collection
        log.info('Merging songs from left collection!')

        tasks2 = [get_song_game(session, song) for song in left_unmatched]
        for (song, romanization, game) in await asyncio.gather(*tasks2):
            # if game was not found, query for game
            if not game:
                game = input(f'Could not get base game from RemyWiki. Please specify the game for {song}: ')
                # if both game AND romanization not found, then function failed to get article
                # from remywiki and must ask for it
                if not romanization:
                    romanization = input(f'Could not get title romanization from RemyWiki. Please specify the romanization for {song}: ')
            # if game was found but not romanization, then song=romanization
            if not romanization:
                romanization = song

            dest_dir = output_path / game / ntfs_strip(romanization)

            # make dest dir and copy
            dest_dir.mkdir(parents=True, exist_ok=True)
            left.collection[song].copy_song(dest_dir)
            log.info(f'Transferred song file contents to {dest_dir}')

    log.info('Merger Complete!')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-v', '--verbose', help='Verbose output', default=False, action='store_true')
    parser.add_argument('-l', '--left', help='Collection you wish to overlay the other', required=True)
    parser.add_argument('-r', '--right', help='Collection you wish to have overlayed by the other', required=True)
    parser.add_argument('-o', '--output', help='Output folder to write new collection to', required=True)
    args = parser.parse_args()

    asyncio.run(main(args))
