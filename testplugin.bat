
python makeplugin.py

set CALIBRE_DEVELOP_FROM=
set CALIBRE_OVERRIDE_LANG=

calibre-customize -a EpubSplit.zip
calibre-debug -g
