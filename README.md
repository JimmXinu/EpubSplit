# EpubSplit

This is a repository for the EpubSplit Calibre Plugin.

Most discussion of this plugin takes place in the [EpubSplit Calibre Plugin forum].

Splitting omnibus eBooks into multiple eBooks seems to be a common request, but there haven't been many tools to do so without a lot of hand editing.

This plugin provides the ability to create new EPUBs by splitting off part of an existing (non-DRM) EPUB format eBook.

Main Features of EpubSplit Plugin:

* Present the user with a list of 'split lines' in the existing EPUB. The beginning of each file listed in the manifest spine and each Table of Contents(TOC) entry. <guide> tagged files are also indicated.
* 'Preview' contents of each 'split line' as a tooltip over the HREF.
* Allow user to edit the TOC entry(s) for each 'line'.
* Select one or more of the offered lines to include in the new eBook,
* Edit the metadata for the new split eBook, and then,
* Extract only the selected contents of the source EPUB into the new EPUB,
* Scan the selected content for CSS & image links for additional files to include,
* Scan the selected content for internal links and anchors and update links that need to point to different filenames,
* Use the metadata entered into calibre for the new eBook (including cover) as the metadata in the new EPUB.
* Return to list of source EPUB sections after creating a new split EPUB.
* Configure which metadata from source EPUB to copy to new eBook, now offering more of the standard metadata and custom columns.
* Configurably populate a custom column with the source book title/author/etc.
* CLI via `calibre-debug --run-plugin EpubSplit -- [options] <input epub> [line numbers...]`

While EpubSplit doesn't have a `pip` package distribution, you can use it as a stand-alone CLI by downloading `epubsplit.py` and executing with python.  However, I offer only minimal support for that option at this time.

[NightMachinary](https://github.com/NightMachinary) has contributed a [zsh script for calling epubsplit.py](https://github.com/JimmXinu/EpubSplit/wiki/Automatic-EPUB-Splitting-(zsh-script))



[EpubSplit Calibre Plugin forum]: http://www.mobileread.com/forums/showthread.php?t=178799

