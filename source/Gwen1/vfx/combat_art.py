"""Author tileable twin-colour filaments, moving blade facets and four-point jewels."""
from pathlib import Path
import numpy as np
from PIL import Image

ART = Path(__file__).resolve().parent / 'art'
ICE = np.array([45, 161, 255])
ROSE = np.array([255, 93, 183])
PEARL = np.array([251, 244, 255])


class Canvas:
    def __init__(self, w, h):
        self.x, self.y = np.meshgrid((np.arange(w)+.5)/w, (np.arange(h)+.5)/h)
        self.rgb = np.zeros((h,w,3))
        self.alpha = np.zeros((h,w))

    def layer(self, coverage, color):
        a = np.clip(coverage, 0, 1)
        self.rgb = self.rgb*(1-a[:,:,None]) + color*a[:,:,None]
        self.alpha = self.alpha*(1-a) + a

    def save(self, stem):
        rgb = self.rgb / np.maximum(self.alpha[:,:,None], 1e-8)
        rgba = np.dstack((rgb, self.alpha*255))
        Image.fromarray(np.uint8(np.clip(rgba,0,255))).save(ART/(stem+'.png'))


def weave(stem, wide):
    c = Canvas(512,128)
    x,y = c.x,c.y
    phase = 2*np.pi*x
    broad = .12 if wide else .072
    for sign, tint in ((-1, ICE),(1, ROSE)):
        center = .5 + sign*(.16+.108*np.sin(phase)+.036*np.sin(phase*2+.65))
        d = (y-center)*sign
        c.layer(.23*np.exp(-(d/(broad*1.9))**2), tint)
        depth = np.clip((d/broad+1)/2,0,1)
        facets = .60+.29*np.abs(2*((x*7+depth*.7)%1)-1)
        c.layer(.81*np.exp(-(d/broad)**4)*facets, tint)
        c.layer(.69*np.exp(-((d-broad*.42)/.013)**2), .52*tint+.48*PEARL)
        c.layer(.64*np.exp(-((d+broad*1.6+.030*np.cos(phase*2))/.012)**2), tint)
        stitch = np.abs((x*10+sign*.22)%1-.5)
        c.layer(.88*np.clip(1-stitch/.28-np.abs(d+broad*.48)/.025,0,1), PEARL)
    c.save(stem)


def jewel_shape(x,y):
    # Concave four-ray silhouette. Split the faces by a diagonal ridge.
    distance = (np.sqrt(np.abs(x))+np.sqrt(np.abs(y)))**2
    return distance, np.where((x*y >= 0) == (np.abs(x) > np.abs(y)), 1., 0.)


def body_wake():
    c=Canvas(512,128)
    phase=2*np.pi*c.x
    for sign,tint in ((-1,ICE),(1,ROSE)):
        center=.5+sign*(.139+.077*np.cos(phase)+.025*np.sin(phase*2))
        d=(c.y-center)*sign
        c.layer(.27*np.exp(-(d/.18)**2),tint)
        c.layer(.88*np.exp(-(d/.095)**4),tint)
        c.layer(.71*np.exp(-((d+.032)/.023)**2),.43*tint+.57*PEARL)
        c.layer(.76*np.exp(-((d-.15-.026*np.cos(phase))/.019)**2),tint)
        stitch=np.abs((c.x*5+sign*.2)%1-.5)
        c.layer(.90*np.clip(1-stitch/.34-np.abs(d-.022)/.033,0,1), PEARL)
    c.save('e_body_wake')


def star(stem, tint):
    c = Canvas(192,192)
    x,y=(c.x-.5)*2/.89,(c.y-.5)*2/.98
    d,face=jewel_shape(x,y)
    c.layer(.32*np.exp(-(x*x+y*y)/.075), tint)
    c.layer(np.clip((1.04-d)*31,0,1), tint)
    c.layer(np.clip((.93-d)*25,0,1)*(.12+.42*face), PEARL)
    c.layer(np.clip((.56-d)*14,0,1)*.68, .60*PEARL+.40*tint)
    c.layer(.45*np.exp(-((x-y)/.028)**2)*np.exp(-(x*x+y*y)/.50), PEARL)
    # Archive textures use power-of-two dimensions.
    c.save(stem)
    with Image.open(ART/(stem+'.png')) as im:
        resized=im.resize((128,128),Image.Resampling.LANCZOS)
    resized.save(ART/(stem+'.png'))


def blade():
    # A higher-resolution, UV-wide enamel sheen for the attached Scissors
    # submesh. Narrow paired cores stay saturated after the in-game mip chain.
    c=Canvas(512,512)
    x,y=c.x,c.y
    for shift,tint in ((.18,ICE),(.68,ROSE)):
        d=(x+2*y-shift+.5)%1-.5
        c.layer(.22*np.exp(-(d/.16)**2),tint)
        c.layer(.78*np.exp(-(d/.049)**2),tint)
        c.layer(.48*np.exp(-((d-.063)/.012)**2),.64*PEARL+.36*tint)
        c.layer(.34*np.exp(-((d+.090+.018*np.sin(9*x))/ .018)**2),tint)
    for cx,cy,sz,tint in ((.24,.37,.15,ICE),(.68,.92,.095,ROSE),(.82,.53,.065,ICE),(.32,.75,.041,ROSE)):
        dx=((x-cx+.5)%1-.5)/sz
        dy=((y-cy+.5)%1-.5)/sz
        d,face=jewel_shape(dx,dy)
        c.layer(.39*np.exp(-(dx*dx+dy*dy)/.15),tint)
        c.layer(np.clip((1-d)*14,0,1), .47*tint+.53*PEARL)
    c.save('e_blade_facets')


def blade_sweep():
    """Sparse travelling glints. A separate emitter keeps its troughs off the base glow."""
    c=Canvas(512,512)
    x,y=c.x,c.y
    for side,tint in ((-1,ICE),(1,ROSE)):
        center=.5+side*(.155+.048*np.sin(2*np.pi*(2.1*x)+side*.47)+.014*np.sin(2*np.pi*5*x))
        d=(y-center)*side
        c.layer(.18*np.exp(-(d/.016)**2),tint)
        c.layer(.68*np.exp(-(d/.0048)**2),tint)
        c.layer(.60*np.exp(-((d-.007)/.0017)**2),.54*PEARL+.46*tint)
    for cx,cy,size,tint in ((.19,.27,.060,ICE),(.37,.79,.050,ROSE),(.66,.42,.056,ICE),(.84,.68,.047,ROSE)):
        dx=((x-cx+.5)%1-.5)/size
        dy=(y-cy)/size
        d,face=jewel_shape(dx,dy)
        c.layer(np.clip((1.02-d)*18,0,1)*.74,tint)
        c.layer(np.clip((.73-d)*12,0,1)*(.15+.38*face),PEARL)
    c.save('e_blade_sweep')


def paint():
    ART.mkdir(exist_ok=True)
    weave('e_dash_filament',False)
    weave('e_swing_brocade',True)
    body_wake()
    blade()
    blade_sweep()
    for stem,tint in (('ice',ICE),('rose',ROSE)):
        star('combat_star_'+stem,tint)


if __name__=='__main__':
    paint()
