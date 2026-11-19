// Textured orthographic rasterization of the reimported native mesh at the packaged idle pose.
'use strict';
const fs=require('node:fs'),path=require('node:path');
const [jobPath]=process.argv.slice(2), job=JSON.parse(fs.readFileSync(jobPath));
const buf=fs.readFileSync(job.skn), sections=buf.readUInt32LE(8), header=12+80*sections;
const local=buf.readUInt32LE(header)===2, ni=buf.readUInt32LE(header+4), nv=buf.readUInt32LE(header+8);
const triAt=header+60,vAt=triAt+2*ni,mat=job.pose,inf=job.influences;
const tex=job.texture.map(o=>({...o,raw:fs.readFileSync(o.path)}));
const pos=new Float32Array(nv*3),normal=new Float32Array(nv*3),uv=new Float32Array(nv*2);
const ranges=[];
const doll=job.subject==='Doll';
for(let i=0;i<sections;i++){
  let a=12+80*i;
  const name=buf.toString('ascii',a,a+64).split('\0')[0];
  if(doll ? name!=='Doll' : (!name.startsWith('Body')&&name!=='Scissors'))continue;
  const first=buf.readUInt32LE(a+64),count=buf.readUInt32LE(a+68),index=buf.readUInt32LE(a+72),n=buf.readUInt32LE(a+76);
  ranges.push({name,first,count,index,n});
  for(let j=first;j<first+count;j++){
    let p=vAt+52*j;
    let x=buf.readFloatLE(p),y=buf.readFloatLE(p+4),z=buf.readFloatLE(p+8);
    let nx=buf.readFloatLE(p+32),ny=buf.readFloatLE(p+36),nz=buf.readFloatLE(p+40);
    for(let k=0;k<4;k++){
      let w=buf.readFloatLE(p+16+k*4);if(!w)continue;
      let M=mat[inf[buf[p+12+k]]];
      for(let r=0;r<3;r++){
        pos[3*j+r]+=w*(M[r][0]*x+M[r][1]*y+M[r][2]*z+M[r][3]);
        normal[3*j+r]+=w*(M[r][0]*nx+M[r][1]*ny+M[r][2]*nz);
      }
    }
    uv[2*j]=buf.readFloatLE(p+44);uv[2*j+1]=buf.readFloatLE(p+48);
  }
}
for(const cam of job.cameras){
  const {w,h,axes,focus,scale,weapon,key}=cam;
  const depth=new Float32Array(w*h);depth.fill(-Infinity);
  const pix=Buffer.alloc(w*h*4),sx=new Float32Array(nv),sy=new Float32Array(nv),sz=new Float32Array(nv),illum=new Float32Array(nv);
  const right=axes[0],down=axes[1],eye=axes[2];
  const side=cam.reverse?1.05:-.77;
  const light=eye.map((e,k)=>.73*e-.61*down[k]+side*right[k]);const ln=Math.hypot(...light);
  const matU=new Float32Array(nv),matV=new Float32Array(nv);
  const cap=tex[doll?2:4];
  for(const s of ranges){
    if(!cam.combined && weapon!==(s.name==='Scissors'))continue;
    for(let j=s.first;j<s.first+s.count;j++){
      let p=3*j,bp=vAt+52*j;
      let x=(weapon?buf.readFloatLE(bp):pos[p])-focus[0],y=(weapon?buf.readFloatLE(bp+4):pos[p+1])-focus[1],z=(weapon?buf.readFloatLE(bp+8):pos[p+2])-focus[2];
      sx[j]=w*.5+scale*(x*right[0]+y*right[1]+z*right[2]);
      sy[j]=h*.5+scale*(x*down[0]+y*down[1]+z*down[2]);sz[j]=x*eye[0]+y*eye[1]+z*eye[2];
      let a=weapon?buf.readFloatLE(bp+32):normal[p],b=weapon?buf.readFloatLE(bp+36):normal[p+1],c=weapon?buf.readFloatLE(bp+40):normal[p+2];const len=Math.hypot(a,b,c)||1;
      matU[j]=.5+.5*(a*right[0]+b*right[1]+c*right[2])/len;
      matV[j]=.5+.5*(a*down[0]+b*down[1]+c*down[2])/len;
      illum[j]=.67+.34*Math.max(0,(a*light[0]+b*light[1]+c*light[2])/(ln*len));
    }
    const isShears=s.name==='Scissors',t=tex[isShears?1:0],ww=t.w,hh=t.h,raw=t.raw,base=local?s.first:0;
    const emissive=job.weaponEmission&&isShears?tex[5]:null;
    const material=job.maskedReflections&&s.name!=='BodyCards'?tex[doll?1:isShears?3:2]:null;
    for(let o=s.index;o<s.index+s.n;o+=3){
      let a=base+buf.readUInt16LE(triAt+2*o),b=base+buf.readUInt16LE(triAt+2*o+2),c=base+buf.readUInt16LE(triAt+2*o+4);
      let x=sx[a],y=sy[a],bx=sx[b]-x,by=sy[b]-y,cx=sx[c]-x,cy=sy[c]-y,det=bx*cy-by*cx;
      if(det>=-1e-7)continue;
      let x0=Math.max(0,Math.floor(x+Math.min(0,bx,cx))),x1=Math.min(w-1,Math.ceil(x+Math.max(0,bx,cx)));
      let y0=Math.max(0,Math.floor(y+Math.min(0,by,cy))),y1=Math.min(h-1,Math.ceil(y+Math.max(0,by,cy)));
      for(let j=y0;j<=y1;j++)for(let i=x0;i<=x1;i++){
        let dx=i+.5-x,dy=j+.5-y,l=(dx*cy-dy*cx)/det,m=(bx*dy-by*dx)/det,k=1-l-m;
        if(k<0||l<0||m<0)continue;
        let pt=j*w+i,z=k*sz[a]+l*sz[b]+m*sz[c];if(z<=depth[pt])continue;
        let u=Math.max(0,Math.min(ww-1,(k*uv[2*a]+l*uv[2*b]+m*uv[2*c])*ww-.5));
        let v=Math.max(0,Math.min(hh-1,(k*uv[2*a+1]+l*uv[2*b+1]+m*uv[2*c+1])*hh-.5));
        let tx=u|0,ty=v|0,fx=u-tx,fy=v-ty,ix1=Math.min(tx+1,ww-1),iy1=Math.min(ty+1,hh-1);
        let A=4*(ty*ww+tx),B=4*(ty*ww+ix1),C=4*(iy1*ww+tx),D=4*(iy1*ww+ix1),I=k*illum[a]+l*illum[b]+m*illum[c];
        const alpha=((1-fy)*((1-fx)*raw[A+3]+fx*raw[B+3])+fy*((1-fx)*raw[C+3]+fx*raw[D+3]))/255;
        const coverage=((i%4)*4+((j+(i%2)*2)%4)+.5)/16;
        if(!material&&alpha<coverage)continue;
        depth[pt]=z;
        let strength=0,lightPixel=0;
        if(material){
          const at=4*(Math.min(material.h-1,Math.floor((v+.5)*material.h/hh))*material.w+Math.min(material.w-1,Math.floor((u+.5)*material.w/ww)));
          strength=material.raw[at]/255;
          const cx=Math.max(0,Math.min(cap.w-1,Math.floor(cap.w*(k*matU[a]+l*matU[b]+m*matU[c]))));
          const cy=Math.max(0,Math.min(cap.h-1,Math.floor(cap.h*(k*matV[a]+l*matV[b]+m*matV[c]))));
          lightPixel=4*(cx+cy*cap.w);
        }
        for(let ch=0;ch<3;ch++){
          const albedo=(1-fy)*((1-fx)*raw[A+ch]+fx*raw[B+ch])+fy*((1-fx)*raw[C+ch]+fx*raw[D+ch]);
          const reflection=material?strength*cap.raw[lightPixel+ch]:0;
          const ex=emissive ? Math.min(emissive.w-1,Math.floor((u+.5)*emissive.w/ww)) : 0;
          const ey=emissive ? Math.min(emissive.h-1,Math.floor((v+.5)*emissive.h/hh)) : 0;
          const glow=emissive ? emissive.raw[4*(ey*emissive.w+ex)+ch] : 0;
          pix[4*pt+ch]=Math.min(255,Math.round(I*(albedo+reflection)+glow));
        }
        pix[4*pt+3]=255;
      }
    }
  }
  fs.writeFileSync(path.join(job.out,key+'.rgba'),pix);
}

