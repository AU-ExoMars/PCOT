import logging

from pcot.datum import Datum
from pcot.parameters.taggedaggregates import Maybe, TaggedDictType
from pcot.ui.tabs import Tab
from pcot.utils import spectralparameters, SignalBlocker
from pcot.utils.spectralparameters import groups
from pcot.xform import XFormType, xformtype, XFormException

logger = logging.getLogger(__name__)



@xformtype
class XFormSpecParam(XFormType):
    def __init__(self):
        super().__init__("spectral parameter", "processing", "0.0.0")
        self.addInputConnector("", Datum.IMG)
        self.addOutputConnector("", Datum.IMG)

        self.params = TaggedDictType(
            group=("The name of the group the parameter is in", Maybe(str)),
            parameter=("The name of the parameter", Maybe(str)),
        )

    def init(self, node):
        # on initialisation, set the group to builtins and the parameter the first item.
        node.params.group = "builtins"
        node.params.parameter = list(groups[node.params.group].keys())[0]

        node.expr = ""      # expression text
        node.desc = ""      # description text

    def perform(self, node):
        img = node.getInput(0, Datum.IMG)

        try:
            if img is None:
                raise XFormException('DATA', 'no image data')

            group = node.params.group
            pname = node.params.parameter

            logger.info("Performing %s in group %s", pname, group)

            if group is None or pname is None:
                raise XFormException('DATA', 'no parameter group or parameter')

            # pull the data from the spectral parameter set if we can
            try:
                group = spectralparameters.groups[group]
            except KeyError:
                raise XFormException('DATA', f"no parameter group '{group}'")

            try:
                # get the parameter info and update the node's data
                parameter = group[pname]
                node.expr = parameter.expr
                node.desc = parameter.desc
                # run the parameter
                out = parameter.run(node.getInput(0))
                node.setOutput(0, out) # temporary no-op.

            except KeyError:
                raise XFormException('DATA', f"no parameter '{pname}' in group '{group}'")


        except Exception:
            # something went wrong, clean up.
            node.setOutput(0, None)
            node.expr = ""
            node.desc = ""
            raise

    def createTab(self, xform, window):
        return TabSpecParam(xform, window)



class TabSpecParam(Tab):
    def __init__(self, node, window):
        super().__init__(window,node, 'tabspecparam.ui')
        self.w.groupCombo.currentIndexChanged.connect(self.groupChanged)
        self.w.paramCombo.currentIndexChanged.connect(self.paramChanged)

        self.nodeChanged()

    def groupChanged(self):
        self.mark()
        self.node.params.group = self.w.groupCombo.currentText()
        self.changed()

    def paramChanged(self):
        self.mark()
        self.node.params.parameter = self.w.paramCombo.currentText()
        self.changed()

    def onNodeChanged(self):
        self.w.canvas.setNode(self.node)
        self.w.canvas.display(self.node.getOutput(0, Datum.IMG))

        # populate the group box and sync with current selection if possible
        with SignalBlocker(self.w.groupCombo, self.w.paramCombo):
            self.w.groupCombo.clear()
            self.w.groupCombo.addItems(groups.keys())
            self.w.groupCombo.setCurrentText(self.node.params.group)

            self.w.paramCombo.clear()
            group = groups[self.node.params.group]
            self.w.paramCombo.addItems(group.keys())
            self.w.paramCombo.setCurrentText(self.node.params.parameter)

        # set the expression
        self.w.exprEdit.setText(self.node.expr)


            


        # select the
