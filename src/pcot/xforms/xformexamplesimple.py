"""
This is an example XFormType (node) class. This one uses the TabAggregate to edit the parameters, which
is an easy way of editing a node with simple TaggedDict parameters.
"""

from pcot.datum import Datum
from pcot.imagecube import ImageCube
from pcot.parameters.taggedaggregates import TaggedDictType
from pcot.xform import XFormType, xformtype, XForm, XFormException
from pcot.xforms.tabgeneric import TabGeneric


@xformtype
class XFormExampleSimpleParameters(XFormType):
    """
    This object is not a node, but the singleton to which nodes of this type point to
    determine their behaviour.

    This docstring will form the help text for the node in the UI. Markdown is permitted
    and processed into HTML. Look at (say) XFormColourMap for an example of how to write this.
    """

    def __init__(self):
        """
        Initialise the type singleton object. This doesn't create the *node*, but the single object that
        all nodes of this type will point to. This constructor runs at startup automatically (actually as part
        of importing PCOT).

        This example adds and multiplies, or multiplies and then adds, its input by
        a pair of constants.
        """

        # Call the superclass constructor with the name of the node type, the group it belongs to,
        # and the version number of the node type.
        # Because group is "hidden", we won't see it in the palette - it's just an example, not for actual use.

        # There are a couple of other parameters you can set here:
        # hasEnable=True - this will add a checkbox to the node's properties panel that allows the user to
        #                  disable the node temporarily. This is useful for nodes that are a bit slow.
        # startEnabled=False - this will start the node disabled. This is useful for nodes that are very slow.
        #                  It has no effect if hasEnable is false.

        super().__init__("simple", "testing", "0.0.0",
                         #  hasEnable=True,
                         #  startEnabled=False
                         )

        # set up parameters. This is a "tagged dictionary" - see the taggedaggregates.py file for more information,
        # but essentially it's a dict with description, type and default value for every item. This object
        # is the "type singleton" which defines the parameters for nodes of this type; calling create() on
        # it will create the actual TaggedDict instance. This is done automatically when we create a new node.
        #
        # We also have TaggedList, and both TaggedList and TaggedDict can contain other TaggedLists and TaggedDict.
        # Check out the tests in test_taggedaggs.py, some of those are quite complex.

        self.params = TaggedDictType(
            # this is a float parameter called "mul"" with a default value of 0.0. The UI will automatically
            # make an editor for it, as it will for all the parameters.
            mul=("multiply", float, 0.0),
            add=("add", float, 0.0),
            # this is a string parameter called "order" with a default value. It can have
            # several different specific values. If we didn't provide these it could have any value, and the
            # tab would have a text editor rather than a dropdown.
            order=("order of ops", str, "mul,add", ["mul,add","add,mul"])
        )

        # add input and output connectors. The first parameter is the name of the connector,
        # the second is the type of data that can be connected to it.
        # Connectors don't really need a name - they're displayed above the connector
        # in the UI if present.

        self.addInputConnector("", Datum.IMG)   # node input, an ImageCube datum
        self.addOutputConnector("", Datum.IMG)  # node output, an ImageCube datum

    def init(self, node: XForm):
        """
        This method is called to actually initialise a node (an XForm object). It typically does this by
        filling in some fields of the node object.
        Here, though, there's nothing to do because node.params will already have been created from self.params
        """
        pass

    def perform(self, node):
        """
        This runs automatically on a node whenever a node's input is changed,
        typically by nodes upstream of this one. It's where the node does its
        work.
        """
        params = node.params   # get a handy reference to the parameters TaggedDict

        # get the input as a Datum
        img: Datum = node.getInput(0)
        if img.isImage():   # if it's an image (it will not be if the input is not connected)...
            # here we do the actual operations, working on Datum objects because it's the easiest way
            # of propagating uncertainty and ROIs, and making sure the operations only occur on parts
            # of the image covered by any ROIs.
            if node.params.order == "mul,add":
                # Datum knows how to add Datum and numbers, both ways round. Subtraction and division
                # will be handled OK too. See GUPPY!
                img  = params.mul * img + params.add
            elif node.params.order == "add,mul":
                img = (img + params.add) * params.mul
            else:
                # this is the kind of exception to raise when things go wrong in a node. The four-letter code
                # is shown in the node's graph box.
                raise XFormException('DATA', "Bad 'order' parameter")
        else:
            # if there's no input, just set the output image to None.
            img = Datum.null

        # and set the node's output to be that datum.
        node.setOutput(0, img)

    def createTab(self, node, window):
        """
        Create a tab for this node. This is a tab that will be displayed in the
        node's properties panel in the UI. It takes the node, which will be stored
        in the tab, and the window, which is the main window of the application.
        It just creates and returns a tab - in this case it's a "standard" tab for
        editing a node with simple parameters.

        If we want to display the data type and source info, add "source_section=True"
        """
        return TabGeneric(node, window)
