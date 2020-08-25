#
# How to draw XFormGraph and its nodes

from grandalf.layouts import SugiyamaLayout,VertexViewer
from grandalf.graphs import *

from PyQt5 import QtWidgets, uic, QtGui, QtCore
from PyQt5.QtCore import Qt,QPointF
from PyQt5.QtGui import QColor,QBrush,QLinearGradient,QFont,QTransform

import math

import xformgraph


connectorFont = QFont()
#connectorFont.setStyleHint(QFont.SansSerif)
connectorFont.setFamily('Sans Serif')
connectorFont.setPixelSize(10)



# constants for node drawing

NODEWIDTH=100
NODEHEIGHT=50 # including connectors
XTEXTOFFSET=5 # offset of text into box
YTEXTOFFSET=5

CONNECTORHEIGHT=10 # height of connector box at bottom of node
YPADDING=10 # additional space between nodes

CONNECTORTEXTXOFF=2       # x offset of connector label
INCONNECTORTEXTYOFF=-14   # y offset of connector label on inputs
OUTCONNECTORTEXTYOFF=10   # y offset of connector label on outputs
ARROWHEADLENGTH=10        # length of arrowhead lines
ARROWHEADANGLE=math.radians(15)

# brushes for different connector types

brushDict={}

grad = QLinearGradient(0,0,20,0)
grad.setColorAt(0,Qt.red)
grad.setColorAt(0.4,Qt.green)
grad.setColorAt(0.8,Qt.blue)
grad.setColorAt(1,QColor(50,50,50))

brushDict['img888']=grad
brushDict['imggrey']=Qt.gray

# convert all brushes to actual QBrush objects
brushDict = { k:QBrush(v) for k,v in brushDict.items()}

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
                
    # invert y coordinates of nodes so we have the source at the top
    cy = max([n.vert.view.xy[1] for n in graph.nodes])/2
    
    snark=0    
    for n in graph.nodes:
        x,y = n.vert.view.xy
        x+=snark # TESTING - shift each node a bit right
        snark+=20
        n.vert.view.xy = (x,cy-y)

def getBrush(typename):
    if typename in brushDict:
        return brushDict[typename]
    else:
        return Qt.magenta
        

# basic shapes with extra data attached so we can get the node

class GMainRect(QtWidgets.QGraphicsRectItem):
    def __init__(self,x1,y1,x2,y2,node):
        self.offsetx = 0 # these are the distances from our original pos.
        self.offsety = 0
        super().__init__(x1,y1,x2,y2)
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable | \
            QtWidgets.QGraphicsItem.ItemIsMovable | \
            QtWidgets.QGraphicsItem.ItemSendsGeometryChanges )
        self.node=node
    # deal with items moving
    def itemChange(self,change,value):
        if change==QtWidgets.QGraphicsItem.ItemPositionChange:
            dx = value.x()-self.offsetx
            dy = value.y()-self.offsety
            self.offsetx = value.x()
            self.offsety = value.y()
            # update the node position; reconstructing the scene should work
            x,y = self.node.vert.view.xy
            self.node.vert.view.xy = (x+dx,y+dy)
            
            # remake the connection arrows
            self.scene().rebuildArrows()
        return super().itemChange(change,value)

class GConnectRect(QtWidgets.QGraphicsRectItem):
    def __init__(self,parent,x1,y1,x2,y2,node,isInput,index):
        super().__init__(x1,y1,x2,y2,parent=parent)
        self.isInput = isInput
        if isInput:
            name,typename = node.type.inputConnectors[index]
        else:
            name,typename = node.type.outputConnectors[index]
        brush = getBrush(typename)
        t = QTransform().translate(x1,0) # need to translate brush patterns
        brush.setTransform(t)
        self.setBrush(brush)
        self.index = index
        self.name = name
        self.node=node
        
class GText(QtWidgets.QGraphicsSimpleTextItem):
    def __init__(self,parent,s,node):
        super().__init__(s,parent=parent)
        self.node=node




# the custom scene. Note that
# when serializing the nodes, the node.vert.view field should be dealt with.

