using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using System.Runtime.InteropServices;

class Probe {
 [StructLayout(LayoutKind.Sequential)] struct TextureDesc { public uint Width,Height,MipLevels,ArraySize,Format; public uint SampleCount,SampleQuality,Usage,BindFlags,CPUAccessFlags,MiscFlags; }
 [StructLayout(LayoutKind.Sequential)] struct Subresource { public IntPtr Data; public uint Pitch,SlicePitch; }
 [StructLayout(LayoutKind.Sequential)] struct Viewport { public float X,Y,Width,Height,MinDepth,MaxDepth; }
 [StructLayout(LayoutKind.Sequential)] struct Mapped { public IntPtr Data; public uint RowPitch,DepthPitch; }
 [StructLayout(LayoutKind.Sequential)] struct BufferDesc { public uint Size,Usage,Bind,CPU,Misc,Stride; }
 [StructLayout(LayoutKind.Sequential)] struct RTBlend { public uint Enable,Src,Dest,Op,SrcAlpha,DestAlpha,OpAlpha; public byte Mask; [MarshalAs(UnmanagedType.ByValArray,SizeConst=3)] public byte[] Padding; }
 [StructLayout(LayoutKind.Sequential)] struct BlendDesc { public uint AlphaToCoverage,Independent; [MarshalAs(UnmanagedType.ByValArray,SizeConst=8)] public RTBlend[] Target; }
 [StructLayout(LayoutKind.Sequential)] struct SamplerDesc { public uint Filter,AddressU,AddressV,AddressW; public float Bias; public uint Aniso,Comparison; [MarshalAs(UnmanagedType.ByValArray,SizeConst=4)] public float[] Border; public float MinLod,MaxLod; }

 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateDevice(IntPtr adapter,uint driver,IntPtr software,uint flags,[In] int[] levels,uint n,uint sdk,out IntPtr device,out int feature,out IntPtr context);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Compile(IntPtr src,UIntPtr len,IntPtr name,IntPtr defs,IntPtr inc,IntPtr entry,IntPtr target,uint flags,uint effect,out IntPtr blob,out IntPtr errors);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateTexture(IntPtr self,ref TextureDesc desc,ref Subresource data,out IntPtr obj);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateRTV(IntPtr self,IntPtr resource,IntPtr desc,out IntPtr view);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateSRV(IntPtr self,IntPtr resource,IntPtr desc,out IntPtr view);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateShader(IntPtr self,IntPtr data,UIntPtr len,IntPtr linkage,out IntPtr shader);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateBuffer(IntPtr self,ref BufferDesc desc,ref Subresource data,out IntPtr obj);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateBlend(IntPtr self,ref BlendDesc desc,out IntPtr obj);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateSampler(IntPtr self,ref SamplerDesc desc,out IntPtr obj);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void Release(IntPtr self);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate IntPtr BlobPtr(IntPtr self);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate UIntPtr BlobSize(IntPtr self);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void PSShader(IntPtr ctx,IntPtr shader,IntPtr classes,uint n);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void PSSetMany(IntPtr ctx,uint slot,uint count,[In] IntPtr[] items);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void PSSetBuffers(IntPtr ctx,uint slot,uint count,[In] IntPtr[] items);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void SetViewports(IntPtr ctx,uint count,ref Viewport vp);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void SetRT(IntPtr ctx,uint count,[In] IntPtr[] targets,IntPtr depth);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void SetBlend(IntPtr ctx,IntPtr blend,[In] float[] factor,uint mask);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void ClearRT(IntPtr ctx,IntPtr target,[In] float[] color);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void Draw(IntPtr ctx,uint count,uint start);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void Topology(IntPtr ctx,uint type);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void CopyResource(IntPtr ctx,IntPtr dst,IntPtr src);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int MapResource(IntPtr ctx,IntPtr resource,uint sub,uint mode,uint flags,out Mapped map);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void UnmapResource(IntPtr ctx,IntPtr resource,uint sub);
 [DllImport("d3d11.dll",CallingConvention=CallingConvention.StdCall)]
 static extern int D3D11CreateDevice(IntPtr adapter,uint driver,IntPtr software,uint flags,[In] int[] levels,uint count,uint sdk,out IntPtr device,out int feature,out IntPtr context);
 [DllImport("d3dcompiler_47.dll",CallingConvention=CallingConvention.StdCall,EntryPoint="D3DCompile")]
 static extern int D3DCompile(IntPtr src,UIntPtr len,IntPtr name,IntPtr defs,IntPtr include,IntPtr entry,IntPtr target,uint flags,uint effect,out IntPtr blob,out IntPtr errors);

