import PyQt5 # just for the type hint
import traceback,inspect,hashlib,re,copy
from collections import deque
from pancamimage import Image
import pyperclip,json,uuid
from typing import List, Set, Dict, Tuple, Optional, Any

import ui,conntypes

# ugly forward declarations so the type hints work

class XForm:
    pass
class XFormGraph:
    pass



# dictionary of name -> transformation type
allTypes = dict()

# Superclass for a transformation type. There is a singleton subclassed
# from this for each type. 

# This is a singleton decorator which, unusually, is not lazy, because we
# need the xforms to be registered at initialisation. Thus the class creation
# forces an instance to be created. We also use it to grab the source code
# and generate an MD5 checksum, so we are *sure* versions match.
class xformtype:
    def __init__(self,cls,*args,**kwargs):
        self._cls=cls
        # get the module so we can add an MD5 checksum of its source code to the type
        # data, for version matching info
        mod = inspect.getmodule(cls)
        src = inspect.getsource(mod).encode('utf-8') # get the source
        self._instance = self._cls(*args,**kwargs) # make the instance
        self._instance._md5 = hashlib.md5(src).hexdigest() # add the checksum
        if self._instance.__doc__ == None:
            print("WARNING: no documentation for xform type '{}'".format(self._instance.name))
        
    def __call__(self):
        return self._instance
        
# This exception is thrown if a loaded node's MD5 checksum (from the node source when the 
# file was saved) disagrees with the node's current MD5: this means that the node's source
# code has changed, and the node is not guaranteed to work as it did when saved.

class BadVersionException(Exception):
    def __init__(n):
        self.message = "Node {} was saved with a different version of type {}".format(n.name,n.type.name)

class XFormType():

    name: str                   # name of the xform (node) type
    group: str                  # the palette group it belongs to
    ver: str                    # the version number
    hasEnable: bool             # does it have an enable button?
    instances: List[XForm]      # all instances in all graphs

    # name is the name which appears in the graph view
    # connection type name is 'any', 'imgrgb' etc.: the internal type name
    # desc is used in the help window

    inputConnectors: List[Tuple[str,str,str]] # the inputs (name,connection type name,description)
    outputConnectors: List[Tuple[str,str,str]] # the outputs (name,connection type name,description)
    autoserialise: Tuple[str]   # tuple of autoserialisable attributes in each node of this type
    _md5: str                   # MD5 hash of source code (generated automatically)
    
    def __init__(self,name,group,ver):
        self.group = group
        self.name = name
        self.ver = ver
        self.instances = [] 
        # add to the global dictionary
        if name in allTypes:
            raise Exception("xform type name already in use: "+name)
        # register the type
        allTypes[name]=self
        # does this node have an "enabled" button? Change in subclass if reqd.
        self.hasEnable=False
        # this contains tuples of (name,typename). Images have typenames which
        # start with "img"
        self.inputConnectors = []
        # this has the same format, but here the output type
        # is the default type for that connection - when an xform is wired up
        # it may override this type. This means that when we wire up an
        # xform, a complicated little dance has to be done to determine the
        # actual output type and then disconnect any connections which are
        # no longer compatible.
        self.outputConnectors = []
        # The type may create additional attributes in the xform, which
        # can be listed here for automatic serialisation and deserialisation;
        # they must be simple Python data. This happens in addition to, and
        # before, the serialise() and deserialise() methods.
        self.autoserialise=() # tuple or list of attribute names
        
    def remove(self,node):
        self.instances.remove(node)
        
    def md5(self):
        # returns a checksum of the sourcecode for the module defining the type,
        # used to check versions
        return self._md5
        
    def doAutoserialise(self,node):
        return {name:node.__dict__[name] for name in self.autoserialise}
        
    def doAutodeserialise(self,node,ent):
        for name in self.autoserialise:
            # ignore key errors, for when we add data during development
            try:
                node.__dict__[name] = ent[name]
            except KeyError:
                pass

    def addInputConnector(self,name,typename,desc=""):
        self.inputConnectors.append( (name,typename,desc) )
    def addOutputConnector(self,name,typename,desc=""):
        self.outputConnectors.append( (name,typename,desc) )

    # rename a node. Subclassed in connector nodes because they are messy.
    # even though we're only changing the display name
    def rename(self,node,name):
        node.displayName = name

    # rename the type, used to rename a macro. Let's hope that
    # we don't reference types by name anywhere else.
    def renameType(self,newname):
        del allTypes[self.name]
        self.name = newname
        allTypes[newname]=self
        ui.mainwindow.MainUI.rebuildPalettes()
        ui.mainwindow.MainUI.rebuildAll()
        
        

        
    def all():
        return allTypes
        
        
    # DOWN HERE ARE METHODS YOU MAY NEED TO OVERRIDE WHEN WRITING NODE TYPES
        
    # this is overriden if a node might change its output type depending on its
    # input types. It's called when an input connection is made or broken, and is followed
    # by a check on existing connections to those outputs which may then be broken if 
    # they are no longer compatible. It's called by XFormGraph.inputChanged(node).
    #
    # DO NOT modify the output type directly, use changeOutputType in the node. This
    # will tell the on-screen connector rect to update its brush. See xforms/xformcurve for
    # an example.
    def generateOutputTypes(self,node):
        pass
        
    # perform the actual action of the transformation, will generate outputs
    # in that object.
    def perform(self,xform):
        pass
        
    # initialise any data fields (often to None)
    def init(self,xform):
        pass
        
    # after control data has changed (either in a tab or by loading a file) it
    # may be necessary to recalculate internal data (e.g. lookup tables). This
    # can be overridden to do that: it happens when a node is deserialised,
    # and should be called in the tab's onNodeChanged() AFTER the controls are set
    # and BEFORE changing any status displays (see xformcurve for an example).
    def recalculate(self,xform):
        pass
        
    # return a dict of all values belonging to the node which should be saved.
    # This happens in addition to autoserialisation/deserialisation
    def serialise(self,xform):
        pass
    
    # given a dictionary, set the values in the node from the dictionary    
    # This happens in addition to autoserialisation/deserialisation
    def deserialise(self,xform,d):
        pass
        
    # create a tab connected to this xform, parented to a main window.
    # Might return none, if this xform doesn't have a meaningful UI.
    def createTab(self,xform,window):
        return None