class XFormGraphScene(QtWidgets.QGraphicsScene):
    def __init__(self,graph):
        super().__init__()
        self.graph = graph
        self.selectionChanged.connect(self.rubberBandSelChanged)
        self.selection=[]
        # place everything, adding "vert" and "vert.view" data to the nodes
        place(graph)
        # and make all the graphics
        self.rebuild()
        
    # rebuild the entire scene from the graph
    def rebuild(self):
        # this will (obv.) change the rubberband selection, so you might get a crash
        # if you do this with live objects
        self.clear() 
        # create the graphics items
        for n in self.graph.nodes:
            # makes the graphics for the node
            self.makeNodeGraphics(n)
        # and make the arrows
        self.arrows=[]
        self.rebuildArrows()

    # assuming that all the nodes have been placed and makeNodeGraphics has been called,
    # connect them all up with arrows according to the connections.
    def rebuildArrows(self):
        # get rid of old arrows
        for line in self.arrows:
            self.removeItem(line)
        self.arrows=[]
        # and make the new ones
        for n1,output,n2,input in self.graph.edges:
            x1,y1 = n1.vert.view.xy # this is the "from" and should be on the output ctor
            x2,y2 = n2.vert.view.xy # this is the "to" and should be on the input ctor
            # draw lines
            xoff = 3
            insize = NODEWIDTH/len(n1.outputs)
            outsize = NODEWIDTH/len(n2.inputs)
            x1 = x1+insize*(input+0.5)
            x2 = x2+outsize*(output+0.5)
            y1+=NODEHEIGHT
            self.arrows.append(self.makeArrow(x1,y1,x2,y2))

    #  create and add an arrow    
    def makeArrow(self,x1,y1,x2,y2):
        line = QtCore.QLineF(x1,y1,x2,y2)
        lineItem = self.addLine(line)
        vec = QtGui.QVector2D(line.p1()-line.p2()).normalized()
        x = vec.x()
        y = vec.y()
        cs = math.cos(ARROWHEADANGLE)
        sn = math.sin(ARROWHEADANGLE)
        xa = x*cs-y*sn
        ya = x*sn+y*cs
        xb = x*cs+y*sn
        yb = -x*sn+y*cs
        poly = QtGui.QPolygonF()
        poly << QPointF(x2,y2) << QPointF(x2+xa*ARROWHEADLENGTH,y2+ya*ARROWHEADLENGTH) << \
            QPointF(x2+xb*ARROWHEADLENGTH,y2+yb*ARROWHEADLENGTH)
        poly = QtWidgets.QGraphicsPolygonItem(poly,parent=lineItem)
        poly.setBrush(Qt.black)
        return lineItem

    # add the necessary items to create a node
    # (assuming place has been called). Just the node, not the connections.
    def makeNodeGraphics(self,n):
        v = n.vert.view
        x,y = v.xy
        # draw basic rect, leaving room for connectors at top and bottom
        # We keep this rectangle in the node so we can change its colour
        n.rect = GMainRect(x,y+CONNECTORHEIGHT,v.w,NODEHEIGHT-CONNECTORHEIGHT*2,n)
        self.addItem(n.rect)
        # draw text label
        text=GText(n.rect,n.type.name,n)
        text.setPos(x+XTEXTOFFSET,y+YTEXTOFFSET+CONNECTORHEIGHT)
        # and the connectors
        if len(n.inputs)>0:
            size = v.w/len(n.inputs)
            xx = x
            for i in range(0,len(n.inputs)):
                # connection rectangles are parented to the main rectangle
                r = GConnectRect(n.rect,xx,y,size,CONNECTORHEIGHT,n,True,i)
                text=GText(n.rect,r.name,n)
                text.setPos(xx+CONNECTORTEXTXOFF,y+INCONNECTORTEXTYOFF)
                text.setFont(connectorFont)
                text.setZValue(1)
                xx += size
        if len(n.outputs)>0:
            size = v.w/len(n.outputs)
            xx = x
            for i in range(0,len(n.outputs)):
                # connection rectangles are parented to the main rectangle
                r=GConnectRect(n.rect,xx,y+NODEHEIGHT-CONNECTORHEIGHT,size,CONNECTORHEIGHT,n,False,i)
                text=GText(n.rect,r.name,n)
                text.setPos(xx+CONNECTORTEXTXOFF,y+NODEHEIGHT-CONNECTORHEIGHT+OUTCONNECTORTEXTYOFF)
                text.setFont(connectorFont)
                text.setZValue(1)
                xx += size

    # handle selection by changing the colour of the main rect of the selected item
    # and building the selection list of nodes.
    def rubberBandSelChanged(self):
        unselCol = Qt.white
        selCol = QColor(200,200,255)
        items = self.selectedItems()
        self.selection=[]
        for n in self.graph.nodes:
            if n.rect in items:
                self.selection.append(n)
                c = selCol
            else:
                c = unselCol
            n.rect.setBrush(c)
        self.update()
