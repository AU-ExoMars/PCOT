import traceback,inspect,hashlib,re,copy
from collections import deque
from pancamimage import Image

import ui,conntypes

# dictionary of name -> transformation type
allTypes = dict()

# pattern for detecting names of "name N" format
nameNumberRegex = re.compile(r'(\w+)\s+([0-9]+)')

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
    def __init__(self,name,group,ver):
        self.group = group
        self.name = name
        self.ver = ver
        # add to the global dictionary
        if name in allTypes:
            raise Exception("xform type name already in use: "+name)
        # register the type
        allTypes[name]=self
        # does this node have an "enabled" button? Change in subclass if reqd.
        self.hasEnable=False
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
    recursePerform=True
    def __init__(self,type,name):
        self.type = type
        self.savedver = type.ver
        # create unconnected connections. Connections are either None
        # or (Xform,index) tuples - the xform is the object to which we are
        # connected, the index is the index of the output connector on that xform for inputs,
        # or the input connector for outputs
        self.inputs = [None for x in type.inputConnectors]
        # we keep a dict of those nodes which get inputs from us, and how many. We can't
        # keep the actual output connections easily, because they are one->many.
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
        self.scene = None # the scene I'm in
        self.inrects = [None for x in self.inputs] # input connector GConnectRects
        self.outrects = [None for x in self.outputs] # output connector GConnectRects
        self.helpwin = None # no help window
        self.enabled = True # a lot of nodes won't use; see XFormType.
        
    def setEnabled(self,b):
        if self.tab is not None:
            self.tab.setNodeEnabled(b)
        self.enabled=b
        self.scene.selChanged()
        self.perform()
        
    def serialise(self,selection=None):
        # build a serialisable python dict of this node's values, including
        # only connections to/from the nodes in the selection (which may
        # be None if you want to serialize the whole set)
        d = {}
        d['xy'] = self.xy
        d['type'] = self.type.name
        d['ins'] = [serialiseConn(c,selection) for c in self.inputs]
        d['comment'] = self.comment
        d['outputTypes'] = self.outputTypes
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
        self.savedver = d['ver'] # ver is version node was saved with
        self.savedmd5 = d['md5'] # and stash the MD5 we were saved with

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
                        other.perform() # perform the input node; the output should perform
        
        
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

    # change an output. This should be called by the type's perform method,
    # and used to call perform on children: now that's done in perform()
    # itself to both avoid multiple calls and to avoid ordering problems.
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
            raise Exception("child count <0 in node {}, child {}".format(self.name,n.name))

    # perform the transformation; delegated to the type object. Also tells
    # any tab open on a node that its node has changed.
    def perform(self):
        ui.msg("Performing {}".format(self.name))
        print("Performing {} hastab={}".format(self.name,self.tab is not None))
#        traceback.print_stack()
        try:
            self.type.perform(self)
#            for o in self.outputs:
#                if isinstance(o,Image):
#                    print("Out: ",o)
                
            # tell the tab that this node has changed
            if self.tab is not None:
                self.tab.onNodeChanged()
            # now all outputs have been set, run connected child nodes.
            # This is where recursion occurs.
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
            
# a graph of transformation nodes
class XFormGraph:
    def __init__(self):
        # all the nodes
        self.nodes = []
        # nothing in the clipboard
        self.clipboard = []
        
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
    
    # copy selected items to the clipboard. This copies a serialized
    # version, like that used for load/save. On deserialisation, node
    # names will be changed to make them unique.
    def copy(self,selection):
        self.clipboard = self.serialise(selection)
        
    # paste the clipboard. This involves deserialising, first ensuring
    # that nodes in the clipboard don't have the same names as those
    # in the actual graph. Returns a list of new nodes.
    def paste(self):
        return self.deserialise(self.clipboard,False)
        
    # remove a note from the graph, and close any tab/window
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
    # any existing nodes and do not perform the nodes. Returns a list
    # of the new nodes. 
    
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
            n.name = nodename # override the default name
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
                # take our name and dissect it if possible into "name" "number".
                m = nameNumberRegex.match(k)
                if m is None: # there's no number element, probably. Tack one on.
                    k=k+' 0'
                else:
                    # it's in the form "name 00" so dissect out the number and increment it.
                    nameElement = m.group(1)
                    numberElement = int(m.group(2))+1
                    k = nameElement+' '+str(numberElement)
            renamed[oldname]=k
            newnames.append(k)
            # this avoids modification of the clipboard objects, which is disastrous.
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
