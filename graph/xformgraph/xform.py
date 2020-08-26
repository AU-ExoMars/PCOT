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
        allTypes[name]=self
        # these contain tuples of (name,typename). Images have typenames which
        # start with "img"
        self.outputConnectors = []
        self.inputConnectors = []

    def addInputConnector(self,name,typename):
        self.inputConnectors.append( (name,typename) )
    def addOutputConnector(self,name,typename):
        self.outputConnectors.append( (name,typename) )
        
    def getInputType(self,i):
        if i>=0 and i<len(self.inputConnectors):
            return self.inputConnectors[i][1]
        else:
            return None
    def getOutputType(self,i):
        if i>=0 and i<len(self.outputConnectors):
            return self.outputConnectors[i][1]
        else:
            return None
        
    def all():
        return allTypes
        
    # perform the actual action of the transformation, will generate outputs
    # in that object.
    def perform(self,xform):
        pass
        
    # create a tab connected to this xform - also needs the main UI window.
    # Might return none, if this xform doesn't have a meaningful UI.
    def createTab(self,mainui,xform):
        return None
        

# an actual instance of a transformation
class XForm:
    def __init__(self,type):
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
        # on-screen geometry, which should be set before we try to draw it
        self.xy = (0,0)
        self.w = None # unset, will be set on draw
        self.h = None
        self.tab = None # no tab open
        # this may have to be disambiguated
        self.name = type.name
        
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

    # connect an input to an output on another xform
    def connect(self,input,other,output):
        if input>=0 and input<len(self.inputs) and self is not other:
            if output>=0 and output<len(other.type.outputConnectors):
                self.inputs[input] = (other,output)
                other.increaseChildCount(self)
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
    # by source data change.
    def setOutput(self,i,data):
        self.outputs[i]=data
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
        print("Performing ",self.name)
        self.type.perform(self)
        if self.tab is not None:
            self.tab.onNodeChanged()
        
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

    # create a new node, passing in a type name.
    def create(self,type):
        if type in allTypes:
            type = allTypes[type]
            xform = XForm(type)
            self.nodes.append(xform)
        else:
            raise Exception("Transformation type not found: "+type)
        return xform
        
    def remove(self,node):
        node.disconnectAll()
        self.nodes.remove(node)
        

    def dump(self):
        for n in self.nodes:
            n.dump()
