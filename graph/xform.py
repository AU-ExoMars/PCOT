import json,traceback
from collections import deque
import ui

# dictionary of name -> transformation type
allTypes = dict()

# Superclass for a transformation type. There is a singleton subclassed
# from this for each type. 

# This is a singleton decorator which, unusually, is not lazy, because we
# need the xforms to be registered at initialisation. Thus the class creation
# forces an instance to be created.        
class singleton:
    def __init__(self,cls,*args,**kwargs):
        self._cls=cls
        self._instance = self._cls(*args,**kwargs)
        
    def __call__(self):
        return self._instance

class XFormType():
    def __init__(self,name):
        self.name = name
        # add to the global dictionary
        if name in allTypes:
            raise Exception("xform type name already in use: "+name)
        # register the type
        allTypes[name]=self
        # number of nodes of this type
        self.count=0
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
        
    def doAutoserialise(self,node):
        return {name:node.__dict__[name] for name in self.autoserialise}
        
    def doAutodeserialise(self,node,ent):
        for name in self.autoserialise:
            node.__dict__[name] = ent[name]

    def addInputConnector(self,name,typename):
        self.inputConnectors.append( (name,typename) )
    def addOutputConnector(self,name,typename):
        self.outputConnectors.append( (name,typename) )
        
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
    # and should be called in the tab's onNodeChanged() AFTER the controls are read
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
        
    # create a tab connected to this xform - also needs the main UI window.
    # Might return none, if this xform doesn't have a meaningful UI.
    def createTab(self,mainui,xform):
        return None

# serialise a connection (xform,i) into (xformName,i)
def serialiseConn(c):
    if c:
        x,i = c
        return (x.name,i)
    else:
        return None

# an actual instance of a transformation
class XForm:
    recursePerform=True
    def __init__(self,type,name):
        self.type = type
        # create unconnected connections. Connections are either None
        # or (Xform,index) tuples - the xform is the object to which we are
        # connected, the index is the index of the output connector on that xform for inputs,
        # or the input connector for outputs
        self.inputs = [None for x in type.inputConnectors]
        # we keep a dict of those nodes which get inputs from us, and how many
        self.children = {}
        # there is also a data output generated for each output by "perform", initially
        # these are None
        self.outputs = [None for x in type.outputConnectors]
        # these are the overriding output types; none if we use the default
        # given by the type object (see the comment on outputConnectors
        # in XFormType)
        self.outputTypes = [None for x in type.outputConnectors]
        self.comment = "" # nodes can have comments
        # set the unique name
        self.name = name
        
        # UI-DEPENDENT DATA DOWN HERE
        self.xy = (0,0) # this SHOULD be serialised
        
        # this stuff shouldn't be serialized
        # on-screen geometry, which should be set before we try to draw it
        self.w = None # unset, will be set on draw
        self.h = None
        self.tab = None # no tab open
        self.current = False
        self.rect = None # the main GMainRect rectangle
        self.inrects = [None for x in self.inputs] # input connector GConnectRects
        self.outrects = [None for x in self.outputs] # output connector GConnectRects
        
    def serialise(self):
        # build a serialisable python dict of this node's values
        d = {}
        d['xy'] = self.xy
        d['type'] = self.type.name
        d['ins'] = [serialiseConn(c) for c in self.inputs]
        d['comment'] = self.comment
        d['outputTypes'] = self.outputTypes
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
        # autoserialised data
        self.type.doAutodeserialise(self,d)
        # run the additional deserialisation method
        self.type.deserialise(self,d)
        
    def getInputType(self,i):
        if i>=0 and i<len(self.inputs):
            return self.type.inputConnectors[i][1]
        else:
            return None
        
    def getOutputType(self,i):
        if i>=0 and i<len(self.outputs):
            if self.outputTypes[i] is None:
                return self.type.outputConnectors[i][1]
            else:
                return self.outputTypes[i]
                
    # this should be used to change an output type is generateOutputTypes
    def changeOutputType(self,index,type):
        self.outputTypes[index]=type
        if self.outrects[index] is not None:
            self.outrects[index].typeChanged()
        
    # this can be used in XFormType's generateOutputTypes if the polymorphism
    # is simply that some outputs should match the types of some inputs. The
    # input is a list of (out,in) tuples. Typical usage for a node with a single
    # input and output is matchOutputsToInputs([(0,0)])
    def matchOutputsToInputs(self,pairs):
        # reset all types
        self.outputTypes = [None for x in self.type.outputConnectors]
        for o,i in pairs:
            if self.inputs[i] is not None:
                parent,pout = self.inputs[i]
                # the output type should be the same as the actual input (which is the
                # type of the output connected to that input)
                self.changeOutputType(o,parent.getOutputType(pout))
                self.outrects[o].typeChanged()
    
    def dump(self):
        print("---DUMP of {}, geom {},{},{}x{}".format(self.type.name,
            self.xy[0],self.xy[1],self.w,self.h))
        print("  INPUTS:")
        for i in range(0,len(self.inputs)):
            c = self.inputs[i]
            if c:
                other,j = c
                print("    input {} <- {} {}".format(i,other.type.name,j))
        print("   CHILDREN:")
        for k,v in self.children.items():
            print("    {} ({} connections)".format(k.name,v))
            
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
                        self.perform()
        
        
    # disconnect an input 
    def disconnect(self,input):
        if input>=0 and input<len(self.inputs):
            if self.inputs[input] is not None:
                n,i = self.inputs[input]
                n.decreaseChildCount(self)
                self.inputs[input]=None
                self.perform()
            
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

    # change an output - typically caused by perform, this will cause all children
    # to perform too, leading to recursive descent of the tree. May also be caused
    # by source data change. The recursive descent behaviour is not used in loading.
    def setOutput(self,i,data):
        self.outputs[i]=data
        if XForm.recursePerform:
            for n in self.children:
                n.perform()
            
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
            raise Exception("child count <0 in node {}, child {}".format(self.name,n.name))

    # perform the transformation; delegated to the type object. Also tells
    # any tab open on a node that its node has changed.
    def perform(self):
        ui.mainui.msg("Performing {}".format(self.name))
        print("Performing {}".format(self.name))
        try:
            self.type.perform(self)
            if self.tab is not None:
                self.tab.onNodeChanged()
        except Exception as e:
            traceback.print_exc()
            ui.mainui.logXFormException(self,e)
        
    # get the value of an input
    def getInput(self,i):
        if self.inputs[i] is None:
            return None
        else:
            n,i = self.inputs[i]
            return n.outputs[i]
            
