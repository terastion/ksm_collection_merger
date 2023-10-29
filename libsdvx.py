import os
import logging as log
from pathlib import Path
from shutil import copy

class SDVXChart:
    difficulties = {\
        'light': 'NOV',\
        'challenge': 'ADV',\
        'extended': 'EXH',\
        'infinite': 'MXM',\
    }
    def __init__(self, chart_file, include_sfx=True):
        # make sure chart file exists
        assert(chart_file.exists())
        self.filename = Path(chart_file.name)
        
        # this gets set to True elsewhere if chart is at different directory than rest of song
        self.custom_path = False

        # Init empty fields in case they're not found in file
        self.title = None
        self.difficulty = None
        self.level = None
        self.music = []
        self.jacket = None
        self.sounds = None

        # read start of ksh file and record desired fields in obj
        with chart_file.open('r', encoding='utf-8-sig', errors='ignore') as chart:
            cur_line = chart.readline().strip()
            while cur_line != "" and cur_line != '--':
                if '=' not in cur_line:
                    cur_line = chart.readline().strip()
                    continue

                (field, value) = cur_line.split('=', 1)
                if field == 'title':
                    self.title = value
                elif field == 'difficulty':
                    self.difficulty = self.difficulties[value]
                elif field == 'level':
                    self.level = int(value)
                elif field == 'm':
                    if ';' in value:
                        self.music = value.split(';')
                    else:
                        self.music = [value]
                elif field == 'jacket':
                    self.jacket = value

                cur_line = chart.readline().strip()

            # see if any files contain extra effect audios and note them in a set
            if include_sfx:
                self.sounds = set()
                while cur_line != '':
                    if '.ogg' in cur_line:
                        # extract any .ogg file mentioned in the chart file
                        splits = cur_line.split('=')
                        for s in splits:
                            if '.ogg' in s:
                                self.sounds.add(s.split(';')[0])
                                break
                    cur_line = chart.readline().strip()

            

class SDVXSong:
    def __init__(self, chart_dir, include_sfx=True):
        # make sure chart dir exists
        assert(chart_dir.exists())
        self.dirname = chart_dir
        self.title = None

        # init chart difficulties to None
        self.charts = {}

        # get all .ksh files in directory and init SDVXChart objs with them
        chart_files = [chart for chart in chart_dir.iterdir() if chart.name[-4:] == '.ksh']
        conflicts = set()
        for chart_file in chart_files:
            log.debug(f'Current chart file is {chart_file}')
            chart = SDVXChart(chart_file, include_sfx)
            
            # set chart title, or check if it matches existing name
            if self.title:
                if self.title != chart.title:
                    conflicts.add(chart.title)
                    conflicts.add(self.title)
            else: self.title = chart.title

            # assign chart to appropriate obj field
            self.charts[chart.difficulty] = chart

        if conflicts:
            conflict_list = list(conflicts)
            while True:
                try:
                    log.warn(f'Title conflict detected at song directory {chart_dir}: \n{\
                        '\n'.join([f'[{num}] {title}' for (num, title) in enumerate(conflict_list)])
                    }')
                    number = int(input('Please type a number to specify correct title: '))
                    for chart in self.charts.values():
                        self.update_chart_title(chart, conflict_list[number])
                    break
                except:
                    log.warn('Invalid entry!')

    # Update chart's title
    def update_chart_title(self, chart, new_title):
        chart.title = new_title

        # assemble full chart path using either song dir + filename
        # or the complete filename in case of charts w/custom paths
        full_path = None
        if chart.custom_path:
            full_path = chart.filename
        else:
            full_path = self.dirname / chart.filename

        with full_path.open('r+', encoding='utf-8-sig', errors='ignore') as file:
            # read all lines and find line containing title=, then update title
            lines = file.readlines()
            for i, line in enumerate(lines):
                if line[:6] == 'title=':
                    lines[i] = f'title={new_title}\n'
                    break

            file.seek(0)
            file.writelines(lines)

    # Get all files used by all difficulties of song
    def get_files(self):
        result = set()
        for chart in self.charts.values():
            result.add(str(chart.filename))
            if chart.jacket:
                result.add(chart.jacket)
            if chart.music:
                result.update(chart.music)
            if chart.sounds:
                result.update(chart.sounds)

        return result

    # Get all files associated with a particular difficulty of song
    def get_difficulty_files(self, diff):
        result = set()
        assert(diff in self.charts)
        chart = self.charts[diff]
        result.add(str(chart.filename))
        if chart.jacket:
            result.add(chart.jacket)
        if chart.music:
            result.update(chart.music)
        if chart.sounds:
            result.update(chart.sounds)

        return result

    # Copy files over to a new folder
    def copy_song(self, dest_dir):
        for diff in self.charts.keys():
            # Check if difficulty is hosted at a different directory
            #log.debug(f'Current difficulty is {diff}')
            chart_directory = self.dirname
            if self.charts[diff].custom_path:
                chart_directory = self.charts[diff].filename.parent

            # copy files over
            for file in self.get_difficulty_files(diff):
                file_name = Path(file).name
                full_file_path = chart_directory / file_name
                dest_file_path = dest_dir / file_name
                if not dest_file_path.exists():
                    copy(full_file_path, dest_dir)


