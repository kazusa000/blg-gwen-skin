"""Masks shared by the titanium sidewall's colour and surface response."""
import numpy as np
def inlay(u,v):
    # Paired champagne rails stop short of the ends of the casting.
    end=np.clip((u-.025)*46,0,1)*np.clip((.975-u)*46,0,1)
    lip=np.exp(-((np.abs(v-.5)-.306)/.012)**2)*end
    incised=np.exp(-((np.abs(v-.5)-.281)/.009)**2)*end
    enamel=np.exp(-((v-.5)/.025)**4)*np.exp(-((u-.5)/.23)**6)
    rivet=np.zeros_like(v);bezel=rivet.copy()
    for x in (.14,.86):
        d=np.sqrt(((u-x)*5.4)**2+((v-.5)*1.04)**2)
        bezel=np.maximum(bezel,np.exp(-((d-.109)/.013)**2))
        rivet=np.maximum(rivet,np.exp(-(d/.082)**4))
    return lip,incised,enamel,rivet,bezel

