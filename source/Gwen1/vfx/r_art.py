"""Facet enamels, silk and moving reflections for the Needlework particle meshes."""
import numpy as np
from PIL import Image

from combat_art import ART, Canvas, ICE, PEARL, ROSE

GOLD=np.array([255,192,122])


def crystal(shade):
    c=Canvas(512,256)
    u,v=c.x,c.y
    band=(v*8).astype(int)
    f=(v*8)%1
    ice=[(96,222,255),(26,98,211)]
    rose=[(255,130,202),(166,41,134)]
    if shade=='ice': rose=[(194,210,251),(88,121,199)]
    if shade=='rose': ice=[(239,187,243),(147,74,170)]
    palette=np.array([*ice,*rose,(214,243,255),(245,194,129),(255,232,188),(125,89,137)])
    base=palette[band]
    # Large, irregular internal facets read at game scale; narrow cuts catch
    # light along the edge of the stone rather than banding the entire shaft.
    plane=(u*3.7+f*.84+np.sin(band)*.23)%1
    facets=np.where(plane<.30,.43,np.where(plane<.68,.93,.66))
    spec=.34*np.exp(-((plane-.68)/.13)**2)+.5*np.exp(-((u-.40+.13*f)/.042)**2)
    metal=band>=4
    metal_ref=.60+.30*np.cos(14*u+2.4*f)+.08*np.cos(39*u-f)
    c.layer(np.ones_like(u),base*np.where(metal,metal_ref,facets)[:,:,None])
    c.layer(np.where(metal,.54*np.exp(-((u-.29+.10*f)/.07)**2),spec),PEARL)
    c.layer(np.where(metal,0,.38*np.exp(-((plane-.30)/.012)**2)),PEARL)
    c.save('r_needle_'+shade)


def floss(style):
    c=Canvas(512,128)
    u,v=c.x,c.y
    phase=2*np.pi*u
    for side in (-1,1):
        tint=ICE if side<0 else (PEARL*.70+ICE*.30 if style=='silver' else ROSE)
        amp=.035 if style=='silver' else .115
        mid=.5+side*(.13+amp*np.sin(phase+.42))
        d=(v-mid)*side
        c.layer(.19*np.exp(-(d/.20)**2),tint)
        c.layer(.85*np.exp(-(d/.062)**4),tint)
        c.layer(.75*np.exp(-((d+.020)/.013)**2),.65*PEARL+.35*tint)
        if style=='crown':
            c.layer(.90*np.exp(-((d-.10-.028*np.cos(phase))/.020)**2),GOLD)
        stitches=np.abs((u*(5 if style=='silver' else 7)+side*.19)%1-.5)
        c.layer(.80*np.clip(1-stitches/.23-np.abs(d-.029)/.025,0,1),PEARL)
    c.save('r_thread_'+style)
    taper=np.sin(np.pi*u)**.68
    c.rgb*=taper[:,:,None]
    c.alpha*=taper
    c.save('r_cast_'+style)


def fibre(shade):
    c=Canvas(128,32)
    tint={'ice':ICE,'rose':ROSE,'crown':GOLD}[shade]
    c.layer(np.ones_like(c.x),tint)
    c.layer(.44*np.exp(-((np.sin(2*np.pi*(c.x*4+c.y))) / .46)**2),PEARL)
    c.save('r_fibre_'+shade)


def reflection():
    c=Canvas(256,128)
    band=(8*c.y).astype(int)
    d=c.x-.10-.027*(c.y*8%1-.5)
    c.layer(np.where(band>=4,.80,.36)*np.exp(-(d/.047)**2),GOLD)
    c.layer(.88*np.exp(-(d/.012)**2),PEARL)
    c.save('r_gilt_sweep')


