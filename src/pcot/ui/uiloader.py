# Lets you load a UI file into a class, like PyQt5 does.
# original source  https://robonobodojo.wordpress.com/2017/10/03/loading-a-pyside-ui-via-a-class/

from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QMetaObject, QByteArray, QBuffer

import pcot.config


class UiLoader(QUiLoader):
    """Private class"""
    def __init__(self, base_instance):
        QUiLoader.__init__(self, base_instance)
        self.base_instance = base_instance

    def createWidget(self, class_name, parent=None, name=''):
        if parent is None and self.base_instance:
            return self.base_instance
        else:
            # create a new widget for child widgets
            widget = QUiLoader.createWidget(self, class_name, parent, name)
            if self.base_instance:
                setattr(self.base_instance, name, widget)
            return widget


def loadUi(ui_file_name, base_instance=None):
    """Use this the same way as uic.loadUi, but takes a filename inside the resources."""
    strdata = pcot.config.getAssetAsString(ui_file_name)
    data = QByteArray(strdata.encode('utf-8'))
    buf = QBuffer(data)    # this will have a QIODevice interface so UiLoader can use it

    loader = UiLoader(base_instance)
    widget = loader.load(buf)
    QMetaObject.connectSlotsByName(widget)
    return widget
