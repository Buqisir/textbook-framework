"""色值体检：CIELAB 明度、灰度打印等效墨量、对白底对比度、两两 ΔE2000。
python3 -I 色值.py '#1E6F8C' '#E3EDF1' ..."""
import sys, math
def lin(c): c/=255; return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def lab(h):
    r,g,b=[int(h[i:i+2],16) for i in (1,3,5)]; R,G,B=lin(r),lin(g),lin(b)
    X=(0.4124*R+0.3576*G+0.1805*B)/0.95047; Y=0.2126*R+0.7152*G+0.0722*B; Z=(0.0193*R+0.1192*G+0.9505*B)/1.08883
    f=lambda t: t**(1/3) if t>0.008856 else 7.787*t+16/116
    return 116*f(Y)-16, 500*(f(X)-f(Y)), 200*(f(Y)-f(Z)), Y
def de2000(a,b):
    L1,a1,b1=a[:3]; L2,a2,b2=b[:3]; C1=math.hypot(a1,b1); C2=math.hypot(a2,b2); Cm=(C1+C2)/2
    G=0.5*(1-math.sqrt(Cm**7/(Cm**7+25**7))); a1p,a2p=(1+G)*a1,(1+G)*a2
    C1p,C2p=math.hypot(a1p,b1),math.hypot(a2p,b2); h1=math.degrees(math.atan2(b1,a1p))%360; h2=math.degrees(math.atan2(b2,a2p))%360
    dL=L2-L1; dC=C2p-C1p; dh=h2-h1
    if C1p*C2p==0: dh=0
    elif dh>180: dh-=360
    elif dh<-180: dh+=360
    dH=2*math.sqrt(C1p*C2p)*math.sin(math.radians(dh/2)); Lm=(L1+L2)/2; Cmp=(C1p+C2p)/2
    hm=(h1+h2)/2 if abs(h1-h2)<=180 else (h1+h2+360)/2
    T=1-0.17*math.cos(math.radians(hm-30))+0.24*math.cos(math.radians(2*hm))+0.32*math.cos(math.radians(3*hm+6))-0.2*math.cos(math.radians(4*hm-63))
    SL=1+0.015*(Lm-50)**2/math.sqrt(20+(Lm-50)**2); SC=1+0.045*Cmp; SH=1+0.015*Cmp*T
    RT=-2*math.sqrt(Cmp**7/(Cmp**7+25**7))*math.sin(math.radians(60*math.exp(-((hm-275)/25)**2)))
    return math.sqrt((dL/SL)**2+(dC/SC)**2+(dH/SH)**2+RT*(dC/SC)*(dH/SH))
cs=sys.argv[1:]; L={c:lab(c) for c in cs}
print("| 色值 | L* | 灰度等效墨量 | 对白底对比度 |\n|---|---|---|---|")
for c in cs:
    Lv,_,_,Y=L[c]; print(f"| `{c}` | {Lv:.1f} | {100-Lv:.0f}% | {1.05/(Y+0.05):.2f}:1 |")
print("\nΔE2000：")
for i,a in enumerate(cs):
    for b in cs[i+1:]: print(f"  {a} vs {b}: {de2000(L[a],L[b]):.1f}  ΔL*={abs(L[a][0]-L[b][0]):.1f}")
