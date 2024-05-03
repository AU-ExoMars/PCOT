"""
This is an example XFormType (node) class. It is a class that you can copy and modify
to make your own nodes. It also has a tab with a single control - however, this tab creates
the controls programmatically rather than loading them from a .ui file created in Designer. See
other nodes for examples of how to do that, but you'll have to add the .ui file to the assets directory.
"""
import numpy as np
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QSlider, QDoubleSpinBox, QComboBox, QSizePolicy

import pcot.ui.tabs
from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.ui.canvas import Canvas
from pcot.utils import SignalBlocker
from pcot.xform import XFormType, xformtype, XForm


@xformtype
class XFormExample(XFormType):
    """
    This object is not a node, but the singleton that nodes of this type point to
    to control their behaviour.

    This docstring will form the help text for the node in the UI. Markdown is permitted
    and processed into HTML. Look at (say) XFormGradient for an example of how to write this.
    """

    def __init__(self):
        """
        Initialise the type singleton object. This doesn't create the *node*, but the single object that
        all nodes of this type will point to. This constructor runs at startup automatically (actually as part
        of importing PCOT).
        """

        # Call the superclass constructor with the name of the node type, the group it belongs to,
        # and the version number of the node type.
        # Because group is "hidden", we won't see it in the palette - it's just an example, not for actual use.

        # There are a couple of other parameters you can set here:
        # hasEnable=True - this will add a checkbox to the node's properties panel that allows the user to
        #                  disable the node temporarily. This is useful for nodes that are a bit slow.
        # startEnabled=False - this will start the node disabled. This is useful for nodes that are very slow.

        super().__init__("example", "hidden", "0.0.0",
                         #  hasEnable=True,
                         #  startEnabled=False
                         )

        # add input and output connectors. The first parameter is the name of the connector,
        # the second is the type of data that can be connected to it.
        # Connectors don't really need a name - they're displayed above the connector
        # in the UI if present.

        self.addInputConnector("", Datum.IMG)   # node input, an ImageCube datum
        self.addOutputConnector("", Datum.IMG)  # node output, an ImageCube datum

    def init(self, node: XForm):
        """
        This method is called to actually initialise a node (an XForm object).
        It typically does this by filling in some fields of the node object.
        """

        # this is the node's output, initialised to the null datum.
        node.out = Datum.null

        # this is some value that the node has as a parameter, controlling its
        # behaviour. We'll modify this value using the UI in the tab. In this case
        # it's a float.
        node.parameter = 0.0
        # for good measure here's another parameter, this time a string (we'll have
        # a combo box for these).
        node.parameter2 = "default"

        # this is a tuple of fields in the node that can be serialised and deserialised. This is used to save the
        # node's state to a file and to the undo stack. The fields must be JSON-serialisable types. If they are not,
        # you'll have to do something more clever overriding the serialise() and deserialise() methods.
        #
        # Each field is a tuple in the form ('name', defaultvalue). The default value is a recent addition to PCOT,
        # and is useful when new parameters are added to a node and they aren't found in files loaded from older
        # versions of the software. If the field is not found in the file, the default value is used.
        #
        # Remember that if you only have one parameter this still needs to be a tuple, so do "self.autoserialise = (
        # 'myparam',)
        self.autoserialise = (('parameter', 0.0),
                              ('parameter2', 'default'))

    def perform(self, node):
        """
        This runs automatically on a node whenever a node's input is changed,
        typically by nodes upstream of this one. It's where the node does its
        work.
        """

        img: ImageCube = node.getInput(0, Datum.IMG)  # get the input image
        if img is not None:
            # do something to the image. In this case, we're just going to
            # create a new image which is 32x32, has the same number of bands,
            # and is filled with the values of the top-left pixel!
            nom = img.img   # nominal pixel values (h,w,depth)
            # (we don't bother reading the uncertainty and DQ, we're not using them)

            # take the top left pixel's nominal value
            pix = nom[0][0]

            # multiply it by the node's parameter
            pix = pix * node.parameter

            # and make a new (h,w,depth) array filled with it
            newdata = np.full((32, 32, img.channels), pix)

            # now create a new ImageCube with the new data, and the same RGB canvas mapping as the input.
            # we're providing no uncertainty and no DQ value - the uncertainty will be zero and the DQ
            # will be NOUNCERTAINTY. We do provide sources for each band - they will be the same as those
            # for the input image. It would be better to do some more intelligent processing with the
            # uncertainty and DQ bits, particularly if any DQ bits in the data we are using are in the
            # dq.BAD set!!.
            newimg = ImageCube(newdata, rgbMapping=img.mapping, sources=img.sources.copy())

        else:
            # if there's no input, just set the output image to None.
            newimg = None

        # wrap the output image in a Datum
        node.out = Datum(Datum.IMG, newimg)
        # and set the node's output to be that datum.
        node.setOutput(0, node.out)

    def createTab(self, node, window):
        """
        Create a tab for this node. This is a tab that will be displayed in the
        node's properties panel in the UI. It takes the node, which will be stored
        in the tab, and the window, which is the main window of the application.
        It just creates and returns a tab - the code for which can be found below.
        """
        return TabExample(node, window)


