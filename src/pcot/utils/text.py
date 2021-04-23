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
    th=0
    tw=0
    lines = txt.split('\\n')
    hs=[]
    bls=[]
    for s in lines:
        (w,h),baseline = cv.getTextSize(txt,cv.FONT_HERSHEY_SIMPLEX,
            fontsize/10,fontthickness)
        th+=h+baseline
        hs.append(h)
        bls.append(baseline)
        tw=max(w,tw)
        
    if above:   
        ty=y-th+hs[0]
    else:
        ty=y+hs[0]+2
    i=0
    for s in lines:
        cv.putText(img,s,(x,ty),cv.FONT_HERSHEY_SIMPLEX,
            fontsize/10,fontcol,fontthickness)
        ty+=hs[i]+bls[i]
        i+=1
        
