# KSM Collection Merger
A program made to organize one collection or merge two collections of [SOUND VOLTEX](https://remywiki.com/What_is_SOUND_VOLTEX) charts converted for [K-Shoot Mania](https://kshootmania.com) or [unnamed\_sdvx\_clone](https://github.com/Drewol/unnamed-sdvx-clone). This program can either organize one collection or merge two chart collections such that the final collection will have charts sorted by game of origin, and each song's folder will be named according to its romanization on [RemyWiki](https://remywiki.com), if available.

## Requirements
### Dependencies
* [Python 3+](https://python.org)
* [Requests](https://requests.readthedocs.io/en/latest/)
* [html\_to\_json](https://pypi.org/project/html-to-json/)

You can install the Python dependencies with `pip`:
```
pip install -r requirements.txt
```

### Other Requirements
You will also need one or two collections of KSM/USC charts to merge. Currently, only `.ksm` format charts are supported.
* The first collection can be organized in any way.
* The second collection must have songs organized by SOUND VOLTEX game name; specifically, there should only be folders titled `SDVX BOOTH`, `SDVX Infinite Infection`, `SDVX Gravity Wars`, `SDVX Heavenly Haven`, `SDVX Vivid Wave`, and `SDVX Exceed Gear`. A good example of such a collection is the [SDVX 1-5 Pack on oniichan.wtf](https://oniichan.wtf/help/songs.html).
    * If an empty second collection is supplied to the program, it will instead organize the first collection. See [Usage](#usage) for info.
* Both collections **should only contain converts from SOUND VOLTEX**. While the program will still run if a chart is not from the game, you will be prompted to supply a name and/or game of origin for said chart. This will also happen if any title query to the wiki is unsuccessful at retrieving a title romanization and/or game of origin.
* Both collections must also have **consistent title metadata** in each chart file. If a song folder contains two chart files with differing titles, the program will fail; see [Title Conflicts](#title-conflicts) for info.

## Usage
```console
$ python merger.py -l LEFT -r RIGHT -o OUTPUT
```

### Options
* `-l LEFT` or `--left LEFT`: Directory of the first collection.
* `-r RIGHT` or `--right RIGHT`: Directory of the second collection.
* `-o OUTPUT` or `--output OUTPUT`: Directory of the final (merged) collection.
* `-h` or `--help`: Show the help message.
* `-v` or `--verbose`: Print debugging messages during the merging process.

The program will merge the collections located at `LEFT` and `RIGHT` and output the newly organized collection to `OUTPUT`. Note that if `RIGHT` is an empty directory, the program will simply output an organized version of `LEFT`.

If the program failed to find a romanization and/or game of origin for a particular song, it will prompt you to supply that information.

The final output collection will have songs organized by their game of origin, while each individual song folder will be named according to its romanization on RemyWiki.

### Title Conflicts

If a song folder contains two chart files that have differing `title` metadata, the program will fail due to a failed check to make sure all charts have the same title. This program currently cannot resolve such conflicts automatically. However, if you run the program with the `--verbose` flag, it will output the name and location of each chart file that it is processing, including that which caused the program failure. Knowing that file, you can edit it and correct its title metadata to match that of the other charts within its song folder.

Here is an example output from the program, assuming it was run from the directory `/data/sdvx`:
```console
[INFO] Initializing left collection
[DEBUG] Initiating SDVXSong left/random in init_folder!
[DEBUG] Current chart file is left/random/MXM.ksh
[DEBUG] Current chart file is left/random/EXH.ksh
Traceback (most recent call last):
  File "/data/sdvx/merger.py", line 290, in <module>
    main(args)
  File "/data/sdvx/merger.py", line 165, in main
    left = libsdvx.SDVXCollection(args.left, verbose=args.verbose)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/sdvx/libsdvx.py", line 149, in __init__
    self.init_folder(collection_dir, include_sfx, verbose)
  File "/data/sdvx/libsdvx.py", line 166, in init_folder
    song = SDVXSong(fullpath, include_sfx, verbose)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/data/sdvx/libsdvx.py", line 87, in __init__
    assert(chart.title == self.title)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```
Since the files `left/random/EXH.ksh` and `left/random/MXM.ksh` appear right before the `AssertionError`, this means that they are the source of the error.

## License
This project is licensed under the terms of the GNU GPL-3.0 license. See the `LICENSE` file for more information.
