#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2018, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback
from functools import partial
import six
from six import text_type as unicode
from six.moves import range

import logging
logger = logging.getLogger(__name__)

from datetime import datetime

from PyQt5 import QtWidgets as QtGui
from PyQt5 import QtCore
from PyQt5.Qt import (QTableWidget, QVBoxLayout, QHBoxLayout, QProgressDialog, QTimer,
                      QDialogButtonBox, Qt, QAbstractItemView, QTableWidgetItem, QTextBrowser,
                      QMenu, QLabel, QLineEdit, QApplication, QColor, QComboBox)

from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.ebooks.metadata import fmt_sidx

from calibre import confirm_config_name
from calibre.gui2 import dynamic

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubsplit.common_utils \
    import (ReadOnlyTableWidgetItem, SizePersistedDialog,
            ImageTitleLayout, get_icon)

from calibre_plugins.epubsplit.config \
    import (NEW_BOOK_PER, PER_SECTION, PER_N_SECTIONS, PER_N_SPLITS )

SAMPLE_NOTE=_("<p><b><i>Double click to copy from sample.</i></b></p>")

class SelectLinesDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, lines,
                 do_split_fn,
                 do_splits_fn,
                 get_split_size_fn,
                 do_user_config,
                 save_size_name='epubsplit:update list dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui
        self.do_split_fn = do_split_fn
        self.do_splits_fn = do_splits_fn
        self.get_split_size_fn = get_split_size_fn
        self.do_user_config = do_user_config
        self.prefs = prefs
        self.keys=dict()

        self.setWindowTitle(header)
        self.setWindowIcon(icon)

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        title_layout = ImageTitleLayout(self, 'images/icon.png',
                                        header)
        layout.addLayout(title_layout)
        lines_layout = QHBoxLayout()
        layout.addLayout(lines_layout)

        self.lines_table = LinesTableWidget(self)
        lines_layout.addWidget(self.lines_table)

        find_layout = QHBoxLayout()

        findtooltip=_('Search for string in Table of Contents Entries.')
        label = QLabel(_('Find:'))
        label.setToolTip(findtooltip)

        # Button to find the document for something
        self.findButton = QtGui.QPushButton(_('Find'),self)
        self.findButton.clicked.connect(self.find)
        self.findButton.setToolTip(findtooltip)

        # The field into which to type the query
        self.findField = QLineEdit(self)
        self.findField.setToolTip(findtooltip)
        self.findField.returnPressed.connect(self.findButton.setFocus)

        # Find type
        self.findtype = QComboBox(self)
        self.findtype.setToolTip(_('Choose how found entries will be treated.'))
        self.populate_findtype()

        # Case Sensitivity option
        self.caseSens = QtGui.QCheckBox(_('Case sensitive'),self)
        self.caseSens.setToolTip(_("Search for case sensitive string; don't treat Harry, HARRY and harry all the same."))

        find_layout.addWidget(label)
        find_layout.addWidget(self.findField)
        find_layout.addWidget(self.findButton)
        find_layout.addWidget(self.findtype)
        find_layout.addWidget(self.caseSens)

        self.addCtrlKeyPress(QtCore.Qt.Key_F,self.findFocus)
        # self.addCtrlKeyPress(QtCore.Qt.Key_G,self.find)

        layout.addLayout(find_layout)

        options_layout = QHBoxLayout()

        # Button to search the document for something
        config_button = QtGui.QPushButton(_('Configure'),self)
        config_button.clicked.connect(self.user_config)
        config_button.setToolTip(_('Configure Plugin'))
        options_layout.addWidget(config_button)

        button_box = QDialogButtonBox(self)
        new_book = button_box.addButton(_("New Book"), button_box.ActionRole)
        new_book.setToolTip(_("Make <i>one</i> new book containing the sections selected above and then edit its Metadata."))
        new_book.clicked.connect(self.new_book)

        self.new_books_b = button_box.addButton(_("New Book per Section"), button_box.ActionRole)
        (txt,tooltip) = NEW_BOOK_PER[self.prefs['new_book_per']]
        self.new_books_b.setText(txt)
        self.new_books_b.setToolTip(tooltip)
        self.new_books_b.clicked.connect(self.new_books)

        get_split_size = button_box.addButton(_("Get Size"), button_box.ActionRole)
        get_split_size.setToolTip("<i></i>" + _("Calculate the size of the new book from the currently selected sections."))
        get_split_size.clicked.connect(self.get_split_size)

        button_box.addButton(_("Done"), button_box.RejectRole)
        button_box.rejected.connect(self.reject)
        options_layout.addWidget(button_box)

        layout.addLayout(options_layout)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.lines_table.populate_table(lines)
        self.lines_table.show_checkedalways(self.prefs['show_checkedalways'])

    def populate_findtype(self):
        self.findtype.clear()
        self.findtype.addItem(_('Highlight'))
        self.findtype.addItem(_('Select'))
        if self.prefs['show_checkedalways']:
            self.findtype.addItem(_('Check'))

    def user_config(self):
        self.do_user_config()
        self.lines_table.show_checkedalways(self.prefs['show_checkedalways'])
        self.populate_findtype()
        (txt,tooltip) = NEW_BOOK_PER[self.prefs['new_book_per']]
        self.new_books_b.setText(txt)
        self.new_books_b.setToolTip(tooltip)

    def get_split_size(self):
        self.get_split_size_fn(self.get_selected_linenums_tocs())

    def new_book(self):
        self.do_split_fn(self.get_selected_linenums_tocs())

    def new_books(self):
        if not self.lines_table.selected_all_have_toc():
            if not confirm("<p><b>"+_('Missing Title(s)')+"</b></p><p>"+
                           ("</p><p>").join([_("Some selected sections don't have a Table of Contents text."),
                                             _("If you continue, those sections will be included with the last prior section that did have a Table of Contents text."),
                                             _("If you cancel, you can go back and add Table of Contents entries.")+" "+
                                             _("Double click to edit the Table of Contents entry for a section.")])
                           +"</p>",
                           'epubsplit_missing_tocs_warning_again',
                           self.gui):
                return
        # return a list of lists of linenums
        self.do_splits_fn(self.lines_table.get_selected_tocs())

    def get_selected_linenums_tocs(self):
        return self.lines_table.get_selected_linenums_tocs()

    def addCtrlKeyPress(self,key,func):
        # print("addKeyPress: key(0x%x)"%key)
        # print("control: 0x%x"%QtCore.Qt.ControlModifier)
        self.keys[key]=func

    def keyPressEvent(self, event):
        # print("event: key(0x%x) modifiers(0x%x)"%(event.key(),event.modifiers()))
        if (event.modifiers() & QtCore.Qt.ControlModifier) and event.key() in self.keys:
            func = self.keys[event.key()]
            return func()
        else:
            return SizePersistedDialog.keyPressEvent(self, event)

    def findFocus(self):
        # print("findFocus called")
        self.findField.setFocus()
        self.findField.selectAll()

    def find(self):
        query = self.findField.text()
        if not self.caseSens.isChecked():
            query = query.lower()
        logger.debug("find:%s"%query)

        # colors copied from Calibre.
        highlightcolor = QColor('#027524') if QApplication.instance().is_dark_theme else QColor('#b4ecb4')

        for row in range(self.lines_table.rowCount()):
            text = self.lines_table.get_row_toc(row)
            if not self.caseSens.isChecked():
                text = text.lower()

            found = False
            if query in text:
                logger.debug("found(%s):%s"%(row,text))
                checkstate = Qt.Checked
                found = True
            else:
                checkstate = Qt.Unchecked

            if self.findtype.currentText() == _('Check'):
                # checkbox
                self.lines_table.item(row,0).setCheckState(checkstate)

            if self.findtype.currentText() == _('Select'):
                # select - need to select each cell in row.
                for col in range(self.lines_table.columnCount()):
                    self.lines_table.item(row,col).setSelected(found)

            if self.findtype.currentText() == _('Highlight'): # Highlight
                tocitem = self.lines_table.item(row,3)
                if found:
                    tocitem.setBackground(highlightcolor)
                else:
                    # copy unhighlighted background from href cell.
                    tocitem.setBackground(self.lines_table.item(row,1).background())

class LinesTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def populate_table(self, lines):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(lines))
        header_labels = ['', _('HREF'), _('Guide'), _('Table of Contents')] #, 'extra'
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().hide()

        self.lines={}
        for row, line in enumerate(lines):
            self.populate_table_row(row, line)
            self.lines[row] = line

        # can't connect to individual cells, it seems.
        self.doubleClicked.connect(self.show_tooltip)

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(1, 2)
        self.setMinimumColumnWidth(2, 100)
        self.setMinimumColumnWidth(3, 10)
        self.setMinimumColumnWidth(4, 100)
        self.setMinimumSize(300, 0)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, line):

        if True:
            checkbox_cell = QTableWidgetItem()
            checkbox_cell.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_cell.setCheckState(Qt.Unchecked)
            checkbox_cell.setToolTip(_('Checked sections will be included in <i>all</i> split books.<br>Default title will still be taken from the first <i>selected</i> section, and section order will remain as shown.')+
                                     '<br>'+_('Use Context Menu (right-click) on selected sections to check or uncheck all selected sections.'))
            self.setItem(row, 0, checkbox_cell)

        href = line['href']
        if line['anchor']:
            href = "%s#%s"%(href,line['anchor'])

        href_cell = ReadOnlyTableWidgetItem(href)
        href_cell.setToolTip(line['sample']+SAMPLE_NOTE)
        self.setItem(row, 1, href_cell)

        if 'guide' in line:
            guide = "(%s):%s"%line['guide']
        else:
            guide = ""
        guide_cell = ReadOnlyTableWidgetItem(guide)
        guide_cell.setToolTip(_("Indicates 'special' pages: copyright, titlepage, etc."))
        self.setItem(row, 2, guide_cell)

        toc_str = "|".join(line['toc'])
        toc_cell = QTableWidgetItem(toc_str)
        toc_cell.setData(Qt.UserRole, toc_str)
        toc_cell.setToolTip(_('''Click and copy hotkey to copy text.
Double-click to edit ToC entry.
Pipes(|) divide different ToC entries to the same place.'''))
        self.setItem(row, 3, toc_cell)

    def get_row_linenum(self,row):
        if not isinstance(row,int): # Can pass either Row qt obj or int.
            row = row.row()
        return row

    def get_row_prev_toc(self,row):
        if not isinstance(row,int): # Can pass either Row qt obj or int.
            row = row.row()
        return self.item(row,3).data(Qt.UserRole).strip()

    def get_row_toc(self,row):
        if not isinstance(row,int): # Can pass either Row qt obj or int.
            row = row.row()
        return self.item(row,3).text().strip()

    def get_selected_rows(self):
        ## order rows by linenum, copy in case QT handed us something
        ## internal.
        rows = list(self.selectionModel().selectedRows())
        rows.sort(key=self.get_row_linenum)
        return rows

    def selected_all_have_toc(self):
        "Return false if any of the sections would not have a title when doing split all."
        for row in self.get_selected_rows():
            linenum = self.get_row_linenum(row)
            pre = self.get_row_prev_toc(row)
            changed = self.get_row_toc(row)
            if not changed or ( (pre == changed) and not pre ):
                return False
        return True

    def get_selected_tocs(self):
        linelists = []
        linenums = []

        for row in self.get_selected_rows():
            linenum = self.get_row_linenum(row)
            # changed tocs only.
            pre = self.get_row_prev_toc(row)
            changed = self.get_row_toc(row)
            toc = pre
            if pre != changed:
                toc = changed
            if toc and linenums:
                linelists.append(linenums)
                linenums = []
            linenums.append(linenum)
            # logger.debug("linenums:%s"%linenums)
            # logger.debug("linelists:%s"%linelists)

        if linenums:
            linelists.append(linenums)

        checkedalways,changedtocs = self.get_checkedalways_changedtocs()
        # logger.debug("linelists:%s"%linelists)
        return linelists, changedtocs, checkedalways

    def show_checkedalways(self,show=False):
        self.setColumnHidden(0,not show)

    def get_checkedalways_changedtocs(self):
        checkedalways = []
        changedtocs = {}
        for row in range(self.rowCount()):
            cb = self.item(row,0)
            if not self.isColumnHidden(0) and cb.checkState() == Qt.Checked:
                checkedalways.append(row)
            # changed tocs only.
            if self.get_row_prev_toc(row) != self.get_row_toc(row):
                changedtocs[row] = self.get_row_toc(row).split('|')
        # logger.debug(checkedalways)
        # logger.debug(changedtocs)

        return checkedalways, changedtocs

    def get_selected_linenums_tocs(self):
        linenums = []
        for row in self.get_selected_rows():
            linenum = self.get_row_linenum(row)
            linenums.append(linenum)
        checkedalways,changedtocs = self.get_checkedalways_changedtocs()

        return linenums, changedtocs, checkedalways

    def show_tooltip(self,modidx):
        "Show section sample from tooltip in an info for copying when double clicked."
        if modidx.column() == 1: # HREFs column only.
            ViewSample(_("Section Sample"),
                       self.item(modidx.row(),modidx.column()).toolTip().replace(SAMPLE_NOTE,''),
                       parent=self.parent()).exec_()

    def contextMenuEvent(self, event):
        if not self.isColumnHidden(0):
            menu = QMenu(self)
            checkAction = menu.addAction(_("Check Selected"))
            uncheckAction = menu.addAction(_("Uncheck Selected"))
            action = menu.exec_(self.mapToGlobal(event.pos()))
            for row in self.get_selected_rows():
                cb = self.item(self.get_row_linenum(row),0)
                if action == checkAction:
                    cb.setCheckState(Qt.Checked)
                if action == uncheckAction:
                    cb.setCheckState(Qt.Unchecked)


