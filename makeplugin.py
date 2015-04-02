#!/usr/bin/python
# -*- coding: utf-8 -*-


__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

import os
from glob import glob

from makezip import createZipFile

if __name__=="__main__":
    
    filename="EpubSplit.zip"
    exclude=['*.pyc','*~','*.xcf','*[0-9].png','BeautifulSoup.py','makezip.py','makeplugin.py','*.po','*.pot','*default.mo']
    # from top dir. 'w' for overwrite
    #from calibre-plugin dir. 'a' for append
    files=['images','translations']
    files.extend(glob('*.py'))
    files.extend(glob('plugin-import-name-*.txt'))
    createZipFile(filename,"w",
                  files,exclude=exclude)
    
