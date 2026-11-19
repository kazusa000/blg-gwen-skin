"""Restore the front lacing and upper champagne piping at the native UV texel density."""
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
def stitch(texture):
    h,w=texture.shape[:2];im=np.roll(texture,w//2,axis=1).copy()
    y,x=np.mgrid[:h,:w];x=(x+.5)*768/w;y=(y+.5)*480/h
    center=392.+2*np.sin(np.pi*y/325);u=x-center
    hw=np.interp(y,[0,60,110,180,300,345,480],[58,70,57,47,46,54,60])
    # Retain the surrounding fitted brocade and rebuild the narrow ivory placket.
    mask=(np.clip((hw-np.abs(u))/8,0,1)*np.clip((y-69)/22,0,1)*np.clip((352-y)/21,0,1))[:,:,None]
    sheen=15*np.exp(-((u+18)/18)**2)-17*(np.abs(u)/hw).clip(0,1)**1.8-10*np.exp(-((y-183)/40)**2)
    silk=np.array([222,205,213])+sheen[:,:,None]
    silk+=1.15*np.sin(.95*x+.04*y)[:,:,None]
    im=Image.fromarray(np.uint8(np.clip(im*(1-mask)+silk*mask,0,255)))
    pen=ImageDraw.Draw(im)
    factor=w/768
    def points(ps):return [(round(a*factor),round(b*h/480)) for a,b in ps]
    def curve(start,a,b,end):
        t=np.linspace(0,1,48)[:,None]
        return (1-t)**3*start+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*end
    def path(ps,color,width,shift=(0,0)):
        pen.line(points(np.array(ps)+shift),fill=color,width=max(1,round(width*factor)),joint='curve')
    for side in (-1,1):
        # Two curved folds of the neckline join the original central V.
        q=curve(np.array([392,102]),[392+side*23,85],[392+side*54,60],[392+side*77,56])
        path(q,(124,96,109),2.1);path(q,(234,206,194),.9,(0,-.8))
        q=curve(np.array([392+side*77,61]),[392+side*65,106],[392+side*48,182],[392+side*49,317])
        path(q,(142,111,119),2.2);path(q,(231,204,182),.95,(-side*.8,0))
        for a,b in zip(q[::3],q[1::3]):path((a+[side*2,0],b+[side*2,0]),(187,156,150),.8)
    for j,(top,bottom) in enumerate(((106,163),(173,223),(230,276))):
        for side in (-1,1):
            l=392+side*(29+j*.8);r=392-side*(29+j*.8)
            q=curve(np.array([l,top]),[l+side*1,top+9],[r-side*3,bottom-7],[r,bottom])
            blue=(side==1) if j<2 else True
            base=(88,149,187) if blue else (193,101,143)
            gloss=(163,206,219) if blue else (232,163,185)
            path(q,(133,112,128),7.1,(.9,1.25));path(q,base,5.9);path(q,gloss,2.15,(-.7,-.45))
            for xx,yy in ((l,top),(r,bottom)):
                pen.ellipse(points([(xx-2.2,yy-1.8),(xx+2.2,yy+1.8)]),outline=(158,128,117),width=max(1,round(factor)))
                pen.point(points([(xx-1.2,yy-1.0)])[0],fill=(243,218,192))
    return np.roll(np.asarray(im),-w//2,axis=1)

