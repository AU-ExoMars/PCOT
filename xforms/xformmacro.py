from PyQt5 import QtWidgets,QtCore
from PyQt5.QtCore import Qt

import ui,ui.tabs,ui.canvas,ui.mainwindow
from xform import xformtype,XFormType
from macros import MacroPrototype,MacroInstance

@xformtype
class XformMacro(XFormType):
    """Encapsulates an instance of a macro"""
    
    def __init__(self):
        super().__init__("macro","utility","0.0.0")
        self.hasEnable=True
        
    def createTab(self,n,w):
        return TabMacro(n,w)
        
    def init(self,node):
        node.instance = None
        
    def serialise(self,node):
        if node.instance is not None:
            name = node.instance.proto.name
        else:
            name = None
        return {'proto': name}

    def deserialise(self,node,d):
        name = d['proto']
        if name is None:
            node.instance = None
        else:
            if name in MacroPrototype.protos:
                node.instance = MacroInstance(MacroPrototype.protos[name])
                ui.error("Macro instantiated, need to update connections")
            else:
                ui.error("Cannot find macro {} in internal dict".format(name))
        
    def perform(self,node):
        pass
        
class TabMacro(ui.tabs.Tab):
    def __init__(self,node,w):
        super().__init__(w,node,'assets/tabmacro.ui')
        self.w.macro.currentIndexChanged.connect(self.macroChanged)
        self.w.openProto.pressed.connect(self.openProto)
        # populate the combobox
        for x in MacroPrototype.protos:
            self.w.macro.addItem(x)
        self.onNodeChanged()
        
    def openProto(self):
        if self.node.instance is not None:
                w=ui.mainwindow.MainUI.createMacroWindow(self.node.instance.proto,False)
            
    def macroChanged(self,i):
        name = self.w.macro.itemText(i)
        if name in MacroPrototype.protos:
            self.node.instance = MacroInstance(MacroPrototype.protos[name])
            ui.error("Macro instantiated, need to update connections")
        else:
            ui.error("Cannot find macro {} in internal dict".format(name))        

    def onNodeChanged(self):
        # set the selected macro to the one which matches our name
        if self.node.instance is not None:
            i = self.w.macro.findText(self.node.instance.proto.name)
            if i<0:
                ui.error("Can't find macro {} in macro combobox!".format(self.node.instance.proto.name))
            else:
                self.w.macro.setCurrentIndex(i)