 static T Fn<T>(IntPtr self,int slot) where T:class {
   IntPtr vt=Marshal.ReadIntPtr(self),fp=Marshal.ReadIntPtr(vt,slot*IntPtr.Size);
   return (T)(object)Marshal.GetDelegateForFunctionPointer(fp,typeof(T));
 }
 static IntPtr Ptr(byte[] data) { IntPtr p=Marshal.AllocHGlobal(data.Length); Marshal.Copy(data,0,p,data.Length); return p; }
 static void Ok(int h,string op) { if(h<0) throw new Exception(op+" HRESULT 0x"+h.ToString("x8")); }
 static byte[] CompileVS() {
   string src="struct O{float4 p:SV_Position;float4 t0:TEXCOORD0;float4 t1:TEXCOORD1;float4 t2:TEXCOORD2;float4 t3:TEXCOORD3;float4 t4:TEXCOORD4;float4 t5:TEXCOORD5;float4 t6:TEXCOORD6;float4 t7:TEXCOORD7;float4 t8:TEXCOORD8;float4 t9:TEXCOORD9;float4 t10:TEXCOORD10;float4 t11:TEXCOORD11;float4 t12:TEXCOORD12;float4 t13:TEXCOORD13;float4 t14:TEXCOORD14;float4 t15:TEXCOORD15;float4 c:COLOR0;}; O main(uint id:SV_VertexID){O o;float2 p=float2((id<<1)&2,id&2);o.p=float4(p*float2(2,-2)+float2(-1,1),0,1);o.t0=float4(.5,.5,.5,.5);o.t1=o.t0;o.t2=float4(0,0,1,1);o.t3=float4(0,0,1,1);o.t4=0;o.t5=.5;o.t6=0;o.t7=0;o.t8=0;o.t9=0;o.t10=0;o.t11=0;o.t12=0;o.t13=0;o.t14=0;o.t15=0;o.c=1;return o;}";
   IntPtr s=Marshal.StringToHGlobalAnsi(src),e=Marshal.StringToHGlobalAnsi("main"),t=Marshal.StringToHGlobalAnsi("vs_5_0"),blob,err;
   int hr=D3DCompile(s,(UIntPtr)Encoding.ASCII.GetByteCount(src),IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,e,t,0,0,out blob,out err);
   if(hr<0) throw new Exception("VS compile: "+(err==IntPtr.Zero?hr.ToString("x"):Marshal.PtrToStringAnsi(Fn<BlobPtr>(err,3)(err))));
   uint n=(uint)Fn<BlobSize>(blob,4)(blob).ToUInt64();byte[] b=new byte[n];Marshal.Copy(Fn<BlobPtr>(blob,3)(blob),b,0,(int)n);Fn<Release>(blob,2)(blob);return b;
 }
 static byte[] Pixel(string path){byte[] b=File.ReadAllBytes(path);if(b.Length<32||Encoding.ASCII.GetString(b,0,4)!="DXBC")throw new Exception("bad DXBC "+path);uint n=BitConverter.ToUInt32(b,24);return b.Take((int)n).ToArray();}
 static IntPtr MakeTex(IntPtr dev, byte[] rgba, uint w, uint h, uint format, uint bind) {
   bool staging=bind==0xffffffffu;
   TextureDesc d=new TextureDesc{Width=w,Height=h,MipLevels=1,ArraySize=1,Format=format,SampleCount=1,Usage=staging?3u:0u,BindFlags=staging?0u:bind,CPUAccessFlags=staging?0x20000u:0};
   Subresource s=new Subresource{Data=Ptr(rgba),Pitch=w*4,SlicePitch=w*h*4};
   IntPtr tex;Ok(Fn<CreateTexture>(dev,5)(dev,ref d,ref s,out tex),"CreateTexture2D");Marshal.FreeHGlobal(s.Data);return tex;
 }
 static IntPtr Buffer(IntPtr dev, byte[] bytes) {
   BufferDesc d=new BufferDesc{Size=(uint)bytes.Length,Usage=0,Bind=4};
   Subresource s=new Subresource{Data=Ptr(bytes),Pitch=0,SlicePitch=0};IntPtr p;
   Ok(Fn<CreateBuffer>(dev,3)(dev,ref d,ref s,out p),"CreateBuffer");Marshal.FreeHGlobal(s.Data);return p;
 }
 static void WriteFloat(byte[] b,int at,float v){System.Buffer.BlockCopy(BitConverter.GetBytes(v),0,b,at,4);}
 static byte[] Run(IntPtr dev,IntPtr ctx,byte[] vsBytes,byte[] psBytes,IntPtr[] srvs,IntPtr[] cbs,IntPtr[] samplers,float[] back){
   IntPtr vs=IntPtr.Zero,ps=IntPtr.Zero;Ok(Fn<CreateShader>(dev,12)(dev,Ptr(vsBytes),(UIntPtr)vsBytes.Length,IntPtr.Zero,out vs),"CreateVS");
   Ok(Fn<CreateShader>(dev,15)(dev,Ptr(psBytes),(UIntPtr)psBytes.Length,IntPtr.Zero,out ps),"CreatePS");
   IntPtr rt=MakeTex(dev,new byte[4],1,1,28,0x20),rtv,st=MakeTex(dev,new byte[4],1,1,28,0xffffffff);
   Ok(Fn<CreateRTV>(dev,9)(dev,rt,IntPtr.Zero,out rtv),"CreateRTV");
   var vp=new Viewport{Width=1,Height=1,MinDepth=0,MaxDepth=1};Fn<SetViewports>(ctx,44)(ctx,1,ref vp);
   Fn<PSShader>(ctx,11)(ctx,vs,IntPtr.Zero,0);Fn<PSShader>(ctx,9)(ctx,ps,IntPtr.Zero,0);
   Fn<Topology>(ctx,24)(ctx,4);
   Fn<PSSetMany>(ctx,8)(ctx,0,16,srvs);
   Fn<PSSetMany>(ctx,10)(ctx,0,16,Enumerable.Repeat(samplers[0],16).ToArray());
   Fn<PSSetBuffers>(ctx,16)(ctx,0,3,cbs);
   Fn<SetRT>(ctx,33)(ctx,1,new[]{rtv},IntPtr.Zero);
   BlendDesc bd=new BlendDesc{AlphaToCoverage=0,Independent=0,Target=Enumerable.Range(0,8).Select(i=>new RTBlend{Enable=(uint)(i==0?1:0),Src=5,Dest=6,Op=1,SrcAlpha=2,DestAlpha=1,OpAlpha=1,Mask=15,Padding=new byte[3]}).ToArray()};
   IntPtr blend;Ok(Fn<CreateBlend>(dev,20)(dev,ref bd,out blend),"CreateBlend");
   Fn<SetBlend>(ctx,35)(ctx,blend,new[]{1f,1f,1f,1f},0xffffffff);
   Fn<ClearRT>(ctx,50)(ctx,rtv,back);Fn<Draw>(ctx,13)(ctx,3,0);
   Fn<CopyResource>(ctx,47)(ctx,st,rt);Mapped m;Ok(Fn<MapResource>(ctx,14)(ctx,st,0,1,0,out m),"Map");
   byte[] b=new byte[4];Marshal.Copy(m.Data,b,0,4);Fn<UnmapResource>(ctx,15)(ctx,st,0);
   return b;
 }
 static IntPtr PixelSRV(IntPtr dev, byte r,byte g,byte b,byte a){
   IntPtr t=MakeTex(dev,new[]{b,g,r,a},1,1,87,8),s;Ok(Fn<CreateSRV>(dev,7)(dev,t,IntPtr.Zero,out s),"CreateSRV");return s;
 }
 static int Main(string[] a){
   try {
    string root=a.Length>0?a[0]:"custom-skins/tmp/Gwen1/recall/build/full-source/shading-check";
    IntPtr device,ctx;int feature;Ok(D3D11CreateDevice(IntPtr.Zero,5,IntPtr.Zero,0,new[]{0xb100,0xb000,0xa100,0xa000},4,7,out device,out feature,out ctx),"D3D11CreateDevice WARP");
    byte[] vs=CompileVS();IntPtr white=PixelSRV(device,255,255,255,255),fow=PixelSRV(device,0,0,0,255),noLut=PixelSRV(device,0,0,0,0),diffuse,mask,matcap;
    SamplerDesc sd=new SamplerDesc{Filter=0x15,AddressU=3,AddressV=3,AddressW=3,Aniso=1,Comparison=8,Border=new float[4],MinLod=0,MaxLod=float.MaxValue};
    IntPtr sampler;Ok(Fn<CreateSampler>(device,23)(device,ref sd,out sampler),"CreateSampler");
    byte[] frame=new byte[528],draw=new byte[272];WriteFloat(draw,0,1);WriteFloat(draw,4,1);WriteFloat(draw,8,1);WriteFloat(draw,16,1);WriteFloat(draw,20,1);WriteFloat(draw,24,1);WriteFloat(draw,28,1);WriteFloat(draw,32,1);WriteFloat(draw,36,1);
    byte[] mtestCb=new byte[16];WriteFloat(mtestCb,4,1);WriteFloat(mtestCb,8,1);
    IntPtr testB=Buffer(device,mtestCb),fb=Buffer(device,frame),db=Buffer(device,draw);
    var back1=new[]{.03f,.08f,.24f,1f};var back2=new[]{.85f,.12f,.65f,1f};
    var bodyShader=Pixel(Path.Combine(root,"body.dxbc"));
    var weaponShader=Pixel(Path.Combine(root,"weapon.dxbc"));
    var dollShader=Pixel(Path.Combine(root,"doll.dxbc"));
    var serializer=new JavaScriptSerializer();
    byte[][] values=serializer.Deserialize<byte[][]>(File.ReadAllText(Path.Combine(root,"reflection-lights.json")));
    var samples=new JavaScriptSerializer().Deserialize<System.Collections.Generic.Dictionary<string,System.Collections.Generic.Dictionary<string,object>>>(File.ReadAllText(Path.Combine(root,"actual-swatches.json")));
    foreach(var entry in samples){
      int[] sample=((System.Collections.ArrayList)entry.Value["diffuse"]).Cast<object>().Select(Convert.ToInt32).ToArray();int maskValue=Convert.ToInt32(entry.Value["mask"]);
      diffuse=PixelSRV(device,(byte)sample[0],(byte)sample[1],(byte)sample[2],(byte)sample[3]);mask=PixelSRV(device,(byte)maskValue,(byte)maskValue,(byte)maskValue,255);IntPtr active=Buffer(device,mtestCb);
      string name=entry.Key;
      string meshName=(string)entry.Value["mesh"];
      var ps=meshName=="doll"?dollShader:(meshName=="weapon"?weaponShader:bodyShader);
      for(int light=0;light<values.Length;light++){
        matcap=PixelSRV(device,values[light][0],values[light][1],values[light][2],values[light][3]);
        IntPtr[] srvs=Enumerable.Repeat(white,16).ToArray();srvs[0]=fow;srvs[1]=noLut;srvs[2]=diffuse;srvs[3]=mask;srvs[4]=matcap;
        byte[] x=Run(device,ctx,vs,ps,srvs,new[]{active,fb,db},new[]{sampler},back1),y=Run(device,ctx,vs,ps,srvs,new[]{active,fb,db},new[]{sampler},back2);
        int bgDelta=Math.Abs(x[0]-y[0])+Math.Abs(x[1]-y[1])+Math.Abs(x[2]-y[2]);
      Console.WriteLine(name+" matcap="+(light==0?"dark":"highlight")+" alpha="+x[3]+" rgba="+x[0]+","+x[1]+","+x[2]+","+x[3]+" bgDelta="+bgDelta+" source="+sample[0]+","+sample[1]+","+sample[2]+" mask="+maskValue);
        if(x[3]!=255||bgDelta!=0)throw new Exception(name+" should be opaque on either background.");
        for (int channel=0;channel<3;channel++){
          int expected=Math.Min(255,(int)Math.Round(sample[channel]+values[light][channel]*maskValue/255.0));
          if(Math.Abs(x[channel]-expected)>2)throw new Exception(name+" lost its albedo or masked highlight.");
        }
      }
    }
    return 0;
   }catch(Exception e){Console.Error.WriteLine(e);return 1;}
 }
}