# are two connectors compatible?
def isCompatibleConnection(outtype,intype):
    # image inputs accept all images
    if intype == 'img':
        return 'img' in outtype 
    else:
        # otherwise has to match exactly
        return outtype==intype    

# a graph of transformation nodes
class XFormGraph:
    def __init__(self):
        # all the nodes
        self.nodes = []
        
    # create a new node, passing in a type name.
    def create(self,typename):
        if typename in allTypes:
            tp = allTypes[typename]
            # disambiguate node names using the count
            count = tp.count
            tp.count+=1
            xform = XForm(tp,"{} {}".format(typename,count))
            self.nodes.append(xform)
            tp.init(xform)
        else:
            raise Exception("Transformation type not found: "+typename)
        return xform
        
    def remove(self,node):
        node.disconnectAll()
        if node.tab is not None:
            node.tab.nodeDeleted()
        self.nodes.remove(node)
        
    def dump(self):
        for n in self.nodes:
            n.dump()
    

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
                        if not isCompatibleConnection(outtype,intype):
                            toDisconnect.append((child,i))
        for child,i in toDisconnect:
            child.disconnect(i)

    def serialise(self,file):
        d = {}
        for n in self.nodes:
            d[n.name] = n.serialise()
        json.dump(d,file,sort_keys=True,indent=4)

    # given a dictionary, build a graph based on it
    def deserialise(self,file):
        # delete old graph - remember that the UI must close all open tabs!
        d = json.load(file)
        self.nodes = []
        # temporary dictionary of nodename->node
        deref={}
        # first pass - build the nodes
        for nodename,ent in d.items():
            n = self.create(ent['type'])
            n.name = nodename # override the default name
            deref[nodename]=n
            n.deserialise(ent) # will also deserialise type-specific data
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

        # we also have to tell all the nodes to perform recursively, from roots down,
        # omitting any already done in the process.
        self.downRecursePerform()
        

    def downRecursePerform(self):
        XFormGraph.already=set()
        for n in self.nodes:
            # identify root nodes (no connected inputs)
            if all(i is None for i in n.inputs):
                self.bfs(n)

    # breadth-first traversal, with extra "already visited" flag because we may visit
    # several roots
    def bfs(self,n):
        XForm.recursePerform=False # turn off perform recursion in setOutput
        try:
            if not n in XFormGraph.already:
                XFormGraph.already.add(n)
                queue=deque()
                queue.append(n)
                while len(queue)>0:
                    p = queue.popleft()
                    p.perform() 
                    for q in p.children:
                        if not q in XFormGraph.already:
                            XFormGraph.already.add(q)
                            queue.append(q)
        finally:
            XForm.recursePerform=True # turn setOutput recursion back on whatever happens
