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
1. Using GIMP, edit the **splash.xcf** file in the pyInstaller directory
   to update the version string, and export it to **splash.png** (hopefully
   this annoying step will be streamlined in the future).
1. Run **poetry install** on both Windows and Linux and check PCOT
   still runs (and that the title bar and About version data is correct)
1. Create a list of the changes by looking at the Git log and add this
   to **PCOT/mkdocs/docs/releases.md** under a new section for the new
   release.
1. Make **pyInstaller** builds for Windows and Linux (at least) and
   check they work, fixing if necessary.
1. Upload the releases to the release site.
1. Upload the docs to the documentation site.
1. Make sure the dev branch is merged into the master branch.
1. Make a release tag in the repository.

