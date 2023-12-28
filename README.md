# KSM Collection Merger
A program made to organize one collection or merge two collections of [SOUND VOLTEX](https://en.wikipedia.org/wiki/Sound_Voltex) charts converted for [K-Shoot Mania](https://kshootmania.com) or [unnamed\_sdvx\_clone](https://github.com/Drewol/unnamed-sdvx-clone). This program can either organize one collection or merge two chart collections such that the final collection will have charts sorted by game of origin, and each song's folder will be named according to its romanization on [RemyWiki](https://remywiki.com), if available.

## Requirements
### Dependencies
* [Python 3.12+](https://python.org)
* [AIOHTTP](https://docs.aiohttp.org/en/stable/)
* [Beautiful Soup 4](https://pypi.org/project/beautifulsoup4/)

You can install the Python dependencies with `pip`:
```
pip install -r requirements.txt
```

### Other Requirements
You will also need one or two collections of KSM/USC charts to merge. Currently, only `.ksm` format charts are supported.
* The first collection can be organized in any way.
* The second collection must have songs organized by SOUND VOLTEX game name; specifically, there should only be folders titled `SDVX BOOTH`, `SDVX Infinite Infection`, `SDVX Gravity Wars`, `SDVX Heavenly Haven`, `SDVX Vivid Wave`, and `SDVX Exceed Gear`. A good example of such a collection is the [SDVX 1-5 Pack on oniichan.wtf](https://oniichan.wtf/help/songs.html).
    * If an empty second collection is supplied to the program, it will instead organize the first collection. See [Usage](#usage) for info.
* Both collections **should only contain converts from SOUND VOLTEX**. While the program will still run if some charts are not from the game, you will be prompted to supply a name and/or game of origin for each chart. This will also happen if any title query to the wiki is unsuccessful at retrieving a title romanization and/or game of origin.
* Both collections should also have **consistent title metadata** in each chart file, if possible. If a song folder contains two chart files with differing titles, you will be prompted to correct them. See [Options](#options) for more info.

## Usage
```console
$ python merger.py -l LEFT -r RIGHT -o OUTPUT [-v]
```

### Options
* `-l LEFT` or `--left LEFT`: Directory of the first collection.
* `-r RIGHT` or `--right RIGHT`: Directory of the second collection.
* `-o OUTPUT` or `--output OUTPUT`: Directory of the final (merged) collection.
* `-h` or `--help`: Show the help message.
* `-v` or `--verbose`: Print debugging messages during the merging process.

The program will merge the collections located at `LEFT` and `RIGHT` and output the newly organized collection to `OUTPUT`. Note that if `RIGHT` is an empty directory, the program will simply output an organized version of `LEFT`.

Note that an additional `data.json` file will be written to both `LEFT` and `RIGHT`. This JSON file contains song/chart metadata for both collections, allowing the merger script to be run again without having to read each chart file again during initialization.

If the program detects that two or more charts in a song folder contain different titles, it will prompt you to specify which one is the correct one, and will also modify each chart file accordingly.

If the program failed to find a romanization and/or game of origin for a particular song, it will prompt you to supply that information.

The final output collection will have songs organized by their game of origin, while each individual song folder will be named according to its romanization on RemyWiki.

## License
This project is licensed under the terms of the GNU GPL-3.0 license. See the `LICENSE` file for more information.