# serialise a connection (xform,i) into (xformName,i).
# Will only serialise connections into the set passed in. If None is passed
# in all connections are OK.
def serialiseConn(c,connSet):
    if c:
        x,i = c
        if (connSet is None) or (x in connSet):
            return (x.name,i)
    return None

# an actual instance of a transformation
class XForm:
    import graphscene # deferred import avoiding circular import
    # type hints for attributes, here mainly as documentation
    type: XFormType  # the type of the node (this does the actual work)
    savedver: str    # the version number this node's type was saved with
    # list of tuples/none, each is the node we connect to and the output 
    # to which we are connected on that node
    inputs: List[Tuple[XForm,int]] 
    # dictionary of nodes we output to and how many connections we have
    children: Dict[XForm,int]
    # the actual output data from this node
    outputs: List[Any]
    # the "overriding" output type (since an "img" output (say) may become
    # an "imgrgb") when the perform happens
    outputTypes: List[str]
    # similarly, overriding input types are required on macros
    inputTypes: List[str]
    comment: str    # a helpful comment
    # the unique name of the node, which is internal only. The name the user sees is displayName.
    name: str 
    # the name as displayed in the graph (and in the tab)
    displayName: str
    enabled: bool   # should this node perform?
    hasRun: bool    # has this node run already in this graph.perform cycle?
    graph: XFormGraph # the graph to which I belong

    xy: Tuple[int,int] # the screen coordinates
    w: int
    h: int
    tabs: List[ui.tabs.Tab] # a list of open tabs
    current: bool   # is this the currently selected node?
    rect: [graphscene.GMainRect] # the main rectangle for the node in the scene
    inrects: List[graphscene.GConnectRect] # input connector rectangles
    outrects: List[graphscene.GConnectRect] # output connector rectangles
    helpwin:  PyQt5.QtWidgets.QMainWindow # an open help window, or None
    
    def __init__(self,type,dispname):
        self.type = type
        self.savedver = type.ver
        # we keep a dict of those nodes which get inputs from us, and how many. We can't
        # keep the actual output connections easily, because they are one->many.
        self.children = {}
        self.comment = "" # nodes can have comments
        # set the unique ID
        self.name = uuid.uuid4().hex
        # and the display name
        self.displayName = dispname
        # set up things which are dependent on the number of connectors,
        # which can change in macros. Initialise the inputs, though.
        self.inputs=[None]*len(type.inputConnectors)
        self.connCountChanged()
        
        # UI-DEPENDENT DATA DOWN HERE
        self.xy = (0,0) # this SHOULD be serialised
        
        # this stuff shouldn't be serialized
        # on-screen geometry, which should be set before we try to draw it
        self.w = None # unset, will be set on draw
        self.h = None
        self.tabs = [] # no tabs open
        self.current = False
        self.rect = None # the main GMainRect rectangle
        self.helpwin = None # no help window
        self.enabled = True # a lot of nodes won't use; see XFormType.
        self.hasRun = False # used to mark a node as already having performed its stuff
        type.instances.append(self)
        
    def dumpInputs(self,t):
        print('--------',t)
        for i in range(0,len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                tp = self.inputTypes[i]
                print("{}: {}/{}/{}".format(i,inp[0],inp[1],tp))
        
    def connCountChanged(self):
        # called when the connector count changes to set up the necessary
        # lists.
        # create unconnected connections. Connections are either None
        # or (Xform,index) tuples - the xform is the object to which we are
        # connected, the index is the index of the output connector on that xform for inputs,
        # or the input connector for outputs. This has to respect any existing connections,
        # otherwise editing becomes really painful.
        n = len(self.type.inputConnectors)
        if n>len(self.inputs):
            # there are more input connectors than inputs, add more to list
            self.inputs+=[None]*(n-len(self.inputs))
        elif n<len(self.inputs):
            # there are fewer, truncate the inputs
            self.inputs=self.inputs[:n]
        # otherwise just leave it.

        # there is also a data output generated for each output by "perform", initially
        # these are None
        self.outputs = [None for x in self.type.outputConnectors]
        # these are the overriding output types; none if we use the default
        # given by the type object (see the comment on outputConnectors
        # in XFormType)
        self.outputTypes = [None for x in self.type.outputConnectors]
        self.inputTypes = [None for x in self.type.inputConnectors]
        self.inrects = [None for x in self.inputs] # input connector GConnectRects
        self.outrects = [None for x in self.outputs] # output connector GConnectRects
        
    def onRemove(self):
        # called when a node is deleted
        self.type.remove(self)
        
    def setEnabled(self,b):
        for x in self.tabs:
            x.setNodeEnabled(b)
        self.enabled=b
        self.graph.scene.selChanged()
        self.graph.perform(self)
        
    def serialise(self,selection=None):
        # build a serialisable python dict of this node's values, including
        # only connections to/from the nodes in the selection (which may
        # be None if you want to serialize the whole set)
        d = {}
        d['xy'] = self.xy
        d['type'] = self.type.name
        d['displayName'] = self.displayName
        d['ins'] = [serialiseConn(c,selection) for c in self.inputs]
        d['comment'] = self.comment
        d['outputTypes'] = self.outputTypes
        d['inputTypes'] = self.inputTypes
        d['md5'] = self.type.md5()
        d['ver'] = self.type.ver # type.ver is version of type
        if self.type.hasEnable: # only save 'enabled' if the node uses it
            d['enabled']=self.enabled
            
        # add autoserialised data
        d.update(self.type.doAutoserialise(self))
        # and run the additional serialisation method
        d2 = self.type.serialise(self)
        if d2 is not None:
            d.update(d2)
        return d
    
    def deserialise(self,d): 
        # deserialise a node from a python dict. Some entries already dealt with.
        self.xy = d['xy']
        self.comment = d['comment']
        self.outputTypes = d['outputTypes']
        self.inputTypes = d['inputTypes']
        self.savedver = d['ver'] # ver is version node was saved with
        self.savedmd5 = d['md5'] # and stash the MD5 we were saved with
        self.displayName = d['displayName']

        # some nodes don't have this, in which case we just set it
        # to true.
        if 'enabled' in d:
            self.enabled = d['enabled']
        else:
            self.enabled = True
            
        # autoserialised data
        self.type.doAutodeserialise(self,d)
        # run the additional deserialisation method
        self.type.deserialise(self,d)
        
    def getOutputType(self,i):
        if i>=0 and i<len(self.outputs):
            if self.outputTypes[i] is None:
                return self.type.outputConnectors[i][1]
            else:
                return self.outputTypes[i]

    def getInputType(self,i):
        if i>=0 and i<len(self.inputs):
            if self.inputTypes[i] is None:
                return self.type.inputConnectors[i][1]
            else:
                return self.inputTypes[i]
                
    # is an output connected? This is a bit messy.
    def isOutputConnected(self,i):
        for outputnode in self.children:
            for inp in outputnode.inputs:
                if inp is not None:
                    inpnode,o = inp
                    if inpnode==self and o==i:
                        return True
        return False
        
    # this should be used to change an output type is generateOutputTypes
    def changeOutputType(self,index,type):
        self.outputTypes[index]=type
        if self.outrects[index] is not None:
#            print("MATCHING: {} becomes {}".format(index,type))
            self.outrects[index].typeChanged()
        
    # this can be used in XFormType's generateOutputTypes if the polymorphism
    # is simply that some outputs should match the types of some inputs. The
    # input is a list of (out,in) tuples. Typical usage for a node with a single
    # input and output is matchOutputsToInputs([(0,0)])
    def matchOutputsToInputs(self,pairs):
        # reset all types - doing it this way in case we add extra outputs!
        self.outputTypes[:len(self.type.outputConnectors)] = [None for x in self.type.outputConnectors]
        for o,i in pairs:
            if self.inputs[i] is not None:
                parent,pout = self.inputs[i]
                # the output type should be the same as the actual input (which is the
                # type of the output connected to that input)
                self.changeOutputType(o,parent.getOutputType(pout))
                if self.outrects[o] is not None:
                    self.outrects[o].typeChanged()

    def debugName(self):
        return "{}/{}/{}".format(self.type.name,self.name,self.displayName)
        
    def dump(self):
        print("---DUMP of {}, geom {},{},{}x{}".format(self.debugName(),
            self.xy[0],self.xy[1],self.w,self.h))
        print("  INPUTS:")
        for i in range(0,len(self.inputs)):
            c = self.inputs[i]
            if c:
                other,j = c
                print("    input {} <- {} {}".format(i,other.debugName(),j))
        print("   CHILDREN:")
        for k,v in self.children.items():
            print("    {} ({} connections)".format(k.name,v))
        s="CONNECTED OUTPUTS: "
        for i in range(0,len(self.outputs)):
            if self.isOutputConnected(i):
                s+=str(i)+" "
        print(s)
            
    # cycle detector - is "other" one of my children? We do a breadth-first
    # search with a queue.
    def cycle(self,other):
        queue=deque()
        queue.append(self)
        while len(queue)>0:
            p = queue.popleft()
            if p is other:
                return True
            for q in p.children:
                queue.append(q)
        return False

    # connect an input to an output on another xform. Note that this doesn't
    # check compatibility; that's done in the UI.
    def connect(self,input,other,output,autoPerform=True):
        if input>=0 and input<len(self.inputs) and self is not other:
            if output>=0 and output<len(other.type.outputConnectors):
                if not self.cycle(other): # this is a double check, the UI checks too.
                    self.inputs[input] = (other,output)
                    other.increaseChildCount(self)
                    if autoPerform:
                        other.graph.perform(other) # perform the input node; the output should perform
        
        
    # disconnect an input 
    def disconnect(self,input):
        if input>=0 and input<len(self.inputs):
            if self.inputs[input] is not None:
                n,i = self.inputs[input]
                n.decreaseChildCount(self)
                self.inputs[input]=None
                self.graph.perform(self) # run perform safely
            
    # disconnect all inputs and outputs prior to removal
    def disconnectAll(self):
        for i in range(0,len(self.inputs)):
            self.disconnect(i)
        for n,v in self.children.items():
            # remove all inputs which reference this node
            for i in range(0,len(n.inputs)):
                if n.inputs[i] is not None:
                    if n.inputs[i][0]==self:
                        # do this directly, rather than with disconnect() both
                        # to avoid a concurrent modification and also because
                        # the child counts are irrelevant and don't need updating
                        n.inputs[i]=None

    # change an output. This should be called by the type's perform method.
    def setOutput(self,i,data):
        self.outputs[i]=data
            
    def increaseChildCount(self,n):
        if n in self.children:
            self.children[n]+=1
        else:
            self.children[n]=1

    def decreaseChildCount(self,n):
        if n in self.children:
            self.children[n]-=1
            if self.children[n]==0:
                del self.children[n]
        else:
            raise Exception("child count <0 in node {}, child {}".format(self.debugName(),n.debugName()))
            
    def canRun(self):
        for inp in self.inputs:
            if inp is not None:
                out,index=inp
                if out.outputs[index] is None:
                    return False
        return True                    

    # perform the transformation; delegated to the type object. Also tells
    # any tab open on a node that its node has changed.
    def perform(self):
        # used to stop perform being called out of context; it should
        # only be called inside the graph's perform.
        if not self.graph.performingGraph:
            raise Exception("Do not call perform directly on a node!")
        ui.msg("Performing {}".format(self.debugName()))
        try:
            # must clear this with prePerform on the graph, or nodes will
            # only run once!
            if self.hasRun:
                print("----Skipping {}, run already this action".format(self.debugName()))
            elif not self.canRun():
                print("----Skipping {}, it can't run (unset inputs)".format(self.debugName()))
            else:
                print("--------------------------------------Performing {}".format(self.debugName()))
                # first clear all outputs
                self.outputs = [None for x in self.type.outputConnectors]
                # now run the node.
                self.type.perform(self)
                self.hasRun = True
                # tell the tab that this node has changed
                for x in self.tabs:
                    x.onNodeChanged()
                # run each child
                for n in self.children:
                    n.perform()
        except Exception as e:
            traceback.print_exc()
            ui.logXFormException(self,e)
        
    # get the value of an input
    def getInput(self,i):
        if self.inputs[i] is None:
            return None
        else:
            n,i = self.inputs[i]
            return n.outputs[i]
            
    # ensure connections are valid and break them if not
    def ensureConnectionsValid(self):
        for i in range(0,len(self.inputs)):
            inp = self.inputs[i]
            if inp is not None:
                n,idx = inp
                outtype = n.getOutputType(idx)
                intype = self.getInputType(i)
                if not conntypes.isCompatibleConnection(outtype,intype):
                    self.disconnect(i)

    def rename(self,name):
        # defer to type, because connector nodes have to rebuild all views.
        self.type.rename(self,name)
            
# a graph of transformation nodes
class XFormGraph:
    import graphscene # deferred import avoiding circular import
    nodes: List[XForm]      # all my nodes
    scene: graphscene.XFormGraphScene # my graphical representation
    isMacro: bool # true if this is a macro prototype, will be false for instances
    # true when I'm recursively performing my nodes. Avoids parallel
    # attempts to run a graph in different threads.
    performingGraph: bool

    def __init__(self,isMacro):
        # all the nodes
        self.nodes = []
        self.performingGraph = False
        self.scene = None # the graph's scene is created by autoLayout
        self.isMacro = isMacro

    def constructScene(self,doAutoLayout):
        import graphscene # deferred import avoiding circular import
        self.scene = graphscene.XFormGraphScene(self,doAutoLayout)
        
    
    # create a new node, passing in a type name.
    def create(self,typename):
        if typename in allTypes:
            tp = allTypes[typename]
            # display name is just the type name to start with.
            xform = XForm(tp,tp.name)
            self.nodes.append(xform)
            xform.graph = self
            tp.init(xform)
        else:
            raise Exception("Transformation type not found: "+typename)
        return xform
    
    # copy selected items to the clipboard. This copies a serialized
    # version, like that used for load/save.
    def copy(self,selection):
        # turn into JSON string
        s = json.dumps(self.serialise(selection))
        # copy to clipboard
        pyperclip.copy(s)
        
    # paste the clipboard. This involves deserialising.
    # Returns a list of new nodes.
    def paste(self):
        # get string from clipboard
        s = pyperclip.paste()
        if len(s)>0:
            try:
                d = json.loads(s) # convert to dict
            except json.decoder.JSONDecodeError:
                raise Exception("Clipboard does not contain valid data")
            return self.deserialise(d,False)
        else:
            return []
        
    # remove a note from the graph, and close any tab/window
    def remove(self,node):
        node.disconnectAll()
        for x in node.tabs:
            x.nodeDeleted()
        self.nodes.remove(node)
        node.onRemove()
        
    def dump(self):
        for n in self.nodes:
            n.dump()

    # we are about to perform some nodes due to a UI change.
    def prePerform(self):
        for n in self.nodes:
            n.hasRun = False
            
    def perform(self,node=None):
        # if we are already running this method, exit. This
        # will be atomic because GIL. The use case here can
        # happen because turning a knob quickly will fire
        # off events quicker than we can run code. It seems.
        # It happens, anyway.
        if self.performingGraph:
            return
            
        self.prePerform()
        self.performingGraph=True
        if node is None:
            for n in self.nodes:
                # identify root nodes (no connected inputs)
                if all(i is None for i in n.inputs):
                    n.perform()
        else:
            node.perform()
        self.performingGraph=False


    # a node's input has changed, which may change the output types. If it does,
    # we need to check the output connections to see if they are still compatible.
    def inputChanged(self,node):
        # rebuild the types, perhaps replacing None (use the type default) with
        # a type name
        node.type.generateOutputTypes(node)
        # now check the children for nodes which connect to this one
        toDisconnect=[]
        for child in node.children:
            for i in range(0,len(child.inputs)):
                if child.inputs[i] is not None:
                    parent,out = child.inputs[i]
                    if parent is node:
                        outtype = node.getOutputType(out)
                        intype = child.getInputType(i)
                        if not conntypes.isCompatibleConnection(outtype,intype):
                            toDisconnect.append((child,i))
        for child,i in toDisconnect:
            child.disconnect(i)

    def serialise(self,items=None):
        # just serialise all the nodes into a dict, or those in a list.
        d = {}
        if items is None:
            items = self.nodes
        for n in items:
            d[n.name] = n.serialise(items)
        return d
        
    # given a dictionary, build a graph based on it. Do not delete
    # any existing nodes unless asked and do not perform the nodes.
    # Returns a list of the new nodes. 
    
    def deserialise(self,d,deleteExistingNodes):
        if deleteExistingNodes:
            self.nodes=[]
        # disambiguate nodes in the dict, to make sure they don't
        # have the same nodes as ones already in the graph
        d=self.disambiguate(d)        
        # temporary dictionary of nodename->node.
        deref={}
        newnodes=[]
        # first pass - build the nodes
        for nodename,ent in d.items():
            n = self.create(ent['type'])
            newnodes.append(n)
            n.name = nodename # override the default name (which is just a random UUID anyway)
            deref[nodename]=n
            n.deserialise(ent) # will also deserialise type-specific data
            if n.type.md5() != n.savedmd5:
                ui.versionWarn(n)
            n.type.recalculate(n) # recalculate internal data from controls
        # that done, fix up the references
        for nodename,ent in d.items():
            n = deref[nodename]
            conns = ent['ins']
            for i in range(0,len(conns)):
                if conns[i] is not None:
                    oname,output = conns[i] # tuples of name,index: see serialiseConn()
                    other = deref[oname]
                    n.connect(i,other,output,False) # don't automatically perform
        # and finally match output types
        for n in newnodes:
            n.type.generateOutputTypes(n)
        return newnodes
        
    # a really ugly thing for just scanning through and returning true if a node
    # of a given name exists. The *correct* thing to do would be have a dict of
    # nodes by name, of course. But this is plenty fast enough.
    def nodeExists(self,name):
        for n in self.nodes:
            if n.name == name:
                return True
        return False
        
    # change the names of nodes in the dict which have the same names as
    # nodes in the existing graph. Returns a new dict.
    def disambiguate(self,d):
        # we do this by creating a new dict. If there are no nodes in
        # the current graph we can just skip it.
        if len(self.nodes)==0:
            return d
            
        newd={} # new dict to be returned
        renamed={} # dict of renamed nodes: oldname->newname
        newnames=[] # list of new names (values in the above dict)

        for k,v in d.items():
            oldname=k
            # while there's still a node in the actual graph that's the same,
            # or we've already renamed something to that
            while self.nodeExists(k) or k in newnames:
                k = uuid.uuid4().hex # generate a UUID
            renamed[oldname]=k
            newnames.append(k)
            # this avoids modification of the clipboard objects, which is disastrous(?)
            newd[k]=copy.deepcopy(v)
            
        # first pass done, now we need to rename all connections;
        # again, scan the entire new dictionary

        for k,v in newd.items():
            # scan all inputs; done by index
            conns = v['ins']
            for i in range(0,len(conns)):
                if conns[i] is not None:
                    oname,output = conns[i]
                    if oname in renamed:
                        conns[i]=(renamed[oname],output)
            v['ins']=conns                        
        # and pass back the new, disambiguated dict
        return newd
    
    def ensureConnectionsValid(self):
        for n in self.nodes:
            n.ensureConnectionsValid()
        
