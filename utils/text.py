#
# Drawing text on CV images
#

import cv2 as cv

# img - image to write on
# txt - text
# x,y - coords in image
# above - if true, write text x,y extending above that point; if false write it below that point
# fontsize - scale of font*10
# fontthickness - line thickness for drawing
# fontcol - (r,g,b)
 

def write(img,txt,x,y,above,fontsize,fontthickness,fontcol):
    print("text {} fontsize {} thickness {}".format(txt,fontsize,fontthickness))
    (tw,th),baseline = cv.getTextSize(txt,cv.FONT_HERSHEY_SIMPLEX,
        fontsize/10,fontthickness)
        
    if above:   
        ty=y-2
    else:
        ty=y+th+baseline-2
    cv.putText(img,txt,(x,ty),cv.FONT_HERSHEY_SIMPLEX,
        fontsize/10,fontcol,fontthickness)
        
