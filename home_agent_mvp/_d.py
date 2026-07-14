import cv2, numpy as np, math
import agents.recognizer_cv as rc
house = rc.recognize_cv("data/_proto/fp.png")
# 单独重跑门洞检测逻辑诊断
bin_inv, bin_raw, gray = rc._load_binary("data/_proto/fp.png")
# 重新获取 nodes/walls_px（与 recognize_cv 内部一致）
lines = rc._hough_lines(bin_inv)
walls_px, nodes = rc._build_walls(bin_inv, lines)
nodes, walls_px, (minx,miny) = rc._normalize(nodes, walls_px)
scale = house["meta"]["scale_mm_per_px"]
print("scale", scale)
print("nodes:",[(round(n[0],1),round(n[1],1)) for n in nodes])
print("walls_px:",walls_px)
# 找底边墙段（归一化 y≈0）
for (a,b) in walls_px:
    n1,n2=nodes[a],nodes[b]
    if abs(n1[1]-n2[1])<=1e-6 and abs(n1[0]-n2[0])>10:
        print("BOTTOM wall normalized:", (round(n1[0],1),round(n1[1],1)), (round(n2[0],1),round(n2[1],1)))
        x0=n1[0]+minx; y0=n1[1]+miny; x1=n2[0]+minx; y1=n2[1]+miny
        h2,w2=bin_raw.shape
        L=math.hypot(x1-x0,y1-y0)
        steps=max(2,int(L/4))
        on=[]
        for s in range(steps+1):
            t=s/steps
            x=x0+(x1-x0)*t; y=y0+(y1-y0)*t
            aa=math.atan2(y1-y0,x1-x0); na,nb=-math.sin(aa),math.cos(aa)
            found=False
            for o in range(-3,4):
                xx=int(round(x+na*o)); yy=int(round(y+nb*o))
                if 0<=xx<w2 and 0<=yy<h2 and bin_raw[yy,xx]>0: found=True;break
            on.append(1 if found else 0)
        print("on pattern:",on)
        gaps=[]
        i=0
        while i<len(on):
            if not on[i]:
                j=i
                while j<len(on) and not on[j]: j+=1
                gaps.append((i,j))
                i=j
            else: i+=1
        print("gaps(indices):",gaps)
