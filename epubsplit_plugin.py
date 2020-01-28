#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2020, Jim Miller'
__docformat__ = 'restructuredtext en'

import logging
logger = logging.getLogger(__name__)

import time, os, copy, threading
from io import BytesIO
from functools import partial
from datetime import datetime

import six
from six.moves.configparser import SafeConfigParser
from six import text_type as unicode

try:
    from PyQt5.Qt import (QApplication, QCursor, Qt, QMenu, QToolButton)
except ImportError as e:
    from PyQt4.Qt import (QApplication, QCursor, Qt, QMenu, QToolButton)

from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.ebooks.metadata.meta import get_metadata
from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.message_box import ViewLog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.utils.date import local_tz

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubsplit.common_utils import (set_plugin_icon_resources, get_icon)

from calibre_plugins.epubsplit.config import prefs

from calibre_plugins.epubsplit.epubsplit import SplitEpub

from calibre_plugins.epubsplit.dialogs import (
    LoopProgressDialog,
    SelectLinesDialog
    )

PLUGIN_ICONS = ['images/icon.png']

class EpubSplitPlugin(InterfaceAction):

    name = 'EpubSplit'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('EpubSplit'), None,
                   _('Split off part of an EPUB into a new book.'), ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    # make button menu drop down only
    #popup_type = QToolButton.InstantPopup

    # disable when not in library. (main,carda,cardb)
    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        # Read the plugin icons and store for potential sharing with the config widget
        icon_resources = self.load_resources(PLUGIN_ICONS)
        set_plugin_icon_resources(self.name, icon_resources)

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.

        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        icon = get_icon('images/icon.png')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def plugin_button(self):
        self.t = time.time()

        if len(self.gui.library_view.get_selected_ids()) != 1:
            d = error_dialog(self.gui,
                             _('Select One Book'),
                             _('Please select exactly one book to split.'),
                             show_copy_button=False)
            d.exec_()
        else:
            self.previous = self.gui.library_view.currentIndex()
            db=self.gui.current_db
            self.book_count = 1 # for series Source columns

            #logger.debug("1:%s"%(time.time()-self.t))
            self.t = time.time()

            source_id = self.gui.library_view.get_selected_ids()[0]

            misource = db.get_metadata(source_id, index_is_id=True)

            if db.has_format(source_id,'EPUB',index_is_id=True):
                splitepub = SplitEpub(BytesIO(db.format(source_id,'EPUB',index_is_id=True)))
                from calibre.ebooks.oeb.polish.container import get_container
                container = get_container(db.format_abspath(source_id,'EPUB',index_is_id=True))
                if container.opf_version_parsed.major >= 3:
                    d = error_dialog(self.gui, _('EPUB3 Detected'),
                                     _('This plugin only works on EPUB2 format ebooks.'))
                    d.exec_()
                    return
            else:
                d = error_dialog(self.gui, _('No EPUB'),
                                 _('This plugin only works on EPUB format ebooks.'))
                d.exec_()
                return

            lines = splitepub.get_split_lines()

            # for line in lines:
            #     logger.debug("line(%d):%s"%(line['num'],line))
            # logger.debug()

            d = SelectLinesDialog(self.gui,
                                  _('Select Sections to Split Off'),
                                  prefs,
                                  self.qaction.icon(),
                                  lines,
                                  partial(self._do_split, db, source_id, misource, splitepub, lines),
                                  partial(self._do_splits, db, source_id, misource, splitepub, lines),
                                  partial(self._get_split_size, splitepub),
                                  partial(self.interface_action_base_plugin.do_user_config,parent=self.gui)
                                  )
            d.exec_()

            return

            if d.result() != d.Accepted:
                return

    def has_lines(self,linenums):
        if len(linenums) < 1:
            error_dialog(self.gui,
                         _('No Sections Selected'),
                         _("Book(s) not split.\n\nYou must select at least one section to split."),
                         show_copy_button=False).exec_()
            return False
        else:
            return True

    def _do_splits(self,
                   db,
                   source_id,
                   misource,
                   splitepub,
                   origlines,
                   newspecs):

        linelists, changedtocs, checkedalways = newspecs
        # logger.debug(linelists)
        if not self.has_lines(linelists):
            return
        LoopProgressDialog(self.gui,
                           linelists,
                           partial(self._do_splits_loop,
                                   db=db,
                                   source_id=source_id,
                                   misource=misource,
                                   changedtocs=changedtocs,
                                   checkedalways=checkedalways,
                                   splitepub=splitepub,
                                   origlines=origlines),
                           self._do_splits_finish,)

    def _do_splits_finish(self,linelists):
        info_dialog(self.gui, _('New Books Created'),
                    _('%s New Books Created.')%len(linelists)).exec_()

    def _do_splits_loop(self,
                        linelist,
                        db=None,
                        source_id=None,
                        misource=None,
                        changedtocs=None,
                        checkedalways=None,
                        splitepub=None,
                        origlines=None,
                        ):
        #logger.debug("origline:%s"%origlines[l])
        try:
            if linelist[0] in changedtocs:
                deftitle=changedtocs[linelist[0]][0] # already unicoded()'ed
            else:
                deftitle=unicode(origlines[linelist[0]]['toc'][0])
        except:
            # catches empty chapter titles
            deftitle=None
        self._do_split(db,
                       source_id,
                       misource,
                       splitepub,
                       origlines,
                       (linelist,changedtocs,checkedalways),
                       deftitle=deftitle)

    def _get_split_size(self,splitepub,newspecs):
        try:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            self.gui.status_bar.show_message(_('Computing size of EPUB...'), 60000)
            linenums, changedtocs, checkedalways = newspecs
            if not self.has_lines(linenums):
                return
            self.t = time.time()
            outputepub = PersistentTemporaryFile(suffix='.epub')
            outlist = list(set(linenums + checkedalways))
            outlist.sort()
            splitepub.write_split_epub(outputepub,
                                       outlist,
                                       changedtocs=changedtocs,)
            logger.debug("size:%s"%(time.time()-self.t))
            self.t = time.time()
        finally:
            self.gui.status_bar.show_message(_('Finished computing size of EPUB.'), 3000)
            QApplication.restoreOverrideCursor()
        info_dialog(self.gui, _('Size of New Book'),
                    _('New EPUB File Size:') + ' ' + humanbytes(os.path.getsize(outputepub.name)),
                    show_copy_button=False).exec_()

    def _do_split(self,
                  db,
                  source_id,
                  misource,
                  splitepub,
                  origlines,
                  newspecs,
                  deftitle=None):

        linenums, changedtocs, checkedalways = newspecs
        # logger.debug("updated tocs:%s"%changedtocs)
        if not self.has_lines(linenums):
            return
        #logger.debug("2:%s"%(time.time()-self.t))
        self.t = time.time()

        #logger.debug("linenums:%s"%linenums)

        defauthors = None

        if not deftitle and prefs['copytoctitle']:
            if linenums[0] in changedtocs:
                deftitle=changedtocs[linenums[0]][0] # already unicoded()'ed
            elif len(origlines[linenums[0]]['toc']) > 0:
                deftitle=unicode(origlines[linenums[0]]['toc'][0])
            #logger.debug("deftitle:%s"%deftitle)

        if not deftitle and prefs['copytitle']:
            deftitle = _("%s Split") % misource.title

        if prefs['copyauthors']:
            defauthors = misource.authors

        mi = MetaInformation(deftitle,defauthors)

        if prefs['copytags']:
            mi.tags = misource.tags # [item for sublist in tagslists for item in sublist]

        if prefs['copylanguages']:
            mi.languages = misource.languages

        if prefs['copyseries']:
            mi.series = misource.series

        if prefs['copydate']:
            mi.timestamp = misource.timestamp

        if prefs['copyrating']:
            mi.rating = misource.rating

        if prefs['copypubdate']:
            mi.pubdate = misource.pubdate

        if prefs['copypublisher']:
            mi.publisher = misource.publisher

        if prefs['copyidentifiers']:
            mi.set_identifiers(misource.get_identifiers())

        if prefs['copycomments'] and misource.comments:
            mi.comments = "<p>"+_("Split from:")+"</p>" + misource.comments

        #logger.debug("mi:%s"%mi)
        book_id = db.create_book_entry(mi,
                                       add_duplicates=True)

        if prefs['copycover'] and misource.has_cover:
            db.set_cover(book_id, db.cover(source_id,index_is_id=True))

        #logger.debug("3:%s"%(time.time()-self.t))
        self.t = time.time()

        custom_columns = self.gui.library_view.model().custom_columns
        for col, action in six.iteritems(prefs['custom_cols']):
            #logger.debug("col: %s action: %s"%(col,action))

            if col not in custom_columns:
                #logger.debug("%s not an existing column, skipping."%col)
                continue

            coldef = custom_columns[col]
            #logger.debug("coldef:%s"%coldef)
            label = coldef['label']
            value = db.get_custom(source_id, label=label, index_is_id=True)
            if value:
                db.set_custom(book_id,value,label=label,commit=False)

        #logger.debug("3.5:%s"%(time.time()-self.t))
        self.t = time.time()

        if prefs['sourcecol'] != '' and prefs['sourcecol'] in custom_columns \
                and prefs['sourcetemplate']:
            val = SafeFormat().safe_format(prefs['sourcetemplate'], misource, 'EpubSplit Source Template Error', misource)
            #logger.debug("Attempting to set %s to %s"%(prefs['sourcecol'],val))
            label = custom_columns[prefs['sourcecol']]['label']
            if custom_columns[prefs['sourcecol']]['datatype'] == 'series':
                val = val + (" [%s]"%self.book_count)
            db.set_custom(book_id, val, label=label, commit=False)
        self.book_count = self.book_count+1
        db.commit()

        #logger.debug("4:%s"%(time.time()-self.t))
        self.t = time.time()

        self.gui.library_view.model().books_added(1)
        self.gui.library_view.select_rows([book_id])

        #logger.debug("5:%s"%(time.time()-self.t))
        self.t = time.time()

        editconfig_txt = _('You can enable or disable Edit Metadata in Preferences > Plugins > EpubSplit.')
        if prefs['editmetadata']:
            confirm('\n'+_('''The book for the new Split EPUB has been created and default metadata filled in.

However, the EPUB will *not* be created until after you've reviewed, edited, and closed the metadata dialog that follows.

You can fill in the metadata yourself, or use download metadata for known books.

If you download or add a cover image, it will be included in the generated EPUB.''')+'\n\n'+
                    editconfig_txt+'\n',
                    'epubsplit_created_now_edit_again',
                    self.gui)
            self.gui.iactions['Edit Metadata'].edit_metadata(False)

        try:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            #logger.debug("5:%s"%(time.time()-self.t))
            self.t = time.time()
            self.gui.tags_view.recount()

            self.gui.status_bar.show_message(_('Splitting off from EPUB...'), 60000)

            mi = db.get_metadata(book_id,index_is_id=True)

            outputepub = PersistentTemporaryFile(suffix='.epub')

            coverjpgpath = None
            if mi.has_cover:
                # grab the path to the real image.
                coverjpgpath = os.path.join(db.library_path, db.path(book_id, index_is_id=True), 'cover.jpg')

            outlist = list(set(linenums + checkedalways))
            outlist.sort()
            splitepub.write_split_epub(outputepub,
                                       outlist,
                                       changedtocs=changedtocs,
                                       authoropts=mi.authors,
                                       titleopt=mi.title,
                                       descopt=mi.comments,
                                       tags=mi.tags,
                                       languages=mi.languages,
                                       coverjpgpath=coverjpgpath)

            #logger.debug("6:%s"%(time.time()-self.t))
            self.t = time.time()
            db.add_format_with_hooks(book_id,
                                     'EPUB',
                                     outputepub, index_is_id=True)

            #logger.debug("7:%s"%(time.time()-self.t))
            self.t = time.time()

            self.gui.status_bar.show_message(_('Finished splitting off EPUB.'), 3000)
            self.gui.library_view.model().refresh_ids([book_id])
            self.gui.tags_view.recount()
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, self.previous)
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
        finally:
            QApplication.restoreOverrideCursor()

        if not prefs['editmetadata']:
            confirm('<p>'+
                    '</p><p>'.join([_('<b><u>%s</u> by %s</b> has been created and default metadata filled in.')%(mi.title,', '.join(mi.authors)),
                                   _('EpubSplit now skips the Edit Metadata step by default.'),
                                   editconfig_txt])+
                    '</p>',
                    'epubsplit_created_now_no_edit_again',
                    self.gui)

    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs

    def get_splitepub(self, *args, **kwargs):
        return SplitEpub(*args, **kwargs)

def humanbytes(B):
   'Return the given bytes as a human friendly KB, MB, GB, or TB string'
   B = float(B)
   KB = float(1024)
   MB = float(KB ** 2) # 1,048,576
   GB = float(KB ** 3) # 1,073,741,824
   TB = float(KB ** 4) # 1,099,511,627,776

   if B < KB:
      return '{0} {1}'.format(B,'Bytes' if 0 == B > 1 else 'Byte')
   elif KB <= B < MB:
      return '{0:.2f} KB'.format(B/KB)
   elif MB <= B < GB:
      return '{0:.2f} MB'.format(B/MB)
   elif GB <= B < TB:
      return '{0:.2f} GB'.format(B/GB)
   elif TB <= B:
      return '{0:.2f} TB'.format(B/TB)
