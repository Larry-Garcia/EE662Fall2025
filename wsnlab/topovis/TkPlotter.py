from .common import *
try:
    from Tkinter import *
except ImportError:  # could be Python3
    try:
        from tkinter import *
    except ImportError:
        # Mock for headless environments
        class Tk: pass
        class Canvas: pass
        LAST = FIRST = BOTH = NONE = NW = YES = None
    
from . import GenericPlotter

arrowMap = { 'head' : LAST, 'tail' : FIRST, 'both' : BOTH, 'none' : NONE }

def colorStr(color):
    if color == None:
        return ''
    else:
        return '#%02x%02x%02x' % tuple(int(x*255) for x in color)

###############################################
class Plotter(GenericPlotter):
    def __init__(self, windowTitle='TopoVis', terrain_size=None, params=None):
        GenericPlotter.__init__(self, params)
        self.nodes = {}
        self.links = {}
        self.nodeLinks = {}
        self.lineStyles = {}
        self.shapes = {}
        self.windowTitle = windowTitle
        self.prepareCanvas(terrain_size)
        self.lastShownTime = 0

    ###################
    def prepareCanvas(self,terrain_size=None):
        if 'Tk' not in globals() and 'Tk' not in locals():
             return # headless
        
        if terrain_size is not None:
            tx,ty = terrain_size
        else:
            tx,ty = 700,700
        
        # Guard against mocked Tk 
        try:
            self.tk = Tk()
            self.tk.title(self.windowTitle)
            self.canvas = Canvas(self.tk, width=tx, height=ty)
            self.canvas.pack(fill=BOTH, expand=YES)
            self.timeText = self.canvas.create_text(0,0,text="time=0.0",anchor=NW)
        except Exception:
            self.tk = None
            self.canvas = None

    ###################
    def setTime(self, time):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        if (time - self.lastShownTime > 0.05):
            self.canvas.itemconfigure(self.timeText, text='Time: %.2fS' % time)
            self.lastShownTime = time

    ###################
    def updateNodePosAndSize(self,id):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        p = self.params
        c = self.canvas
        if id not in self.nodes.keys():
            node_tag = c.create_oval(0,0,0,0)
            label_tag = c.create_text(0,0,text=str(id))
            self.nodes[id] = (node_tag,label_tag)
        else:
            (node_tag,label_tag) = self.nodes[id]

        node = self.scene.nodes[id]
        nodesize = node.scale*p.nodesize
        x1 = node.pos[0] - nodesize
        y1 = node.pos[1] - nodesize
        (x2,y2) = (x1 + nodesize*2, y1 + nodesize*2)
        c.coords(node_tag, x1, y1, x2, y2)
        c.coords(label_tag, node.pos)

        for l in self.nodeLinks[id]:
            self.updateLink(*l)

    ###################
    def configLine(self,tagOrId,style):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        config = {}
        config['fill']  = colorStr(style.color)
        config['width'] = style.width
        config['arrow'] = arrowMap[style.arrow]
        config['dash']  = style.dash
        self.canvas.itemconfigure(tagOrId,**config)

    ###################
    def configPolygon(self,tagOrId,lineStyle,fillStyle):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        config = {}
        config['outline'] = colorStr(lineStyle.color)
        config['width']    = lineStyle.width
        config['dash']     = lineStyle.dash
        config['fill']     = colorStr(fillStyle.color)
        self.canvas.itemconfigure(tagOrId,**config)

    ###################
    def createLink(self,src,dst,style):
        if src is dst:
            raise('Source and destination are the same node')
        if not hasattr(self, 'canvas') or self.canvas is None: return None
        p = self.params
        c = self.canvas
        (x1,y1,x2,y2) = computeLinkEndPoints(
                self.scene.nodes[src],
                self.scene.nodes[dst], 
                p.nodesize)
        link_obj = c.create_line(x1, y1, x2, y2, tags='link')
        self.configLine(link_obj, self.scene.lineStyles[style])
        return link_obj

    ###################
    def updateLink(self,src,dst,style):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        p = self.params
        c = self.canvas
        link_obj = self.links[(src,dst,style)]
        (x1,y1,x2,y2) = computeLinkEndPoints(
                self.scene.nodes[src],
                self.scene.nodes[dst], 
                p.nodesize)
        c.coords(link_obj, x1, y1, x2, y2)


    ###################
    def node(self,id,x,y):
        self.nodeLinks[id] = []
        self.updateNodePosAndSize(id)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def nodemove(self,id,x,y):
        self.updateNodePosAndSize(id)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def nodecolor(self,id,r,g,b):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        (node_tag,label_tag) = self.nodes[id]
        self.canvas.itemconfig(node_tag, outline=colorStr((r,g,b)))
        self.canvas.itemconfigure(label_tag, fill=colorStr((r,g,b)))
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def nodewidth(self,id,width):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        (node_tag,label_tag) = self.nodes[id]
        self.canvas.itemconfig(node_tag, width=width)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def nodescale(self,id,scale):
        # scale attribute has been set by TopoVis
        # just update the node
        self.updateNodePosAndSize(id)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def nodelabel(self,id,label):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        (node_tag,label_tag) = self.nodes[id]
        self.canvas.itemconfigure(label_tag, text=self.scene.nodes[id].label)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def addlink(self,src,dst,style):
        self.nodeLinks[src].append((src,dst,style))
        self.nodeLinks[dst].append((src,dst,style))
        self.links[(src,dst,style)] = self.createLink(src, dst, style)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def dellink(self,src,dst,style):
        self.nodeLinks[src].remove((src,dst,style))
        self.nodeLinks[dst].remove((src,dst,style))
        if hasattr(self, 'links') and (src,dst,style) in self.links:
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.delete(self.links[(src,dst,style)])
            del self.links[(src,dst,style)]
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def clearlinks(self):
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.delete('link')
        self.links.clear()
        for n in self.nodes.keys():
            self.nodeLinks[n] = []
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def circle(self,x,y,r,id,linestyle,fillstyle):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        if id in self.shapes.keys():
            self.canvas.delete(self.shapes[id])
            del self.shapes[id]
        self.shapes[id] = self.canvas.create_oval(x-r,y-r,x+r,y+r)
        self.configPolygon(self.shapes[id], linestyle, fillstyle)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def line(self,x1,y1,x2,y2,id,linestyle):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        if id in self.shapes.keys():
            self.canvas.delete(self.shapes[id])
            del self.shapes[id]
        self.shapes[id] = self.canvas.create_line(x1,y1,x2,y2)
        self.configLine(self.shapes[id], linestyle)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def rect(self,x1,y1,x2,y2,id,linestyle,fillstyle):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        if id in self.shapes.keys():
            self.canvas.delete(self.shapes[id])
            del self.shapes[id]
        self.shapes[id] = self.canvas.create_rectangle(x1,y1,x2,y2)
        self.configPolygon(self.shapes[id], linestyle, fillstyle)
        if hasattr(self, 'tk') and self.tk: self.tk.update()

    ###################
    def delshape(self,id):
        if not hasattr(self, 'canvas') or self.canvas is None: return
        if id in self.shapes.keys():
            self.canvas.delete(self.shapes[id])
            if hasattr(self, 'tk') and self.tk: self.tk.update()
