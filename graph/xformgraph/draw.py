#
# How to draw XFormGraph and its nodes

from grandalf.layouts import SugiyamaLayout,VertexViewer
from grandalf.graphs import *

from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor,QBrush,QLinearGradient,QFont,QTransform

connectorFont = QFont()
#connectorFont.setStyleHint(QFont.SansSerif)
connectorFont.setFamily('Sans Serif')
connectorFont.setPixelSize(10)



import xformgraph

# constants for node drawing

NODEWIDTH=100
NODEHEIGHT=50 # including connectors
XTEXTOFFSET=5 # offset of text into box
YTEXTOFFSET=5

CONNECTORHEIGHT=10 # height of connector box at bottom of node
YPADDING=10 # additional space between nodes

CONNECTORTEXTXOFF=2
INCONNECTORTEXTYOFF=-14
OUTCONNECTORTEXTYOFF=10

# brushes for different connector types

brushDict={}


grad = QLinearGradient(0,0,20,0)
grad.setColorAt(0,Qt.red)
grad.setColorAt(0.4,Qt.green)
grad.setColorAt(0.8,Qt.blue)
grad.setColorAt(1,QColor(50,50,50))

brushDict['img888']=grad
brushDict['imggrey']=Qt.gray


# try to generate a graph (or at least x,y coordinates inside
# the xforms). This is going to be messy, there's no Right Way
# to do it. There exist algorithms for n-ary trees, such as 
# Reingold-Tilford, but this isn't a tree.

# At the moment I'm using grandalf; this will combine all
# the edge connections (inputs and outputs) together but we can
# deal with that at render time.

def place(graph):
    graph.edges = [] # we'll build an edges array
    g = Graph()
    # add the vertices
    for n in graph.nodes:
        n.vert = Vertex(n)
        n.vert.view = VertexViewer(w=NODEWIDTH,h=NODEHEIGHT+YPADDING)
        g.add_vertex(n.vert)
    # now the edges
    for n in graph.nodes:
        for input in range(0,len(n.inputs)):
            inp = n.inputs[input]
            if inp is not None:
                other,output = inp
                n1 = n.vert
                n2 = other.vert
                g.add_edge(Edge(n1,n2))
                # add the edge as input,output (with indices)
                graph.edges.append( (other,output,n,input) )
    # build the layout separately for each unconnected
    # subgraph:
    
    for gr in g.C:
        sug = SugiyamaLayout(gr)
        sug.init_all()
        sug.draw(3) # 3 iterations of algorithm
                
    # invert y coordinates of nodes
    cy = max([n.vert.view.xy[1] for n in graph.nodes])/2
    
    for n in graph.nodes:
        x,y = n.vert.view.xy
        n.vert.view.xy = (x,cy-y)

def getBrush(typename):
    if typename in brushDict:
        return brushDict[typename]
    else:
        return Qt.magenta
        

# basic shapes with extra data attached so we can get the node

class GMainRect(QtWidgets.QGraphicsRectItem):
    def __init__(self,x1,y1,x2,y2,node):
        super().__init__(x1,y1,x2,y2)
        self.node=node

class GConnectRect(QtWidgets.QGraphicsRectItem):
    def __init__(self,x1,y1,x2,y2,node,isInput,index):
        super().__init__(x1,y1,x2,y2)
        self.isInput = isInput
        if isInput:
            name,typename = node.type.inputConnectors[index]
        else:
            name,typename = node.type.outputConnectors[index]
        self.setBrush(getBrush(typename))
        self.index = index
        self.name = name
        self.node=node
        
class GText(QtWidgets.QGraphicsSimpleTextItem):
    def __init__(self,s,node):
        super().__init__(s)
        self.node=node



# add the necessary items to create a node
# (assuming place has been called). Just the node, not the connections.
def makeNodeGraphics(graph,scene,n):
    v = n.vert.view
    x,y = v.xy
    # draw basic rect, leaving room for connectors at top and bottom
    # We keep this rectangle in the node so we can change its colour
    n.rect = GMainRect(x,y+CONNECTORHEIGHT,v.w,NODEHEIGHT-CONNECTORHEIGHT*2,n)
    scene.addItem(n.rect)
    # draw text label
    text=GText(n.type.name,n)
    scene.addItem(text)
    text.setPos(x+XTEXTOFFSET,y+YTEXTOFFSET+CONNECTORHEIGHT)
    # and the connectors
    if len(n.inputs)>0:
        size = v.w/len(n.inputs)
        xx = 0
        for i in range(0,len(n.inputs)):
            r = GConnectRect(xx,y,size,CONNECTORHEIGHT,n,True,i)
            scene.addItem(r)
            text=GText(r.name,n)
            scene.addItem(text)
            text.setPos(xx+CONNECTORTEXTXOFF,y+INCONNECTORTEXTYOFF)
            text.setFont(connectorFont)
            text.setZValue(1)
            xx += size
    if len(n.outputs)>0:
        size = v.w/len(n.outputs)
        xx = 0
        for i in range(0,len(n.outputs)):
            r=GConnectRect(xx,y+NODEHEIGHT-CONNECTORHEIGHT,size,CONNECTORHEIGHT,n,False,i)
            scene.addItem(r)
            text=GText(r.name,n)
            scene.addItem(text)
            text.setPos(xx+CONNECTORTEXTXOFF,y+NODEHEIGHT-CONNECTORHEIGHT+OUTCONNECTORTEXTYOFF)
            text.setFont(connectorFont)
            text.setZValue(1)
            xx += size

# the custom scene, which can handle events on the scene.

class XFormGraphScene(QtWidgets.QGraphicsScene):
    def __init__(self,graph):
        super().__init__()
        self.graph = graph
        # place everything, adding "vert" and "vert.view" data to the nodes
        place(graph)
        # now create the graphics items
        for n in graph.nodes:
            # makes the graphics for the node
            makeNodeGraphics(graph,self,n)
        for n1,output,n2,input in graph.edges:
            x1,y1 = n1.vert.view.xy # this is the "from" and should be on the output ctor
            x2,y2 = n2.vert.view.xy # this is the "to" and should be on the input ctor
            # draw lines
            xoff = 3
            insize = NODEWIDTH/len(n1.outputs)
            outsize = NODEWIDTH/len(n2.inputs)
            x1 = x1+insize*(input+0.5)
            x2 = x2+outsize*(output+0.5)
            y1+=NODEHEIGHT
            self.addLine(x1,y1,x2,y2)
            # with a blob at the tail (yeah, should do arrows at the head)
            self.addEllipse(x1-3,y1-3,6,6,brush=Qt.black)
            
    # change the colour of a node's rectangle to indicate it is selected - will
    # change all the other nodes' rectangles to white
    def selectNode(self,n):
        unselCol = Qt.white
        selCol = QColor(200,200,255)
        for nn in self.graph.nodes:
            nn.rect.setBrush(selCol if nn is n else unselCol)
        self.update()
        
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            p = event.scenePos()
            for i in self.items(p,Qt.IntersectsItemShape,Qt.DescendingOrder,QTransform()):
                if isinstance(i,GMainRect):
                    self.selectNode(i.node)
            
    
