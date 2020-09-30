import tokenize,argparse
from tokenize import NUMBER,STRING,NAME,OP

class LinkOut:
    USES = 0
    LINKS = 1
    OWNS = 2
    IS = 3
    
    def __init__(self,dest,type,srcmult,destmult):
        self.dest=dest
        self.srcmult = srcmult
        self.destmult = destmult
        self.type = type
        
    def render(self,src):
        if self.type == LinkOut.USES:
            edge='style="dotted",label="uses"'
        elif self.type == LinkOut.IS:
            edge='arrowhead="empty"'
        elif self.type == LinkOut.OWNS:
            edge='arrowtail="diamond",dir="back",'+self.getMultStr()
        elif self.type == LinkOut.LINKS:
            edge='arrowtail="odiamond",dir="back",'+self.getMultStr()
        else:
            raise Exception("Bad link type")            
        return "CLASS_{}->CLASS_{} [{}]".format(src.name,self.dest.name,edge)
        
    def getMultStr(self):
        src = '*' if self.srcmult else '1'
        dest = '*' if self.destmult else '1'
        return 'headlabel="{}",taillabel="{}"'.format(dest,src)
        
class Class:
    def __init__(self,name,g):
        self.name = name
        self.methods = []
        self.members = []
        self.linksOut = []
        g.classes.append(self)
        
    def addMember(self,name):
        self.members.append(name)
    def addMethod(self,name):
        self.members.append(name)

    def addUses(self,dest):
        self.linksOut.append(LinkOut(dest,LinkOut.USES,False,False))
    
    def addLinks(self,dest,srcmult,destmult):
        self.linksOut.append(LinkOut(dest,LinkOut.LINKS,srcmult,destmult))
    def addLinksOne(self,dest):
        self.addLinks(dest,False,False)
    def addLinksMany(self,dest):
        self.addLinks(dest,False,True)

    def addOwns(self,dest,srcmult,destmult):
        self.linksOut.append(LinkOut(dest,LinkOut.OWNS,srcmult,destmult))
    def addOwnsOne(self,dest):
        self.addOwns(dest,False,False)
    def addOwnsMany(self,dest):
        self.addOwns(dest,False,True)
        
    def addIs(self,dest):
        self.linksOut.append(LinkOut(dest,LinkOut.IS,False,False))
        
    def render(self):
        methodstr = "\\n".join(self.methods)
        memberstr = "\\n".join(self.members)
        lst = [ x for x in [self.name,methodstr,memberstr] if x!='']
        label = "{"+("|".join(lst))+"}"
        return 'CLASS_{} [label="{}"]'.format(self.name,label)

    def renderLinks(self):
        s=[]
        for x in self.linksOut:
            s.append(x.render(self))
        return "\n".join(s)

class Graph:
    def __init__(self):
        self.classes=[]
        
    def render(self):
        print("digraph {")
        print("node [shape=record]")
        print("edge [labeldistance=1.2]")
        for x in self.classes:
            print(x.render())
        for x in self.classes:
            print(x.renderLinks())
        print("}")
        

def gettoken(path):
    with open(path,"rb") as f:
        for toknum, tokval, start, end, line in tokenize.tokenize(f.readline):
            if toknum == NUMBER:
                yield(NUMBER,tokval)
            elif toknum == STRING:
                yield(STRING,tokval)
            elif toknum == NAME:
                yield(NAME,tokval)
            elif toknum == OP:
                yield(OP,tokval)

class Parser:
    def __init__(self,path):
        self.rewindstack=[]
        self.graph=Graph()
        self.basenext = gettoken(path).__next__
        self.classes={}
        while True:
            t,v = self.next()
            if t==NAME:
                if v == 'end':
                    break
                else:
                    self.parseClass(v)
            elif t==OP:
                if v == ';':
                    break # another way of ending
            else:
                raise Exception("expected a class, @, ; or 'end'")
        
    def next(self):
        if len(self.rewindstack)!=0:
            return self.rewindstack.pop()
        else:
            return self.basenext()
    
    def rewind(self,t,v):
        self.rewindstack.append((t,v))
        
    def parseClass(self,name):
        c = Class(name,self.graph)
        c.links=[]
        self.classes[name]=c
        while(True):
            t,v = self.next()
            if t==OP:
                if v ==';':
                    break
                elif v == '@':
                    self.parseLink(c)
                else:
                    self.parseMemberOrMethod(c,v)
            else:
                raise Exception("Expected a method/member type")
                
    def parseMemberOrMethod(self,c,type):
        t,name = self.next()
        if t!=NAME:
            raise Exception("Expected member/method name")
        # methods have () after them, methods don't
        t,v = self.next()
        if t==OP and v=='(': # it's a member
            t,v = self.next() # skip closing bracket
            c.addMethod(type+name)
        else:
            c.addMember(type+name)
            self.rewind(t,v) # rewind the tokeniser
            
    def parseLink(self,c):
        t,linktype = self.next()
        if t!=NAME:
            raise Exception("Expected a link type")
        if not linktype in ['is','links','owns','uses']:
            raise Exception("Expected a link type")
        t,v = self.next()
        destmult = False 
        if t==OP:
            if v=='+':
                destmult = True
                t,dest = self.next()
                if t!=NAME:
                    raise Exception("Expected a link destination class")
            else:
                raise Exception("Expected a link destination class or '+'")
        else:
            dest = v
        c.links.append((linktype,dest,destmult))

    def render(self):
        # build links
        for name,c in self.classes.items():
            for linktype,dest,destmult in c.links:
                if not dest in self.classes:
                    raise Exception("Link to unknown class "+dest)
                dest = self.classes[dest]
                if linktype == 'is':
                    c.addIs(dest)
                elif linktype == 'owns':
                    c.addOwns(dest,False,destmult)
                elif linktype == 'links':
                    c.addLinks(dest,False,destmult)
                elif linktype == 'uses':
                    c.addUses(dest)
        self.graph.render()

if __name__ == "__main__":
    p = argparse.ArgumentParser(description='Generate class diagram')
    p.add_argument('file', metavar='filename', type=str,
                   help='.uml file to read')

    args = p.parse_args()
    Parser(args.file).render()

