# dictionary of name -> transformation type
allTypes = dict()

# Superclass for a transformation type. There is a singleton subclassed
# from this for each type. 

# we use a singleton metaclass here - while the class constructor must be referred to with
# all its arguments in the first case (to set up the singleton), any subsequent
# call to the constructor will return the singleton and doesn't require the
# arguments.

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class XFormType(metaclass=Singleton):
    def __init__(self,name):
        self.name = name
        # add to the global dictionary
        if name in allTypes:
            raise Exception("xform type name already in use: "+name)
        allTypes[name]=self
        # these contain tuples of (name,typename). Images have typenames which
        # start with "img"
        self.inputConnectors = []
        self.outputConnectors = []

    def addInputConnector(self,name,typename):
        self.inputConnectors.append( (name,typename) )
    def addOutputConnector(self,name,typename):
        self.outputConnectors.append( (name,typename) )
        
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
        self.outputs = [None for x in type.outputConnectors]
        # there is also a data product generated for each output by "perform", initially
        # these are None
        self.products = [None for x in type.outputConnectors]
        
    def dump(self):
        print("---DUMP of {}".format(self.type.name))
        print("  INPUTS:")
        for i in range(0,len(self.inputs)):
            c = self.inputs[i]
            if c:
                other,j = c
                print("    input {} <- {} {}".format(i,other.type.name,j))
        print("  OUTPUTS:")
        for i in range(0,len(self.outputs)):
            c = self.outputs[i]
            if c:
                other,j = c
                print("    output {} -> {} {}".format(i,other.type.name,j))

    # connect an input to an output on another xform
    def connectIn(self,input,other,output):
        if input>=0 and input<len(self.inputs) and self is not other:
            if output>=0 and output<len(other.outputs):
                self.inputs[input] = (other,output)
                other.outputs[output] = (self,input)
        
        
    # connect an output to an input on another xform
    def connectOut(self,output,other,input):
        if input>=0 and input<len(other.inputs) and self is not other:
            if output>=0 and output<len(self.outputs):
                self.outputs[output] = (other,input)
                other.inputs[input] = (self,output)

    # disconnect an input and the corresponding output on the other xform        
    def disconnectIn(self,input):
        if input>=0 and input<len(self.inputs):
            if self.inputs[input] is not None:
                other,output = self.inputs[input]
                other.outputs[output]=None
                self.inputs[input]=None

    # disconnect an output and the corresponding input on the other xform        
    def disconnectOut(self,output):
        self.dump()
        print("Disconnecting output ",output)
        if output>=0 and output<len(self.outputs):
            if self.outputs[output] is not None:
                other,input = self.outputs[output]
                other.inputs[input] = None
                self.outputs[output] = None
            
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
