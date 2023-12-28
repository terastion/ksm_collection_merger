import json
import logging as log
from pathlib import Path
from shutil import copy
from typing import Self

# class for a single .ksh chart file's metadata
class SDVXChart:
    fields = {
        'title': 'title',
        'artist': 'artist',
        'effect': 'effector',
        'illustrator': 'illustrator',
        'difficulty': 'difficulty',
        'level': 'level',
        'm': 'music',
        'jacket': 'jacket',
        'sounds': 'sounds',
        'custom_path': 'custom_path',
    }

    def __init__(self, chart_file: Path = None, json_dict: dict = None, include_sfx: bool = True) -> Self:
        assert(chart_file and chart_file.exists() or json_dict)
        if json_dict:
            self.filename = Path(json_dict['filename'])
        else:
            self.filename = Path(chart_file.name)

        # this gets set to True if chart files are at different directory than rest of song
        # which does not happen on init
        self.custom_path = False

        # init empty fields in case they're not found in file
        self.effector = None
        self.illustrator = None
        self.level = None
        self.music = []
        self.jacket = None
        self.sounds = None

        # have all class fields as references
        ksm_fields = list(self.fields.keys())
        class_fields = list(self.fields.values())

        # if json_dict provided, set object fields to corresponding json_dict fields
        if json_dict:
            [setattr(self, field, json_dict[field]) for field in class_fields if field in json_dict]

        # otherwise, read ksh file and record desired fields in object
        else:
            with chart_file.open('r', encoding='utf-8-sig', errors='ignore') as chart:
                cur_line = chart.readline().strip()
                while cur_line != "" and cur_line != "--":
                    # skip non-metadata lines
                    if '=' not in cur_line:
                        cur_line = chart.readline().strip()
                        continue

                    # read each field and set object field accordingly
                    (field, value) = cur_line.split('=', 1)
                    if field in ksm_fields:
                        # read level field as a number
                        if field == 'level':
                            self.level = int(value)
                        # some charts have more than 1 music file associated w it, separated by ';'
                        # the 1st one is the clean version of a song, 2nd one is with SFX
                        elif field == 'm':
                            if ';' in value:
                                self.music = value.split(';')
                            else:
                                self.music = [value]
                        else:
                            setattr(self, self.fields[field], value)

                    # read next line for loop
                    cur_line = chart.readline().strip()

                # check chart file for any extra effect audios
                if include_sfx:
                    self.sounds = set()
                while cur_line != '':
                    if '.ogg' in cur_line:
                        # extract any .ogg filename mentioned in chart file
                        # and add to sounds set
                        splits = cur_line.split('=')
                        for s in splits:
                            if '.ogg' in s:
                                self.sounds.add(s.split(';')[0])
                                break
                    cur_line = chart.readline().strip()

                # convert sounds set into a list for serialization purposes
                self.sounds = list(self.sounds)

    # convert object to serializable dict
    def to_json(self) -> dict:
        result = self.__dict__.copy()
        result['filename'] = str(self.filename)

        # do not include title or artist, as these are included 
        # in an SDVXChart's parent SDVXSong
        del result['title']
        del result['artist']
        return result

    # get all files of chart
    def get_files(self) -> list[str]:
        result = []
        result.append(str(self.filename))
        if self.jacket:
            result.append(self.jacket)
        if self.music:
            result += self.music
        if self.sounds:
            result += self.sounds
        return result

