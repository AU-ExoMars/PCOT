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
        
    def all():
        return allTypes
        
    # perform the actual action of the transformation, will generate products
    # in that object.
    def perform(self,xform):
        pass
        

# an actual instance of a transformation
class XForm:
    def __init__(self,type):
        self.type = type
        # create unconnected connections. Connections are either None
        # or (Xform,index) tuples - the xform is the object to which we are
        # connected, the index is the index of the output connector on that xform for inputs,
        # or the input connector for outputs
        self.inputs = [None for x in type.inputConnectors]
        # there is also a data product generated for each output by "perform", initially
        # these are None
        self.products = [None for x in type.outputConnectors]
        # on-screen geometry, which should be set before we try to draw it
        self.xy = (0,0)
        self.w = None # unset, will be set on draw
        self.h = None
        
    def dump(self):
        print("---DUMP of {}, geom {},{},{}x{}".format(self.type.name,
            self.xy[0],self.xy[1],self.w,self.h))
        print("  INPUTS:")
        for i in range(0,len(self.inputs)):
            c = self.inputs[i]
            if c:
                other,j = c
                print("    input {} <- {} {}".format(i,other.type.name,j))

    # connect an input to an output on another xform
    def connect(self,input,other,output):
        if input>=0 and input<len(self.inputs) and self is not other:
            if output>=0 and output<len(other.type.outputConnectors):
                self.inputs[input] = (other,output)
        
        
    # disconnect an input 
    def disconnect(self,input):
        if input>=0 and input<len(self.inputs):
            self.inputs[input]=None

    # perform the transformation; delegated to the type object
    def perform(self):
        self.type.perform(self)


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

    def dump(self):
        for n in self.nodes:
            n.dump()
