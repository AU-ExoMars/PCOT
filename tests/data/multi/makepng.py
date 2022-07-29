from PIL import Image

def mk(col):
    img = Image.new('I;16', (80,30), color=col)
    img.save(f"{col}.png")
    
mk(0)
mk(32768)
mk(65535)
