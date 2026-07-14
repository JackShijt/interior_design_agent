import cv2, numpy as np, os
from agents import recognizer_cv as rc

PX=0.1; W,H=int(4200*PX),int(3600*PX); PAD=40
img=np.full((H+2*PAD,W+2*PAD,3),255,np.uint8)
def m(v): return int(round(v*PX))
def line(a,b):
    cv2.line(img,(m(a[0])+PAD,m(a[1])+PAD),(m(b[0])+PAD,m(b[1])+PAD),(0,0,0),3)
line((0,H),(m(2100-450),H)); line((m(2100+450),H),(W,H))  # 底边留门洞
line((0,0),(W,0)); line((0,0),(0,H)); line((W,0),(W,H))
line((m(2520),0),(m(2520),m(2160)))  # 内墙留门洞
cv2.putText(img,"4200",(W//2-20,H+PAD-8),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,0),1)
cv2.putText(img,"3600",(W+PAD+4,H//2),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,0),1)
os.makedirs("data/_proto",exist_ok=True)
cv2.imwrite("data/_proto/fp.png",img)
h=rc.recognize_cv("data/_proto/fp.png")
print("meta:",h["meta"])
print("walls:",len(h["walls"]))
for w in h["walls"]: print("  ",w["id"],w["p1"],w["p2"],w["type"])
print("openings:",len(h["openings"]))
for o in h["openings"]: print("  ",o["id"],o["type"],o["pos_px"],o["width_mm"])
print("rooms:",len(h["rooms"]))
for r in h["rooms"]: print("  ",r["name"],"area=",r["area"],"poly=",r["poly"])
