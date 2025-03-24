import pcot.ui.tabs
from pcot.datum import Datum
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import XFormType, xformtype

CALIB_TARGETS = ["PCT", "Foo", "Bar"]

@xformtype
class XFormReflectance(XFormType):
    """
    Given an image which has source data and a set of labelled ROIs
    (regions of interest), generate gradient and intercept values
    to correct the image to reflectance values.

    The ROIs must correspond to calibration target patches in the image.
    The calibration target can be selected by the user.

    The image must know what camera and filters it came from, and the camera
    must have filter information including nominal reflectances for each
    patch on that target.
    """
    def __init__(self):
        super().__init__("reflectance", "calibration", "0.0.0")
        self.addInputConnector("img", Datum.IMG)
        self.addOutputConnector("mul", Datum.NUMBER)
        self.addOutputConnector("add", Datum.NUMBER)

        self.params = TaggedDictType(
            target=("The calibration target to use", str, CALIB_TARGETS[0],
                    CALIB_TARGETS)
        )

    def init(self, node):
        node.bandToPlot = 0     # no serialisation needed

    def createTab(self, xform, window):
        return TabReflectance(xform, window)

    def perform(self, node):
        # read the image
        img = node.getInput(0, Datum.IMG)
        # ...more here...



class TabReflectance(pcot.ui.tabs.Tab):
    def __init__(self, node, window):
        super().__init__(window, node, 'tabreflectance.ui')
        self.w.targetCombo.currentIndexChanged.connect(self.targetChanged)
        # populate the target combo box
        self.w.targetCombo.addItems(CALIB_TARGETS)
        self.w.bandCombo.currentIndexChanged.connect(self.bandChanged)
        # populating the band combo box with filters from the input image is done
        # in the nodeChanged method
        self.w.replot.clicked.connect(self.replot)
        self.nodeChanged()

    def targetChanged(self, i):
        self.mark()
        self.node.params.target = CALIB_TARGETS[i]
        self.changed()

    def bandChanged(self, i):
        self.mark()
        self.node.band = i
        self.changed()

    def onNodeChanged(self):
        self.markReplotReady()
        self.w.targetCombo.setCurrentIndex(CALIB_TARGETS.index(self.node.params.target))
        # populate the band combo box with the filters from the image
        self.w.bandCombo.clear()
        self.w.bandCombo.addItems(["dummy", "dummy2"])

    def markReplotReady(self):
        """make the replot button red"""
        self.w.replot.setStyleSheet("background-color:rgb(255,100,100)")

    def replot(self):
        ax = self.w.mpl.ax
        ax.cla()
        ax.set_xlabel("True reflectance (nm)")
        ax.set_ylabel("Measured reflectance (nm)")
        ax.plot([0, 1], [0, 1], '+-r')
        self.w.mpl.draw()
        self.w.replot.setStyleSheet("")
