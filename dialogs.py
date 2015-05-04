#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2015, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback
from functools import partial

import logging
logger = logging.getLogger(__name__)

from datetime import datetime

try:
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (QTableWidget, QVBoxLayout, QHBoxLayout, QProgressDialog, QTimer,
                          QDialogButtonBox, Qt, QAbstractItemView, QTableWidgetItem)
except ImportError as e:
    from PyQt4 import QtGui
    from PyQt4.Qt import (QTableWidget, QVBoxLayout, QHBoxLayout, QProgressDialog, QTimer,
                          QDialogButtonBox, Qt, QAbstractItemView, QTableWidgetItem)

try:
    from calibre.gui2 import QVariant
    del QVariant
except ImportError:
    is_qt4 = False
    convert_qvariant = lambda x: x
else:
    is_qt4 = True

    def convert_qvariant(x):
        vt = x.type()
        if vt == x.String:
            return unicode(x.toString())
        if vt == x.List:
            return [convert_qvariant(i) for i in x.toList()]
        return x.toPyObject()

from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.message_box import ViewLog
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

class SelectLinesDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, lines,
                 do_split_fn,
                 do_splits_fn,
                 save_size_name='epubsplit:update list dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui
        self.do_split_fn = do_split_fn
        self.do_splits_fn = do_splits_fn

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

        options_layout = QHBoxLayout()

        button_box = QDialogButtonBox(self)
        new_book = button_box.addButton(_("New Book"), button_box.ActionRole)
        new_book.setToolTip(_("Make <i>one</i> new book containing the sections selected above and then edit its Metadata."))
        new_book.clicked.connect(self.new_book)

        new_books = button_box.addButton(_("New Book per Section"), button_box.ActionRole)
        new_books.setToolTip(_("Make a new book for <i>each</i> of the sections selected above.  Title for each will be the Table of Contents, which you can edit here first."))
        new_books.clicked.connect(self.new_books)

        button_box.addButton(_("Done"), button_box.RejectRole)
        button_box.rejected.connect(self.reject)
        options_layout.addWidget(button_box)

        layout.addLayout(options_layout)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.lines_table.populate_table(lines)

    def new_book(self):
        self.do_split_fn(self.get_selected_linenums_tocs())

    def new_books(self):
        if not self.lines_table.selected_all_have_toc():
            error_dialog(self.gui,
                         _('Missing Title(s)'),
                         _("Books not split.\n\nSome selected sections don't have a Table of Contents text.  You must enter one before splitting sections to individual books.  Double click to edit the Table of Contents entry for a section."),
                         show_copy_button=False).exec_()
        else:
            self.do_splits_fn(self.get_selected_linenums_tocs())

    def get_selected_linenums_tocs(self):
        return self.lines_table.get_selected_linenums_tocs()

class LinesTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def populate_table(self, lines):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(lines))
        header_labels = [_('HREF'), _('Guide'), _('Table of Contents')] #, 'extra'
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
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 10)
        self.setMinimumColumnWidth(3, 100)
        self.setMinimumSize(300, 0)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, line):

        href = line['href']
        if line['anchor']:
            href = "%s#%s"%(href,line['anchor'])

        href_cell = ReadOnlyTableWidgetItem(href)
        href_cell.setToolTip(line['sample']+_("<p><b><i>Double click to copy from sample.</i></b></p>"))
        href_cell.setData(Qt.UserRole, line['num'])
        self.setItem(row, 0, href_cell)

        if 'guide' in line:
            guide = "(%s):%s"%line['guide']
        else:
            guide = ""
        guide_cell = ReadOnlyTableWidgetItem(guide)
        guide_cell.setToolTip(_("Indicates 'special' pages: copyright, titlepage, etc."))
        self.setItem(row, 1, guide_cell)

        toc_str = "|".join(line['toc'])
        toc_cell = QTableWidgetItem(toc_str)
        toc_cell.setData(Qt.UserRole, toc_str)
        toc_cell.setToolTip(_('''Click and copy hotkey to copy text.
Double-click to edit ToC entry.
Pipes(|) divide different ToC entries to the same place.'''))
        self.setItem(row, 2, toc_cell)

    def selected_all_have_toc(self):
        "Return false if any of the sections would not have a title when doing split all."
        for row in self.selectionModel().selectedRows():
            linenum = convert_qvariant(row.data(Qt.UserRole))
            pre = convert_qvariant(self.item(row.row(),2).data(Qt.UserRole)).strip()
            changed = self.item(row.row(),2).text().strip()
            if not changed or ( (pre == changed) and not pre ):
                return False
        return True

    def get_selected_linenums_tocs(self):
        # lines = []
        # for row in range(self.rowCount()):
        #     rnum = self.item(row, 0).data(Qt.UserRole).toPyObject()
        #     line = self.lines[rnum]
        #     lines.append(line)
        # return lines
        linenums = []
        changedtocs = {}

        for row in self.selectionModel().selectedRows():
            linenum = convert_qvariant(row.data(Qt.UserRole))
            linenums.append(linenum)
            # changed tocs only.
            if convert_qvariant(self.item(row.row(),2).data(Qt.UserRole)) != self.item(row.row(),2).text():
                changedtocs[linenum] = unicode(self.item(row.row(),2).text()).strip().split('|')

        linenums.sort()
        return linenums, changedtocs


    def show_tooltip(self,modidx):
        "Show section sample from tooltip in an info for copying when double clicked."
        if modidx.column() == 0: # first column only.
            ViewLog(_("Section Sample"),
                    # negate the <pre> ViewLog wraps with.
                    "</pre>%s<pre>"%self.item(modidx.row(),modidx.column()).toolTip(),
                    parent=self.parent()).exec_()

class LoopProgressDialog(QProgressDialog):
    '''
    ProgressDialog displayed while splitting each section.
    '''
    def __init__(self, gui,
                 split_list,
                 foreach_function,
                 finish_function,
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
        self.finish_function = finish_function
        self.status_prefix = status_prefix
        self.i = 0
        self.start_time = datetime.now()

        ## self.do_loop does QTimer.singleShot on self.do_loop also.
        ## A weird way to do a loop, but that was the example I had.
        QTimer.singleShot(0, self.do_loop)
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
        self.finish_function(self.split_list)

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