def flow(shade,orbit=False):
    c=Canvas(512,128)
    rng=np.random.default_rng(318 if shade=='ice' else 791)
    u,v=c.x,c.y
    def noise(u,v,n,m):
        # The two U edges meet continuously under both tiling and UV scrolling.
        lattice=rng.uniform(-1,1,(m,n))
        x,y=u*n,v*m
        i,j=np.floor(x).astype(int),np.floor(y).astype(int)
        f,g=x-i,y-j
        f,g=f*f*(3-2*f),g*g*(3-2*g)
        return ((1-g)*((1-f)*lattice[j%m,i%n]+f*lattice[j%m,(i+1)%n])+
                g*((1-f)*lattice[(j+1)%m,i%n]+f*lattice[(j+1)%m,(i+1)%n]))
    phase=2*np.pi*u
    warp=.062*noise(u,v,3,4)+.028*noise(u,v,9,7)
    center=.49+.078*np.sin(phase+.5)+.047*np.sin(2*phase-.61)+warp
    width=.194+.035*np.sin(phase-.9)+.016*noise(u,v,6,4)
    # Advect the density through periodic vortices. A low core underneath
    # the returning curls keeps neighbouring sections connected.
    uu,vv=u.copy(),v.copy()
    for cx,cy,r,spin in [(.13,.49,.29,1.85),(.52,.65,.21,-2.1),(.84,.42,.24,1.65)]:
        dx=((uu-cx+.5)%1-.5)*2.6
        dy=vv-cy
        angle=spin*np.exp(-(dx*dx+dy*dy)/r**2)
        uu+=(dx*np.cos(angle)-dy*np.sin(angle)-dx)/2.6
        vv+=dx*np.sin(angle)+dy*np.cos(angle)-dy
    d=(vv-center)/width
    turbulent=.52*noise(uu,vv+warp,5,6)+.28*noise(uu,vv+warp,11,13)+.20*noise(uu,vv,26,17)
    # Keep a jewel-blue / fuchsia core. The earlier pale lavender and 65%
    # white strand layer blended to a near-white streak at game scale.
    tint=np.array((35,126,255) if shade=='ice' else (255,55,174))
    alt=np.array((96,69,211) if shade=='ice' else (184,42,146))
    pearl=tint*.62+np.array((181,226,255))*.38
    edge=np.clip(np.minimum(v,1-v)/.16,0,1)**1.4
    c.layer(.31*np.exp(-.77*((v-center)/width)**2)*edge,alt)
    c.layer(.78*np.exp(-1.40*(d-.21*np.sin(2*phase))**2)*edge*(.72+.58*turbulent),tint)
    for i in range(4):
        mid=(-1.13+i*.62)+.33*np.sin(2*np.pi*uu+.92*i)+.46*noise(uu,vv,4+i,6)
        strength=.31+.18*np.cos(phase+i*1.3)+.15*turbulent
        c.layer(strength*np.exp(-((d-mid)/(.13+.03*i))**2)*edge,pearl if i%2 else tint)
    if orbit:
        # Fine condensate drifts on the moving arc. Feather each grain into the veil.
        for i in range(32):
            cu,cv=rng.random(),rng.uniform(.26,.74)
            rr=rng.uniform(.0024,.0068)
            dx=((u-cu+.5)%1-.5)/rr
            dy=(v-cv)/(rr*3.7)
            c.layer(rng.uniform(.22,.61)*np.exp(-(dx*dx+dy*dy)),pearl)
    c.save(('r_orbit_haze_' if orbit else 'r_flow_')+shade)


def facet_light():
    c=Canvas(256,128)
    band=(8*c.y).astype(int)
    distance=c.x-.17-.064*(8*c.y%1-.5)
    strength=np.where(band<4,.90,.27)
    c.layer(.40*strength*np.exp(-(distance/.058)**2),ICE*.32+PEARL*.68)
    c.layer(.94*strength*np.exp(-(distance/.018)**2),PEARL)
    c.save('r_facet_light')


