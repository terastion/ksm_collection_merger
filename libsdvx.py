import os
from tinylog import log, debug
from shutil import copy
#from collections import defaultdict

class SDVXChart:
    difficulties = {\
        'light': 'NOV',\
        'challenge': 'ADV',\
        'extended': 'EXH',\
        'infinite': 'MXM',\
    }
    def __init__(self, chart_file, include_sfx=True):
        # make sure chart file exists
        assert(os.path.exists(chart_file))
        self.filename = os.path.basename(chart_file)
        
        # this gets set to True elsewhere if chart is at different directory than rest of song
        self.custom_path = False

        # Init empty fields in case they're not found in file
        self.title = None
        self.difficulty = None
        self.level = None
        self.music = None
        self.jacket = None
        self.sounds = None

        # read start of ksh file and record desired fields in obj
        with open(chart_file, 'r', encoding='utf-8-sig', errors='ignore') as chart:
            cur_line = chart.readline().strip()
            while cur_line != "" and cur_line != '--':
                if '=' not in cur_line:
                    cur_line = chart.readline().strip()
                    continue

                (field, value) = cur_line.split('=', 1)
                if field == 'title':
                    self.title = value
                #elif field == 'artist':
                #    self.artist = value
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
    def __init__(self, chart_dir, include_sfx=True, verbose=False):
        # make sure chart dir exists
        assert(os.path.isdir(chart_dir))
        self.dirname = chart_dir
        self.title = None

        # init chart difficulties to None
        #self.charts = defaultdict(lambda: None)
        self.charts = {}

        # get all .ksh files in directory and init SDVXChart objs with them
        chart_files = [chart for chart in os.listdir(chart_dir) if chart[-4:] == '.ksh']
        conflicts = set()
        for chart_file in chart_files:
            debug(verbose, f'Current chart file is {os.path.join(chart_dir, chart_file)}')
            chart = SDVXChart(os.path.join(chart_dir, chart_file), include_sfx)
            
            # set chart title, or check if it matches existing name
            if self.title:
                #assert(chart.title == self.title)
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
                    number = int(input(f'Title conflict detected:\n{'\n'.join([f'[{num}] {title}' for (num, title) in enumerate(conflict_list)])}\nPlease type a number: '))
                    for chart in self.charts.values():
                        self.update_chart_title(chart, conflict_list[number])
                    break
                except:
                    print('Invalid entry!')

    # Update chart's title
    def update_chart_title(self, chart, new_title):
        chart.title = new_title
        full_path = ""
        if chart.custom_path:
            full_path = chart.filename
        else:
            full_path = os.path.join(self.dirname, chart.filename)
        with open(full_path, 'r+', encoding='utf-8-sig', errors='ignore') as file:
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
        for h in self.charts.values():
            result.add(h.filename)
            result.add(h.jacket)
            result.update(h.music)
            result.update(h.sounds)

        return result

    # Get all files associated with a particular difficulty of song
    def get_difficulty_files(self, diff):
        result = set()
        assert(diff in self.charts)
        chart = self.charts[diff]
        result.add(chart.filename)
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
            #debug(verbose, f'Current difficulty is {diff}')
            chart_directory = self.dirname
            if self.charts[diff].custom_path:
                chart_directory = os.path.dirname(self.charts[diff].filename)

            # copy files over
            for file in self.get_difficulty_files(diff):
                file_name = os.path.basename(file)
                full_file_path = os.path.join(chart_directory, file_name)
                dest_file_path = os.path.join(dest_dir, file_name)
                if not os.path.exists(dest_file_path):
                    copy(full_file_path, dest_dir)


class SDVXCollection:
    def __init__(self, collection_dir, include_sfx=True, verbose=False):
        # make sure collection dir exists
        assert(os.path.isdir(collection_dir))

        # init song dict and other fields
        #self.collection = defaultdict(lambda: None)
        self.collection = {}
        self.path = os.path.realpath(collection_dir)

        # iterate through all directories in collection dir and init
        self.init_folder(collection_dir, include_sfx, verbose)

    # Check for the presence of .ksh files in directory
    def is_song_directory(self, song_dir):
        return [file for file in os.listdir(song_dir) if file[-3:] == 'ksh'] != []
    
    # Initialize a collection folder, iterating through its contents and creating
    # SDVXSongs out of each song folder contained inside
    # Also recursive!
    def init_folder(self, collection_dir, include_sfx, verbose):
        # iterate through folder contents
        for songdir in os.listdir(collection_dir):
            fullpath = os.path.join(collection_dir, songdir)
            if os.path.isdir(fullpath):
                # if folder contains ksh charts, init SDVXSong obj
                if self.is_song_directory(fullpath):
                    debug(verbose, f'Initiating SDVXSong {fullpath} in init_folder!')
                    song = SDVXSong(fullpath, include_sfx, verbose)

                    # if song title does not exist in collection, add it
                    # otherwise, attempt to merge SDVXSongs into one
                    if song.title not in self.collection:
                        debug(verbose, f'Adding {song.title} to collection!')
                        self.collection[song.title] = song
                    else:
                        log('warn', f'Song {song.title} at {fullpath} already exists at {self.collection[song.title].dirname}.')
                        canon = self.merge_songs(self.collection[song.title], song)
                        if canon:
                            #pass
                            log('info', f'Successfully merged under {canon.dirname}!')
                        else:
                            #pass
                            log('warning', 'Failed to merge!')
                # otherwise, recursive call init_folder on subfolder
                else:
                    self.init_folder(fullpath, include_sfx, verbose)

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
            log('warn', f'Neither difficulty of {song1.title} contains a MXM!')
            return

        # Generate full (relative path) of mxm_song and edit mxm chart to use it
        # Then set main_song's MXM to mxm_song's MXM
        if not mxm_song.charts['MXM'].custom_path:
            mxm_path = os.path.join(mxm_song.dirname, os.path.basename(mxm_song.charts['MXM'].filename))
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