class SDVXCollection:
    def __init__(self, collection_dir, include_sfx=True):
        # make sure collection dir exists
        collection_dir_path = Path(collection_dir)
        assert(collection_dir_path.exists())

        # init song dict and other fields
        self.collection = {}
        self.path = collection_dir_path.resolve()

        # iterate through all directories in collection dir and init
        self.init_folder(collection_dir_path, include_sfx)

    # Check for the presence of .ksh files in directory
    def is_song_directory(self, song_dir):
        return [file for file in song_dir.iterdir() if file.name[-4:] == '.ksh'] != []
    
    # Initialize a collection folder, iterating through its contents and creating
    # SDVXSongs out of each song folder contained inside
    # Recursive function to handle subfolders
    def init_folder(self, collection_dir, include_sfx):
        # iterate through folder contents
        for songdir in collection_dir.iterdir():
            if songdir.is_dir():
                # if folder contains ksh charts, init SDVXSong obj
                if self.is_song_directory(songdir):
                    log.debug(f'Initiating SDVXSong at {songdir}')
                    song = SDVXSong(songdir, include_sfx)

                    # if song title does not exist in collection, add it
                    # otherwise, attempt to merge SDVXSongs into one
                    if song.title not in self.collection:
                        log.debug(f'Adding {song.title} located at {songdir} to collection!')
                        self.collection[song.title] = song
                    else:
                        log.warn(f'Song {song.title} at {songdir} already exists at {self.collection[song.title].dirname}.')
                        canon = self.merge_songs(self.collection[song.title], song)
                        if canon:
                            #pass
                            log.info(f'Successfully merged under {canon.dirname}!')
                        else:
                            #pass
                            log.warn('Failed to merge!')
                # otherwise, recursive call init_folder on subfolder
                else:
                    self.init_folder(songdir, include_sfx)

    # Merge song folders that contain INF/GRV/VVD/XCD with their regular counterparts
    # Returns the main song path to be used
    def merge_songs(self, song1, song2):
        main_song = None
        mxm_song = None

        # Determine which song is canonical by checking if either lack/contain a MXM
        if 'MXM' in song1.charts and not 'MXM' in song2.charts:
            main_song = song2
            mxm_song = song1
            self.collection[song1.title] = song2
        elif not 'MXM' in song1.charts and 'MXM' in song2.charts:
            main_song = song1
            mxm_song = song2
        else:
            log.warn(f'Neither difficulty of {song1.title} contains a MXM!')
            return

        # Generate full (relative path) of mxm_song and edit mxm chart to use it
        # Then set main_song's MXM to mxm_song's MXM
        if not mxm_song.charts['MXM'].custom_path:
            #mxm_path = os.path.join(mxm_song.dirname, os.path.basename(mxm_song.charts['MXM'].filename))
            mxm_path = mxm_song.dirname / mxm_song.charts['MXM'].filename.name
            mxm_song.charts['MXM'].filename = mxm_path
            mxm_song.charts['MXM'].custom_path = True
        main_song.charts['MXM'] = mxm_song.charts['MXM']

        del mxm_song
        return main_song
    
    # Search for a string in song list
    def search_song(self, query):
        results = []
        for song in self.collection.keys():
            if query in song:
                results.append(song)

        return results