# class representing a song folder, which contains chart files for different difficulties
class SDVXSong:
    # list indexes for each difficulty name
    difficulties = {
        'light': 0,
        'challenge': 1,
        'extended': 2,
        'infinite': 3
    }

    def __init__(self, song_dir: Path = None, json_dict: dict = None, include_sfx: bool = True) -> Self:
        assert(song_dir and song_dir.exists() or json_dict)
        self.dirname = song_dir or Path(json_dict['dirname'])
        self.title = None

        # the four list items represent NOV, ADV, EXH, and MXM/INF/GRV/VVD/XCD difficulties
        self.charts = [None, None, None, None]

        # populate class fields with json_dict data if available
        if json_dict:
            self.charts = [SDVXChart(json_dict=chart, include_sfx=include_sfx) if chart else None for chart in json_dict['charts']]
            # update each SDVXChart with title/artist metadata
            # since json data for a chart does not contain it
            for chart in self.charts:
                if chart:
                    chart.title = json_dict['title']
                    chart.artist = json_dict['artist']
            self.title = json_dict['title']
            self.artist = json_dict['artist']
        # otherwise, scan song_dir for ksm files
        else:
            chart_files = song_dir.glob('*.ksh')
            conflicts = set()
            for chart_file in chart_files:
                log.debug(f'Current chart file is {chart_file}')
                chart = SDVXChart(chart_file=chart_file, include_sfx=include_sfx)

                # set chart title, or checks if it matches existing name
                # if it does match an existing name, add to list of conflicting titles
                if self.title:
                    if self.title != chart.title:
                        conflicts.add(chart.title)
                        conflicts.add(self.title)
                else: self.title = chart.title
                self.artist = chart.artist

                # add SDVXChart to list of SDVXSong's charts
                self.charts[self.difficulties[chart.difficulty]] = chart

            # if there are naming conflicts, prompt user for the correct name
            # and propagate it to all chart files
            if conflicts:
                conflict_list = list(conflicts)
                while True:
                    try:
                        log.warn(f'Title conflict detected at song directory {song_dir}: \n{\
                            '\n'.join([f'[{num}] {title}' for (num, title) in enumerate(conflict_list)])\
                        }')
                        number = int(input('Please type a number to specify correct title: '))
                        self.update_title(chart, conflict_list[number])
                        break
                    except:
                        log.warn('Invalid entry!')

    # update song title for all chart files
    def update_title(self, new_title: str):
        self.title = new_title
        for chart in self.charts:
            # only update chart data if title doesn't match new one
            if chart and chart.title != new_title:
                # update title in SDVXChart object
                chart.title = new_title

                # assemble full chart path using either song dir + filename
                # or the complete filename in case of charts w/custom paths
                full_path = None
                if chart.custom_path:
                    full_path = chart.filename
                else:
                    full_path = self.dirname / chart.filename

                # read all lines and find line containing title=, then update title
                with full_path.open('r+', encoding='utf-8-sig', errors='ignore') as file:
                    lines = file.readlines()
                    for i, line in enumerate(lines):
                        if line[:6] == 'title=':
                            lines[i] = f'title={new_title}\n'
                            break

                    file.seek(0)
                    file.writelines(lines)

    # convert object to serializable dict
    def to_json(self) -> dict:
        result = self.__dict__.copy()
        result['dirname'] = str(self.dirname)
        result['charts'] = [chart.to_json() if chart else None for chart in self.charts]
        return result

    # get all files used by all difficulties of song
    def get_files(self) -> list[str]:
        result = set()
        for chart in self.charts:
            if chart:
                result.update(chart.get_files())

        return list(result)

    # get all files of a specific difficulty
    def get_difficulty_files(self, diff) -> list[str]:
        chart = self.charts[self.difficulties[diff]]
        return chart.get_files() if chart else []

    # copy song files over to a new directory
    def copy_song(self, dest_dir: Path):
        for chart in self.charts:
            if chart:
                # check if difficulty is hosted at different directory
                chart_directory = self.dirname
                if chart.custom_path:
                    chart_directory = chart.filename.parent

                # copy files over
                for file in self.get_difficulty_files(chart.difficulty):
                    file_name = Path(file).name
                    full_file_path = chart_directory / file_name
                    
                    # check if file does not already exist in dest_dir
                    # otherwise copy it over
                    dest_file_path = dest_dir / file_name
                    if not dest_file_path.exists():
                        copy(full_file_path, dest_file_path)

