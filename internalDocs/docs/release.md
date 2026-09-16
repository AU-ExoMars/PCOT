# Release procedure

To make a new release, follow this checklist.

1. Create a new version number and codeword. For the version number, use
   [semantic versioning](https://semver.org). This means:
    * Version number in MAJOR.MINOR.PATCH format
    * append "-alpha" if we are still in alpha
    * increment the MAJOR number if backward incompatible changes are introduced
    * increment the MINOR number if new, backward compatible changes are introduced
      OR if deprecating functionality.
    * increment the PATCH number if backward compatible bug fixes are introduced
    * The version codeword is a helpful mnemonic. We were
      using a script to generate [Rainbow codes](http://pale.org/rainbow.php), but
      we've now moved on to [Megalithic sites in the UK](https://m.megalithic.co.uk/asb_mapsquare.php)
      running through letters of the alphabet and roughly south to north,
      trying to stick with more memorable names.
1. Edit **PCOT/src/pcot/VERSION.txt** to add the new version data, also
   specifying the date (in ISO 8601, YYYY-MM-DD format).
1. Edit **PCOT/pyproject.toml** to add the new version data.
1. Run **poetry install** on both Windows and Linux and check PCOT
   still runs (and that the title bar and About version data is correct)
1. Run **generate_autodocs.py** in **mkdocs/docs** to get up-to-date
   autodocs.
1. Create a list of the changes by looking at the Git log and add this
   to **PCOT/mkdocs/docs/releases.md** under a new section for the new
   release.
1. Check **mkdocs/docs/userguide/update.md** for any release-specific update notes
   (e.g. the LITTLE DENNIS Conda-rebuild section added for the 1.0.0-beta release).
   These should probably be removed once that release is no longer current, or
   generalised into something like "when updating from versions older than LITTLE
   DENNIS to newer ones, do X" so the instructions don't go stale.
1. ~~Make **pyInstaller** builds for Windows and Linux.~~ **We no longer do PyInstaller
   builds - they proved too unreliable.** The steps are left below for reference in case
   we revisit this.
1. Upload the docs to the documentation site.
1. Commit with "version bump for release (VERSION NAME)" in the text
1. Make sure the dev branch is merged into the master branch.
1. Make a release tag in the repository.


## Making a MacOS build

**No longer done - kept for reference, see the note on PyInstaller builds above.**

This is currently a bit more complicated because I'm having to
commandeer a teaching machine to do it on.

1. download the code 
2. ```export PATH=/usr/local/anaconda3/bin/:$PATH```
3. ```echo ". /usr/local/anaconda3/etc/profile.d/conda.sh" >> ~/.bash_profile```
4. ```source ~/.bash_profile```
5. ```conda create -n pcot python=3.8 poetry=1.1.6```
6. ```conda activate pcot```
7. ```poetry install```
8. run pcot (to test)
9. remove references to splash screen from main.py
(the try block which doesn't currently work)
10. run pcot again to make sure it's still fine
11. ```pip3 install pyinstaller```
12. cd into pyinstaller dir
13. ```pyinstaller macos.spec```
14. ```conda deactivate```
15. ```dist/pcot``` to test
16. rename **dist/pcot** to **dist/pcot-macos**

## Uploading to the release repo

**No longer done - kept for reference, see the note on PyInstaller builds above.**

This currently uses Jim Finnis' Femtomine server system.
I'm not going to talk about how Femtomine works here - it's a fairly
complex command-line app (at least for adding data). Assuming you
have installed FM and the remote mine link is set up, the commands
to add the new files and set the text metadata are:

```sh
femtomine add pcot-windows.exe --tkey=brief_md --textfile=windows_note +new +v0.2.0
femtomine add pcot-linux.exe --tkey=brief_md --textfile=linux_note +new +v0.2.0
femtomine add pcot-macos.exe --tkey=brief_md --textfile=macos_note +new +v0.2.0
```
assuming that all files are in the current working directory - and you'll have to change
the version number tag! 

This will take some time, and the new items will not appear in the query results until their tags
are set. Once they are uploaded, set this up by first removing the "latest" tag from the current
latest items and then adding tags to the newly uploaded items:
```sh
femtomine mod :latest +latest
femtomine mod :new,+latest,+pcot,+apps +new
```


