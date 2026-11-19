"""Top-left pixel bounds on the game diffuse atlas (four pixels of gutter outside each tile)."""
from pathlib import Path
from core import WORK,SKIN
OUT=WORK/'full-source'
SOURCE=SKIN/'Gwen1-BLG.blend'
ATLAS=(8192,4096)
WEAPON_SIZE=(4096,4096)
TILES={'turnaround-v1.png':(8,8,1536,1024),'gwen-mantle-silk.png':(1560,8,1536,1024),
       'bodice':(4672,8,3496,2016),
       'gwen-train-crest.png':(4176,460,126,122),'gwen-hair-streaks.png':(3110,8,1024,768)}
VIEWS=('front','back','left','right','up','rear_low')
WEAPON_CROPS={'Prismatic glass inlay':(156,10,736,1577),'Polished champagne relief':(260,305,628,1105),
              'Pearl and cloisonné enamel':(105,768,783,1630),'Ivory television glass':(353,971,537,1087)}
WEAPON_TILES={'Prismatic glass inlay':(8,8,1512,4072),'Polished champagne relief':(3052,8,1020,2216),
              'Pearl and cloisonné enamel':(1536,8,1490,1896),'Ivory television glass':(1536,1920,792,496)}
for i,key in enumerate(VIEWS):
    TILES['pile/'+key]=(8+i%3*1548,1048+i//3*1520,1504,1504)
    TILES['face/'+key]=(4672+i%3*1156,2048+i//3*1024,1000,1000)
for key,box in WEAPON_TILES.items():TILES['weapon/'+key]=box
for i,key in enumerate(('gold','steel','blue','pink','ink')):
    TILES['wall/'+key]=(1536,2440+i*330,2536,308)
for i in range(8):TILES['dye/'+str(i)]=(4176,626+i*48,448,38)
def coords(box,uv,size=ATLAS):
    x,y,w,h=box
    return (uv*[w-1,h-1]+[x+.5,y+.5])/size