def mist_end_mask():
    c=Canvas(256,128)
    # The whole strip samples this once. The sides dissolve before the core,
    # with unequal feather lengths for the wisps on either side of the needle.
    u,v=c.x,c.y
    edge=np.abs(2*v-1)
    depth=.22+.19*edge+.064*np.sin(9*v+.4)+.032*np.sin(21*v)
    rise=np.clip((u-.016)/depth,0,1)
    fall=np.clip((1-u-.016)/(depth+.04*np.cos(13*v)),0,1)
    alpha=rise*rise*(3-2*rise)*fall*fall*(3-2*fall)
    c.layer(alpha,np.array([255,255,255]))
    c.save('r_mist_end_mask')


def flight_wake():
    c = Canvas(1024, 128)
    u, v = c.x, c.y
    bend = .055*np.sin(5.1*u+.2) + .042*np.sin(10.3*u-.63)
    y = v - .50 - bend
    spread = .63 + .35*np.sin(np.pi*u)
    c.layer(.59*np.exp(-(y/(.225*spread))**2), np.array([75, 55, 169]))
    c.layer(.78*np.exp(-((y + .092*spread)/(.113*spread))**2), np.array([36, 155, 244]))
    c.layer(.73*np.exp(-((y - .109*spread)/(.097*spread))**2), np.array([241, 77, 172]))
    for offset, frequency, color in [(-.09, 8.7, [121, 219, 252]), (.12, 6.3, [255, 152, 213]),
                                     (.008, 13.4, [175, 144, 245])]:
        strand = offset*spread + .044*np.sin(frequency*u+offset*9)
        c.layer(.55*np.exp(-((y-strand)/(.024+.018*u))**2), np.array(color))
    def smooth(x):
        x = np.clip(x, 0, 1)
        return x*x*(3-2*x)
    tail = smooth((1-u)/(.54 + .13*np.sin(v*12)))
    edge = smooth(np.minimum(v,1-v)/.13)
    envelope = smooth(u/.044) * tail * edge
    c.alpha *= envelope
    c.rgb *= envelope[...,None]
    c.save('r_flight_wake')


def paint():
    for shade in ('ice','rose','crown'):
        crystal(shade)
        fibre(shade)
    reflection()
    facet_light()
    flight_wake()
    with Image.open(ART/'r_flight_wake.png') as wake:
        for shade in ('ice','crown'):
            sheet = Image.new('RGBA',(512,512))
            with Image.open(ART/f'r_needle_{shade}.png') as needle:
                sheet.paste(needle.resize((512,250),Image.Resampling.LANCZOS),(0,2))
            sheet.paste(wake.resize((512,250),Image.Resampling.LANCZOS),(0,260))
            sheet.save(ART/f'r_projectile_{shade}.png')
    # Camera-trail U repeats in world space. Density stays above zero on the
    # central filament at every U, including both ends and the lower mip levels.
    wind = Canvas(512,128)
    phase = 2*np.pi*wind.x
    y = wind.y-.5
    bend = .048*np.sin(phase) + .024*np.sin(2*phase+.73)
    wind.layer(.67*np.exp(-((y-bend)/.218)**2),np.array([218,226,250]))
    for offset,thickness in [(-.105,.037),(.025,.055),(.145,.028)]:
        center = offset + bend + .026*np.sin(2*phase+offset*10)
        wind.layer(.84*np.exp(-((y-center)/thickness)**2),np.array([251,250,255]))
    edge = np.clip(np.minimum(wind.y,1-wind.y)/.11,0,1)**2
    wind.rgb *= edge[...,None]
    wind.alpha *= edge
    wind.save('r_wind_fibre')
    mist_end_mask()
    for shade in ('ice','rose'):
        flow(shade)
        flow(shade,orbit=True)
    grain=Canvas(32,32)
    d=(2*grain.x-1)**2+(2*grain.y-1)**2
    grain.layer(.34*np.exp(-3.6*d),ICE*.34+ROSE*.35+PEARL*.31)
    grain.layer(.84*np.exp(-12*d),PEARL)
    grain.save('r_orbit_pearl')
    for style in ('silver','loom','crown'):
        floss(style)