# master class representing a collection of song folders
class SDVXCollection:
    def __init__(self, collection_dir: Path = None, include_sfx=True):
        # make sure collection dir exists
        assert(collection_dir and collection_dir.exists())
        self.path = collection_dir.resolve()

        # if data file exists in collection dir,
        # initialize object from json
        # otherwise, initialize collection from folder
        json_file = collection_dir / 'data.json'
        if json_file.exists():
            with json_file.open('r') as file:
                json_dict = json.load(file)
                self.collection = {}
                for song in json_dict['collection']:
                    title = song['title']
                    sdvxsong = SDVXSong(json_dict=song)
                    self.collection[title] = sdvxsong
        else:
            self.collection = {}

            # iterate through all directories in collection dir and init
            self.init_folder(collection_dir, include_sfx)

    # check for the presence of .ksh files in directory
    def is_song_directory(song_dir: Path) -> bool:
        return bool(next(song_dir.glob('*.ksh'), False))
    
    def init_folder(self, collection_dir: Path, include_sfx: bool):
        # iterate through dir contents
        for songdir in collection_dir.iterdir():
            if songdir.is_dir():
                # if folder contains ksh charts, init SDVXSong obj
                # otherwise, recursive call init_folder on subfolder
                if SDVXCollection.is_song_directory(songdir):
                    log.debug(f'Initiating SDVXSong at {songdir}')
                    song = SDVXSong(song_dir=songdir, include_sfx=include_sfx)

                    # if song title does not exist in collection, add it
                    # otherwise, attempt to merge SDVXSongs into one
                    if song.title not in self.collection:
                        log.debug(f'Adding {song.title} located at {songdir} to collection')
                        self.collection[song.title] = song
                    else:
                        log.warn(f'Song {song.title} at {songdir} already exists at {self.collection[song.title].dirname}.')
                        canon = self.merge_songs_internal(self.collection[song.title], song)
                        if canon:
                            log.info(f'Successfully merged under {canon.dirname}!')
                        else:
                            log.info('Failed to merge songs')
                else:
                    log.warn(f'Directory {songdir} is not a song directory!')
                    self.init_folder(songdir, include_sfx)

    # merge song folders that contain INF/GRV/VVD/XCD difficulties with their regular counterparts
    # returns the main song path to be used
    # only to be used when initializing SDVXCollection and in merger script
    def merge_songs_internal(self, song1: SDVXSong, song2: SDVXSong) -> SDVXSong | None:
        main_song = None
        mxm_song = None

        # determine which song is main by checking which one contains a MXM
        # and which one lacks it
        if song1.charts[3] and not song2.charts[3]:
            main_song = song2
            mxm_song = song1
            self.collection[song1.title] = song2
        elif not song1.charts[3] and song2.charts[3]:
            main_song = song1
            mxm_song = song2
        else:
            #log.warn(f'Neither difficulty of {song1.title} contains a MXM!')
            return None

        # generate full (relative path) of mxm_song and edit mxm chart to use it
        # then set main_song's MXM to mxm_song's MXM
        if not mxm_song.charts[3].custom_path:
            mxm_path = mxm_song.dirname / mxm_song.charts[3].filename.name
            mxm_song.charts[3].filename = mxm_path
            mxm_song.charts[3].custom_path = True
        main_song.charts[3] = mxm_song.charts[3]

        #del mxm_song
        return main_song

    # search for a string in song list
    def search_song(self, query: str) -> list[str]:
        return [song for song in self.collection.keys() if query in song]

    # convert object to serializable dict
    def to_json(self) -> dict:
        result = {}
        result['collection'] = []
        for song in self.collection.values():
            result['collection'].append(song.to_json())

        return result

    # export collection json to a data file
    def export_collection(self):
        json_file = self.path / 'data.json'
        with json_file.open('w') as file:
            json.dump(self.to_json(), file, ensure_ascii=False)