class TabExample(pcot.ui.tabs.Tab):
    """This is a tab - a QWidget that will be displayed in the properties panel of the UI
    for this particular node"""

    def __init__(self, node, window):
        """Initialise the widget for this node"""

        # call the superclass constructor with the window and the node, but not a UI filename
        # because we're going to create the UI programatically.
        super().__init__(window, node, None)

        # now we create a UI - look at documentation and tutorials for PySide2, PySide6 (the new
        # version) or PyQt5 for how to create UIs programatically. This is a very simple example.
        # Here's one tutorial: https://www.pythonguis.com/pyside2-tutorial/

        # The constructor will already have created a QWidget for us
        # to add things to, called self.w. We'll create a grid layout
        # and set it on that widget.

        layout = QGridLayout()
        self.w.setLayout(layout)

        # create a label and a spinbox for the first parameter. You'll notice in other files that the widgets
        # are called "self.w.something". That's because they're loaded from a .ui file, which creates them as
        # attributes of the main tab widget. Here we're creating them ourselves, so we don't need to do that.

        layout.addWidget(QLabel("Parameter 1"), 0, 0)
        self.spin = QDoubleSpinBox(self.w)
        self.spin.setRange(-10, 10)
        self.spin.setSingleStep(0.1)
        layout.addWidget(self.spin, 0, 1)

        # create a label and a combo box for the second parameter

        layout.addWidget(QLabel("Parameter 2"), 1, 0)
        self.combo = QComboBox(self.w)
        self.combo.addItems(["default", "option 1", "option 2", "option 3"])
        layout.addWidget(self.combo, 1, 1)

        # create a canvas - this is the main display object for images
        # in the UI.

        self.canvas = Canvas(self.w)

        # we put the canvas in row 0, column 2. We set it to be 4 rows deep and 1 column wide. Some
        # of this stuff is a black art, but the basic idea is that we want the canvas to be taller than
        # the other widgets, so we give it more rows. We also set the column to stretch, so that it will
        # take up more space than the other columns (5 times as much, ideally).

        layout.addWidget(self.canvas, 0, 2, 4, 1)
        layout.setColumnStretch(2, 5)

        # now we have the widgets, we need to link them to data. We can handle changes to the data
        # in onNodeChanged, which will reset the widgets to the values in the node. Here we will
        # connect the widget signals to slots in the tab object, which will then update the node.

        # yes, these look weird - "valueChanged" is a signal, and connect is a method of the signal.
        self.spin.valueChanged.connect(self.onSpinChanged)
        self.combo.currentIndexChanged.connect(self.onComboChanged)

        # there is no connect for the canvas because it can't change node state

        # finally, tell the tab to update itself from the node.

        self.nodeChanged()  # (not to be confused with onNodeChanged!)

    def onSpinChanged(self, val):
        """This slot method is called when the spinbox changes its value. We update the node and tell it
        that it has changed, which causes the node (and all its children) to run perform()."""

        self.node.parameter = val
        self.changed()

    def onComboChanged(self, newIdx):
        """Here the combo box value has changed - we're not using it, but we'll change it in the node anyway.
        Although we're using the index, we're going to set the text."""

        self.node.parameter2 = self.combo.itemText(newIdx)
        self.changed()

    def onNodeChanged(self):
        """This is called when a node changes, and is where we update the tab from the node."""

        # easy part - just set the spinbox and combo box values to the node's values.

        self.spin.setValue(self.node.parameter)

        # this avoids an infinite loop where changing the combo changes the node,
        # which runs this method to change the combo, which changes the node...
        # It's not actually necessary here, but this is how you fix that problem if
        # you come across it.

        with SignalBlocker(self.combo):
            self.combo.setCurrentText(self.node.parameter2)

        # slightly harder part - update the canvas with the image in the node.
        # some setup stuff first

        self.canvas.setMapping(self.node.mapping)
        self.canvas.setGraph(self.node.graph)
        self.canvas.setPersister(self.node)
        # then display the image
        self.canvas.display(self.node.out.get(Datum.IMG))