def LoopProgressDialog(gui,
                       split_list,
                       foreach_function,
                       finish_function,
                       init_label=_("Splitting Sections..."),
                       win_title=_("Splitting Sections..."),
                       status_prefix=_("Splitting Sections...")):
    ld = _LoopProgressDialog(gui,
                             split_list,
                             foreach_function,
                             init_label,
                             win_title,
                             status_prefix)

    # Mac OS X gets upset if the finish_function is called from inside
    # the real _LoopProgressDialog class.

    # reflect old behavior.
    if not ld.wasCanceled():
        finish_function(split_list)

class _LoopProgressDialog(QProgressDialog):
    '''
    ProgressDialog displayed while splitting each section.
    '''
    def __init__(self, gui,
                 split_list,
                 foreach_function,
                 init_label=_("Splitting Sections..."),
                 win_title=_("Splitting Sections..."),
                 status_prefix=_("Splitting Sections...")):
        QProgressDialog.__init__(self,
                                 init_label,
                                 _('Cancel'), 0, len(split_list), gui)
        self.setWindowTitle(win_title)
        self.setMinimumWidth(500)
        self.split_list = split_list
        self.foreach_function = foreach_function
        self.status_prefix = status_prefix
        self.i = 0
        self.start_time = datetime.now()

        ## self.do_loop does QTimer.singleShot on self.do_loop also.
        ## A weird way to do a loop, but that was the example I had.
        ## 100 instead of 0 on the first go due to Win10(and later
        ## qt6) not displaying dialog properly.
        QTimer.singleShot(100, self.do_loop)
        self.exec_()

    def updateStatus(self):
        remaining_time_string = ''
        if self.i > -1:
            time_spent = (datetime.now() - self.start_time).total_seconds()
            estimated_remaining = (time_spent/(self.i+1)) * len(self.split_list) - time_spent
            remaining_time_string = _(' - %s estimated until done') % ( time_duration_format(estimated_remaining))

        self.setLabelText('%s %d / %d%s' % (self.status_prefix, self.i+1, len(self.split_list), remaining_time_string))
        self.setValue(self.i+1)
        #print(self.labelText())

    def do_loop(self):

        if self.i == 0:
            self.setValue(0)

        split = self.split_list[self.i]
        self.foreach_function(split)

        self.updateStatus()
        self.i += 1

        if self.i >= len(self.split_list) or self.wasCanceled():
            return self.do_when_finished()
        else:
            QTimer.singleShot(0, self.do_loop)

    def do_when_finished(self):
        self.hide()

