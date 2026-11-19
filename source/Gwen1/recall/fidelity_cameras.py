"""Orthographic cameras shared by the original scene and the round-tripped native mesh."""
import numpy as np
VIEWS={'front':(.05,.10,1),'game':(-.38,.88,1),'back':(.20,.43,-1),
       'left':(-1,.16,.17),'right':(1,.27,.14),'rear_game':(-.54,.94,-1),
       'front_right':(.70,.40,1),'rear_right':(.78,.15,-.85),
       'up':(.03,1,.17),'low':(-.17,-.24,1),'rear_low':(.12,-.22,-1)}
WIDTH,HEIGHT=880,1100
HOLDOUT={'check_game':(.57,.95,.76),'check_back':(-.62,.47,-.86)}
SCALE=214.
CENTER=np.array([0.,96.,0.])
def axes(eye):
    eye=np.asarray(eye,dtype=float);eye/=np.linalg.norm(eye)
    right=np.cross([0.,1.,0.],eye);right/=np.linalg.norm(right)
    return np.stack((right,-np.cross(eye,right),eye),axis=1)