class ViewSample(SizePersistedDialog):

    def __init__(self, title, html, parent=None):
        SizePersistedDialog.__init__(self, parent, 'epubsplit:view sample')
        self.l = l = QVBoxLayout()
        self.setLayout(l)

        self.tb = QTextBrowser(self)
        self.tb.setHtml(html)
        l.addWidget(self.tb)

        self.bb = QDialogButtonBox(QDialogButtonBox.Ok)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        l.addWidget(self.bb)
        self.setModal(False)
        self.setWindowTitle(title)
        self.setWindowIcon(get_icon('format-justify-fill.png'))

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.show()

def time_duration_format(seconds):
    """
    Convert seconds into a string describing the duration in larger time units (seconds, minutes, hours, days)
    Only returns the two largest time divisions (eg, will drop seconds if there's hours remaining)

    :param seconds: number of seconds
    :return: string description of the duration
    """
    periods = [
        (_('%d day'),_('%d days'),       60*60*24),
        (_('%d hour'),_('%d hours'),     60*60),
        (_('%d minute'),_('%d minutes'), 60),
        (_('%d second'),_('%d seconds'), 1)
        ]

    strings = []
    for period_label, period_plural_label, period_seconds in periods:
        if seconds > period_seconds:
            period_value, seconds = divmod(seconds,period_seconds)
            if period_value == 1:
                strings.append( period_label % period_value)
            else:
                strings.append(period_plural_label % period_value)
            if len(strings) == 2:
                break

    if len(strings) == 0:
        return _('less than 1 second')
    else:
        return ', '.join(strings)

